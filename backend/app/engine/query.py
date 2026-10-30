"""SQL generation from a spec, and the statistical result with the small-cell rule.

All queries run on the hdab schema, which already excludes opted-out patients.
SQL is built from templates; codes and values are bound as parameters.
"""
from __future__ import annotations

import time

from ..datastore import DataStore
from . import smallcell
from .spec import Criterion, GroupBy, Metric, Spec

S = "hdab"  # schema for secondary use


class Q:
    """Collects bound parameters while SQL text is built."""

    def __init__(self):
        self.params: list = []

    def p(self, v) -> str:
        self.params.append(v)
        return "?"

    def like_any(self, col: str, codes: list[str]) -> str:
        if not codes:
            return "TRUE"
        return "(" + " OR ".join(f"{col} LIKE {self.p(c.upper().rstrip('*') + '%')}" for c in codes) + ")"


def _cmp(q: Q, expr: str, c: Criterion) -> str:
    if c.op is None or c.value is None:
        return "TRUE"
    if c.value_max is not None:
        return f"({expr} >= {q.p(float(c.value))} AND {expr} <= {q.p(float(c.value_max))})"
    v = c.value if isinstance(c.value, str) else float(c.value)
    return f"{expr} {c.op} {q.p(v)}"


def _dates(q: Q, col: str, c: Criterion) -> str:
    parts = []
    if c.date_from:
        parts.append(f"{col} >= CAST({q.p(c.date_from)} AS DATE)")
    if c.date_to:
        parts.append(f"{col} <= CAST({q.p(c.date_to)} AS DATE)")
    return " AND ".join(parts) or "TRUE"


def encounter_conditions(q: Q, c: Criterion, alias: str = "") -> str:
    a = f"{alias}." if alias else ""
    conds = [_dates(q, f"{a}start_date", c)]
    if c.inpatient is not None:
        conds.append(f"{a}inpatient" if c.inpatient else f"NOT {a}inpatient")
    if c.encounter_type:
        conds.append(f"{a}type = {q.p(c.encounter_type.lower())}")
    if c.primary_icd10:
        conds.append(q.like_any(f"{a}primary_icd10", c.primary_icd10))
    if c.value is not None and c.type == "data_holder":
        conds.append(f"lower({a}data_holder) = lower({q.p(str(c.value))})")
    return " AND ".join(conds)


def criterion_sql(q: Q, c: Criterion, alias: str = "p") -> str:
    """Boolean SQL expression over a patient row `alias` of hdab.patients."""
    pid = f"{alias}.patient_id"
    if c.type == "condition":
        e = f"{pid} IN (SELECT patient_id FROM {S}.conditions WHERE {q.like_any('code', c.codes)} AND {_dates(q, 'date', c)})"
    elif c.type == "medication":
        # placeholders must be created in the order they appear in the SQL text
        codes = q.like_any("code", c.codes)
        dates = _dates(q, "date", c)
        active = "TRUE"
        if c.active_on:
            active = (f"date <= CAST({q.p(c.active_on)} AS DATE) "
                      f"AND (end_date IS NULL OR end_date >= CAST({q.p(c.active_on)} AS DATE))")
        e = f"{pid} IN (SELECT patient_id FROM {S}.medications WHERE {codes} AND {dates} AND {active})"
    elif c.type == "observation":
        base = f"{q.like_any('code', c.codes)} AND {_dates(q, 'date', c)} AND value IS NOT NULL"
        if c.observation_select == "any" or c.op is None:
            e = f"{pid} IN (SELECT patient_id FROM {S}.observations WHERE {base} AND {_cmp(q, 'value', c)})"
        else:
            agg = {"latest": "arg_max(value, date)", "max": "max(value)", "min": "min(value)", "mean": "avg(value)"}[c.observation_select]
            e = (f"{pid} IN (SELECT patient_id FROM (SELECT patient_id, {agg} AS v FROM {S}.observations "
                 f"WHERE {base} GROUP BY patient_id) WHERE {_cmp(q, 'v', c)})")
    elif c.type == "encounter":
        e = f"{pid} IN (SELECT patient_id FROM {S}.encounters_x WHERE {encounter_conditions(q, c)})"
    elif c.type == "sex":
        e = f"lower({alias}.sex) IN ({', '.join(q.p(v) for v in _sex_values(str(c.value)))})"
    elif c.type == "age":
        e = _cmp(q, f"{alias}.age", c)
    elif c.type == "region":
        e = f"lower({alias}.region) = lower({q.p(str(c.value))})"
    elif c.type == "data_holder":
        e = f"lower({alias}.data_holder) = lower({q.p(str(c.value))})"
    else:  # pragma: no cover
        raise ValueError(c.type)
    return f"NOT ({e})" if c.negate else e


def _sex_values(v: str) -> list[str]:
    v = v.lower()
    if v in ("f", "female", "w", "woman", "women", "weiblich"):
        return ["f", "female", "w", "weiblich"]
    if v in ("m", "male", "man", "men", "männlich"):
        return ["m", "male", "männlich"]
    return [v]


def where_sql(q: Q, crit: list[Criterion], alias: str = "p") -> str:
    return " AND ".join(criterion_sql(q, c, alias) for c in crit) or "TRUE"


def population_sql(q: Q, crit: list[Criterion]) -> str:
    return f"SELECT p.* FROM {S}.patients p WHERE {where_sql(q, crit)}"


# --------------------------------------------------------------------- grouping
def group_expr(q: Q, g: GroupBy, alias: str = "p", enc_alias: str | None = None) -> str:
    if g.dimension == "sex":
        return f"{alias}.sex"
    if g.dimension == "region":
        return f"{alias}.region"
    if g.dimension == "data_holder":
        # a stay belongs to the hospital where it happened
        return f"COALESCE({enc_alias}.data_holder, {alias}.data_holder)" if enc_alias else f"{alias}.data_holder"
    if g.dimension == "year":
        return f"CAST(year({enc_alias}.start_date) AS VARCHAR)" if enc_alias else "NULL"
    if g.dimension == "age_group":
        cases = []
        for (lo, hi), label in zip(g.bins, group_labels(g)):
            cond = f"{alias}.age >= {int(lo)}" + (f" AND {alias}.age <= {int(hi)}" if hi is not None else "")
            cases.append(f"WHEN {cond} THEN {q.p(label)}")
        return "CASE " + " ".join(cases) + " ELSE NULL END"
    raise ValueError(f"group dimension {g.dimension} is evaluated per member")


def group_labels(g: GroupBy) -> list[str]:
    if g.labels:
        return g.labels
    if g.dimension == "age_group":
        return [f"{lo}+" if hi is None else f"{lo}-{hi}" for lo, hi in g.bins]
    if g.members:
        return [m.term or ",".join(m.codes) for m in g.members]
    return list(g.categories)


def all_groups(store: DataStore, g: GroupBy) -> list[str]:
    """Every group that must be shown, even if empty."""
    if g.dimension in ("age_group", "medication", "condition") or g.categories:
        return group_labels(g)
    if g.dimension == "year":
        return [r["v"] for r in store.sql("SELECT DISTINCT CAST(year(start_date) AS VARCHAR) v FROM kis.encounters ORDER BY 1")]
    col = {"sex": "sex", "region": "region", "data_holder": "data_holder"}[g.dimension]
    # categories come from the full KIS so a group emptied by opt-outs still appears
    return [r["v"] for r in store.sql(f"SELECT DISTINCT {col} AS v FROM kis.patients WHERE {col} IS NOT NULL ORDER BY 1")]


# --------------------------------------------------------------------- metrics
def _value_sql(q: Q, v, alias="p") -> str:
    if v.source == "age":
        return f"{alias}.age"
    if v.source == "observation":
        agg = {"latest": "arg_max(value, date)", "first": "arg_min(value, date)", "mean": "avg(value)",
               "max": "max(value)", "min": "min(value)"}[v.select]
        return (f"(SELECT {agg} FROM {S}.observations o WHERE o.patient_id = {alias}.patient_id "
                f"AND {q.like_any('o.code', v.codes)} AND o.value IS NOT NULL)")
    if v.source == "encounter_count":
        return f"(SELECT count(*) FROM {S}.encounters_x e WHERE e.patient_id = {alias}.patient_id)"
    raise ValueError(v.source)


def _split(crit: list[Criterion]) -> tuple[list[Criterion], list[Criterion]]:
    enc = [c for c in crit if c.type == "encounter" and not c.negate]
    return [c for c in crit if c not in enc], enc


def metric_sql(m: Metric, groups: list[GroupBy]) -> tuple[str, list, list[str]]:
    """Build the SQL; each fragment has its own Q so parameters stay in textual order."""
    gcols = [f"g{i}" for i in range(len(groups))]
    if m.unit == "encounters":
        pat, enc = _split(m.criteria)
        qg, qe, qp = Q(), Q(), Q()
        sel = "".join(f", {group_expr(qg, g, 'p', 'e')} AS {c}" for g, c in zip(groups, gcols))
        ewhere = " AND ".join(encounter_conditions(qe, c, "e") for c in enc) or "TRUE"
        pwhere = where_sql(qp, pat)
        base = (f"SELECT e.encounter_id, e.patient_id, e.length_of_stay AS v{sel} "
                f"FROM {S}.patients p JOIN {S}.encounters_x e ON e.patient_id = p.patient_id "
                f"WHERE {pwhere} AND {ewhere}")
        params = qg.params + qp.params + qe.params
        agg = "count(*) AS num, count(DISTINCT patient_id) AS n_pat, count(v) AS n_val, sum(v) AS total"
    else:
        qn, qv, qg, qd = Q(), Q(), Q(), Q()
        num = where_sql(qn, m.criteria)
        val = _value_sql(qv, m.value) if m.kind == "mean" and m.value else "NULL"
        sel = "".join(f", {group_expr(qg, g)} AS {c}" for g, c in zip(groups, gcols))
        if m.kind == "percentage":
            den = where_sql(qd, m.denominator)
            base = f"SELECT p.patient_id, ({num}) AS hit, {val} AS v{sel} FROM {S}.patients p WHERE {den}"
            params = qn.params + qv.params + qg.params + qd.params
        else:
            base = f"SELECT p.patient_id, TRUE AS hit, {val} AS v{sel} FROM {S}.patients p WHERE {num}"
            params = qv.params + qg.params + qn.params
        agg = "count(*) FILTER (WHERE hit) AS num, count(*) AS den, count(v) AS n_val, sum(v) AS total"
    cols = ", ".join(gcols + [agg])
    sql = f"SELECT {cols} FROM ({base}) t" + (f" GROUP BY {', '.join(gcols)}" if gcols else "")
    return sql, params, gcols


def run_metric(store: DataStore, spec: Spec, m: Metric) -> dict:
    t0 = time.perf_counter()
    groups = m.group_by if m.group_by is not None else spec.group_by
    member_dims = [g for g in groups if g.dimension in ("medication", "condition")]
    if member_dims:
        g = member_dims[0]
        rest = [x for x in groups if x is not g]
        rows = []
        for member, label in zip(g.members, group_labels(g)):
            sub = m.model_copy(update={"criteria": m.criteria + [member],
                                       "denominator": m.denominator + ([member] if m.kind == "percentage" else []),
                                       "group_by": rest})
            for r in run_metric(store, spec, sub)["groups"]:
                rows.append({"group": {g.dimension: label, **r["group"]}, **{k: v for k, v in r.items() if k != "group"}})
        return {**_head(m), "groups": rows, "ms": _ms(t0)}

    sql, params, gcols = metric_sql(m, groups)
    raw = store.sql(sql, params)
    by_key = {tuple(r[c] for c in gcols): r for r in raw}
    keys = _cartesian([all_groups(store, g) for g in groups]) if groups else [()]
    out = [{"group": {g.dimension: k for g, k in zip(groups, key)}, **_cell(m, by_key.get(tuple(key), {}))}
           for key in keys]
    return {**_head(m), "groups": out, "sql": sql, "params": [str(p) for p in params], "ms": _ms(t0)}


def _cell(m: Metric, r: dict) -> dict:
    """Apply the small-cell rule. Raw numbers never leave this function for statistics."""
    num, den = int(r.get("num") or 0), int(r.get("den") or 0)
    if m.kind == "count":
        return {"value": smallcell.safe_count(num)}
    if m.kind == "percentage":
        return {"value": smallcell.safe_percentage(num, den),
                "numerator": smallcell.safe_count(num), "denominator": smallcell.safe_count(den)}
    n_val = int(r.get("n_val") or 0)
    # mean of fewer than 10 patients is suppressed
    n_pat = int(r.get("n_pat") or n_val) if m.unit == "encounters" else n_val
    return {"value": smallcell.safe_mean(r.get("total"), n_val if n_pat >= smallcell.THRESHOLD else 0),
            "n": smallcell.safe_count(n_val)}


def _head(m: Metric) -> dict:
    return {"id": m.id, "label": m.label, "kind": m.kind, "unit": m.unit}


def _cartesian(lists: list[list]) -> list[tuple]:
    out = [()]
    for lst in lists:
        out = [o + (x,) for o in out for x in lst]
    return out


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


def run_spec(store: DataStore, spec: Spec) -> list[dict]:
    return [run_metric(store, spec, m) for m in spec.metrics]


def answer_table(spec: Spec, results: list[dict]) -> dict | list:
    """Results pivoted per group: {"Wien": {"adults": 3247, ...}} (nested for several dimensions)."""
    if not spec.group_by:
        return {r["id"]: r["groups"][0]["value"] if r["groups"] else None for r in results}
    table: dict = {}
    for r in results:
        for g in r["groups"]:
            label = " / ".join(str(v) for v in g["group"].values())
            table.setdefault(label, {})[r["id"]] = g["value"]
    return table


def cohort_ids(store: DataStore, crit: list[Criterion]) -> list[str]:
    q = Q()
    return [r["patient_id"] for r in store.sql(f"SELECT patient_id FROM ({population_sql(q, crit)}) ORDER BY 1", q.params)]

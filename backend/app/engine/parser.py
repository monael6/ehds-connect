"""Turns a request (JSON with plain-English definitions) into a Spec.

Rule-based and deterministic, so three runs give the same result:

1. every definition "Name = ..." becomes a named concept (age, ICD-10, ATC, LOINC, sex,
   encounter type, region, hospital, or a combination of other concepts),
2. the question gives the subject ("women with breast cancer"),
3. "Report per <groups>: <a>, <b> and <c>" gives the groups and one metric per item;
   references such as "of them", "their" or "that share" point to the previous metric.

Plain-English terms without a definition are mapped to codes through the code lists
in the data (descriptions of ICD-10 / ATC / LOINC codes, never patient rows) and a small
synonym list. Every mapping is reported to staff.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..config import settings
from ..datastore import DataStore
from .spec import Criterion, GroupBy, Metric, Spec, ValueSpec

ICD = r"[A-TV-Z]\d{2}(?:\.\d{1,2})?"
ATC = r"[A-Z]\d{2}[A-Z]{0,2}\d{0,2}"
LOINC = r"\d{1,5}-\d"

POP_NOUNS = {
    "patients": [], "patient": [], "people": [], "persons": [], "person": [], "individuals": [],
    "adults": [Criterion(type="age", op=">=", value=18, term="adult")],
    "adult": [Criterion(type="age", op=">=", value=18, term="adult")],
    "children": [Criterion(type="age", op="<", value=18, term="child")],
    "minors": [Criterion(type="age", op="<", value=18, term="child")],
    "women": [Criterion(type="sex", value="female", term="women")],
    "woman": [Criterion(type="sex", value="female", term="women")],
    "females": [Criterion(type="sex", value="female", term="women")],
    "men": [Criterion(type="sex", value="male", term="men")],
    "man": [Criterion(type="sex", value="male", term="men")],
    "males": [Criterion(type="sex", value="male", term="men")],
}

# measurement names -> LOINC, from data/README.md
OBSERVATION_SYNONYMS = {
    "hba1c": ["4548-4"], "glycated haemoglobin": ["4548-4"], "glycated hemoglobin": ["4548-4"],
    "long-term blood sugar": ["4548-4"],
    "bmi": ["39156-5"], "body mass index": ["39156-5"],
    "systolic blood pressure": ["8480-6"], "systolic bp": ["8480-6"], "blood pressure": ["8480-6"],
    "egfr": ["62238-1"], "kidney function": ["62238-1"], "glomerular filtration": ["62238-1"],
}

# a few clinical synonyms that do not appear literally in the code descriptions
CONDITION_SYNONYMS = {
    "type 2 diabetes": ["E11"], "type 1 diabetes": ["E10"], "diabetes": ["E10", "E11"],
    "copd": ["J44"], "chronic obstructive pulmonary disease": ["J44"],
    "atrial fibrillation": ["I48"], "afib": ["I48"], "hypertension": ["I10"], "high blood pressure": ["I10"],
    "heart failure": ["I50"], "stroke": ["I63"], "breast cancer": ["C50"], "depression": ["F32"],
    "asthma": ["J45"], "obesity": ["E66"], "chronic kidney disease": ["N18"], "ckd": ["N18"],
    "hip fracture": ["S72"], "femur fracture": ["S72"], "pneumonia": ["J18"], "appendicitis": ["K35"],
    "urinary tract infection": ["N39"], "uti": ["N39"],
}
MEDICATION_SYNONYMS = {
    "metformin": ["A10BA02"], "sglt2 inhibitor": ["A10BK"], "glp-1 receptor agonist": ["A10BJ"],
    "insulin": ["A10A"], "statin": ["C10AA"], "ace inhibitor": ["C09AA"], "arb": ["C09CA"],
    "angiotensin receptor blocker": ["C09CA"], "beta blocker": ["C07"], "calcium channel blocker": ["C08"],
    "oral anticoagulant": ["B01AA", "B01AF"], "anticoagulant": ["B01AA", "B01AF"], "doac": ["B01AF"],
    "antidepressant": ["N06A"], "ssri": ["N06AB"], "loop diuretic": ["C03CA"], "diuretic": ["C03"],
    "inhaled corticosteroid": ["R03AK"], "bronchodilator": ["R03"],
}

REGIONS = ["Burgenland", "Kärnten", "Niederösterreich", "Oberösterreich", "Salzburg", "Steiermark",
           "Tirol", "Vorarlberg", "Wien"]

REF_PRONOUNS = re.compile(r"\b(of them|of these|of those|among them|their|they|these|those|that share|this share|the share)\b", re.I)


@dataclass
class Concept:
    name: str
    criteria: list[Criterion] = field(default_factory=list)
    kind: str = "criteria"          # criteria | observation | formula | encounter
    obs_codes: list[str] = field(default_factory=list)
    obs_select: str = "latest"
    formula: tuple[str, str] | None = None
    source: str = ""


@dataclass
class ParseContext:
    store: DataStore | None
    concepts: dict[str, Concept] = field(default_factory=dict)
    age_bins: list[tuple[int, int | None]] = field(default_factory=list)
    active_rule: bool = False
    encounter_dates: tuple[str | None, str | None] = (None, None)
    count_stays: bool = False
    mapping: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    _code_lists: dict[str, list[dict]] = field(default_factory=dict)

    def code_list(self, table: str) -> list[dict]:
        if self.store is None:
            return []
        if table not in self._code_lists:
            self._code_lists[table] = self.store.code_list(table)
        return self._code_lists[table]


# ============================================================ helpers
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("–", "-").replace("—", "-")).strip()


def variants(name: str) -> list[str]:
    n = name.lower().strip()
    out = {n}
    if n.endswith("y") and not n.endswith("ay"):
        out.add(n[:-1] + "ies")
    out |= {n + "s", n + "es"}
    if n.endswith("s"):
        out.add(n[:-1])
    if n == "woman":
        out.add("women")
    if n == "women":
        out.add("woman")
    return sorted(out, key=len, reverse=True)


def codes_in(text: str, pattern: str) -> list[str]:
    return [c.upper() for c in re.findall(rf"\b({pattern})\b", text)]


def _age(text: str) -> list[Criterion]:
    t = text.lower()
    m = re.search(r"aged?\s+(\d+)\s*(?:years?)?\s*(?:or|and)\s+(?:older|over|above|more)", t) or \
        re.search(r"aged?\s+(\d+)\+", t) or re.search(r"(?:at least|minimum)\s+(\d+)\s+years", t) or \
        re.search(r"(\d+)\s+years?\s+(?:or|and)\s+(?:older|over)", t)
    if m:
        return [Criterion(type="age", op=">=", value=int(m.group(1)), term=m.group(0))]
    m = re.search(r"aged?\s+(?:under|below|less than|younger than)\s+(\d+)", t)
    if m:
        return [Criterion(type="age", op="<", value=int(m.group(1)), term=m.group(0))]
    m = re.search(r"aged?\s+(\d+)\s*(?:-|to)\s*(\d+)", t)
    if m:
        return [Criterion(type="age", op=">=", value=int(m.group(1)), value_max=int(m.group(2)), term=m.group(0))]
    return []


def _threshold(text: str) -> tuple[str, float] | None:
    t = text.lower()
    pats = [(r"(?:>=|≥|at least|or more|or higher|or above)\s*(\d+(?:\.\d+)?)", ">="),
            (r"(\d+(?:\.\d+)?)\s*(?:%|\S*)?\s*or (?:more|higher|above)", ">="),
            (r"(?:<=|≤|at most|or less|or lower|or below)\s*(\d+(?:\.\d+)?)", "<="),
            (r"(?:>|above|over|greater than|more than|higher than)\s*(\d+(?:\.\d+)?)", ">"),
            (r"(?:<|below|under|less than|lower than)\s*(\d+(?:\.\d+)?)", "<")]
    for p, op in pats:
        m = re.search(p, t)
        if m:
            return op, float(m.group(1))
    return None


def _dates_in(text: str) -> tuple[str | None, str | None]:
    t = text.lower()
    m = re.search(r"\b(?:in|during)\s+(20\d{2})\b", t)
    if m:
        return f"{m.group(1)}-01-01", f"{m.group(1)}-12-31"
    m = re.search(r"between\s+(20\d{2})\s+and\s+(20\d{2})", t) or re.search(r"from\s+(20\d{2})\s+to\s+(20\d{2})", t)
    if m:
        return f"{m.group(1)}-01-01", f"{m.group(2)}-12-31"
    m = re.search(r"(?:since|from|after)\s+(20\d{2})", t)
    if m:
        return f"{m.group(1)}-01-01", None
    return None, None


# ============================================================ definitions
def split_definitions(defs: list[str]) -> list[str]:
    out = []
    for d in defs:
        parts = re.split(r";\s+(?=[A-Za-z0-9][\w\s\-/']{0,40}\s=\s)", norm(d))
        out.extend(p.strip() for p in parts if p.strip())
    return out


def parse_definition(ctx: ParseContext, d: str) -> None:
    low = d.lower()
    if re.match(r"report\b", low):
        return
    if re.search(r"age (bands?|groups?)", low) and re.search(r"\d+\s*-\s*\d+|\d+\+", low) and "=" not in d.split(":")[0]:
        ctx.age_bins = parse_bins(d.split(":", 1)[-1])
        return
    if re.search(r"\bmedication is active\b|\bactive (on|if|means)\b|\bis active\b", low) and "=" not in d.split(" if ")[0]:
        ctx.active_rule = True
        return
    if re.match(r"(count|counting)\b", low) and re.search(r"\bstays?\b|\bencounters?\b|\bvisits?\b", low):
        ctx.count_stays = True
        f, t = _dates_in(re.sub(r"start_date is", "", low))
        if f or t:
            ctx.encounter_dates = (f, t)
        return
    m = re.match(r"use the (latest|first|highest|lowest|mean|average|most recent)\s+(.+?)\s*\((?:loinc\s*)?(" + LOINC + r")\)", low)
    if m:
        sel = {"latest": "latest", "most recent": "latest", "first": "first", "highest": "max",
               "lowest": "min", "mean": "mean", "average": "mean"}[m.group(1)]
        name = m.group(2).strip()
        ctx.concepts[name] = Concept(name, kind="observation", obs_codes=[m.group(3)], obs_select=sel, source=d)
        ctx.mapping.append({"term": name, "system": "LOINC", "codes": [m.group(3)], "how": "definition"})
        return
    if " = " not in d:
        ctx.notes.append(f"Not interpreted: {d}")
        return
    name, body = d.split(" = ", 1)
    name = name.strip().strip("'\"").lower()
    concept = parse_body(ctx, name, body.strip().rstrip("."), d)
    ctx.concepts[name] = concept


def parse_bins(text: str) -> list[tuple[int, int | None]]:
    bins = []
    for lo, hi, plus in re.findall(r"(\d+)\s*(?:-|to)\s*(\d+)|(\d+)\s*\+", text):
        if plus:
            bins.append((int(plus), None))
        else:
            bins.append((int(lo), int(hi)))
    return bins


def parse_body(ctx: ParseContext, name: str, body: str, src: str) -> Concept:
    low = body.lower()
    # percentage / ratio formula: "A / B × 100"
    if "/" in body and re.search(r"[x×*]\s*100|per ?cent|%", low):
        num, den = body.split("/", 1)
        den = re.split(r"[x×*]\s*100", den)[0]
        return Concept(name, kind="formula", formula=(num.strip(), den.strip().rstrip(",")), source=src)

    crit: list[Criterion] = []
    if re.search(r"icd-?10|condition|diagnos", low) and codes_in(body, ICD) and "primary_icd10" not in low \
            and "main diagnosis" not in low:
        codes = codes_in(body, ICD)
        crit.append(Criterion(type="condition", codes=codes, term=name))
        ctx.mapping.append({"term": name, "system": "ICD-10", "codes": codes, "how": "definition"})
    elif re.search(r"\batc\b", low) and codes_in(body, ATC):
        codes = codes_in(body, ATC)
        crit.append(Criterion(type="medication", codes=codes, term=name))
        ctx.mapping.append({"term": name, "system": "ATC", "codes": codes, "how": "definition"})
    if re.search(r"\bloinc\b", low) and codes_in(body, LOINC):
        codes = codes_in(body, LOINC)
        th = _threshold(re.sub(LOINC, "", body))
        if th:
            sel = "latest" if re.search(r"latest|most recent|last", low) else "any"
            crit.append(Criterion(type="observation", codes=codes, term=name, op=th[0], value=th[1],
                                  observation_select=sel))
        elif not re.search(r"\bwho\b|\bwith\b|\bhave\b", low):
            ctx.mapping.append({"term": name, "system": "LOINC", "codes": codes, "how": "definition"})
            return Concept(name, kind="observation", obs_codes=codes, source=src)
        ctx.mapping.append({"term": name, "system": "LOINC", "codes": codes, "how": "definition"})
    if re.search(r"\bsex\b|\bgender\b", low):
        sx = re.search(r"'(\w+)'|\"(\w+)\"|\b(female|male)\b", low)
        if sx:
            crit.append(Criterion(type="sex", value=next(g for g in sx.groups() if g), term=name))
    if re.search(r"encounter|stay|visit|admission", low) and re.search(r"type|inpatient|outpatient|emergency", low):
        t = re.search(r"'(inpatient|outpatient|emergency)'|\b(inpatient|outpatient|emergency)\b", low)
        etype = next(g for g in t.groups() if g) if t else None
        pc = codes_in(body, ICD) if re.search(r"primary_icd10|main diagnosis|primary diagnosis", low) else []
        f, to = _dates_in(low)
        crit.append(Criterion(type="encounter", encounter_type=etype, inpatient=True if etype == "inpatient" else None,
                              primary_icd10=pc, term=name, date_from=f, date_to=to))
        if pc:
            ctx.mapping.append({"term": name, "system": "ICD-10 (primary_icd10)", "codes": pc, "how": "definition"})
        return Concept(name, crit, kind="encounter", source=src)
    if re.search(r"primary_icd10|main diagnosis|primary diagnosis", low) and codes_in(body, ICD):
        pc = codes_in(body, ICD)
        crit.append(Criterion(type="encounter", inpatient=True, encounter_type="inpatient", primary_icd10=pc, term=name))
        ctx.mapping.append({"term": name, "system": "ICD-10 (primary_icd10)", "codes": pc, "how": "definition"})
        return Concept(name, crit, kind="encounter", source=src)
    if re.search(r"\baged?\b|\byears\b", low):
        crit += _age(low)
    for r in REGIONS:
        if r.lower() in low:
            crit.append(Criterion(type="region", value=r, term=name))
    if ctx.store is not None:
        for dh in ctx.store.data_holders():
            if dh.lower() in low:
                crit.append(Criterion(type="data_holder", value=dh, term=name))
    if crit and not re.search(r"\bwho\b|\bwith\b", low):
        return Concept(name, crit, source=src)
    # composite: "adults with type 2 diabetes who have at least one HbA1c value (LOINC 4548-4)"
    extra = phrase_criteria(ctx, body)
    merged = _merge(crit, extra)
    return Concept(name, merged, source=src)


def _merge(a: list[Criterion], b: list[Criterion]) -> list[Criterion]:
    out = list(a)
    keys = {_key(c) for c in a}
    for c in b:
        if _key(c) not in keys:
            out.append(c)
            keys.add(_key(c))
    return out


def _key(c: Criterion) -> tuple:
    return (c.type, tuple(c.codes), c.op, str(c.value), c.value_max, c.negate, c.encounter_type,
            tuple(c.primary_icd10), c.active_on, c.date_from, c.date_to)


# ============================================================ phrases
def _concept_index(ctx: ParseContext) -> list[tuple[str, str]]:
    """(surface form, concept name), longest first."""
    idx = []
    for name in ctx.concepts:
        for v in variants(name):
            idx.append((v, name))
    return sorted(idx, key=lambda x: len(x[0]), reverse=True)


def phrase_criteria(ctx: ParseContext, phrase: str, *, with_obs_value: bool = True) -> list[Criterion]:
    """All criteria a phrase names: defined concepts, population nouns, synonyms, codes in the data."""
    text = " " + norm(phrase).lower() + " "
    text = re.sub(r"\(loinc [^)]*\)", " ", text)
    crit: list[Criterion] = []
    consumed = [False] * len(text)

    def take(start: int, end: int) -> bool:
        if any(consumed[start:end]):
            return False
        for i in range(start, end):
            consumed[i] = True
        return True

    def negated(start: int) -> bool:
        before = text[max(0, start - 25):start]
        return bool(re.search(r"\b(no|without|not|never|none|non)\b[\w\s\-]{0,14}$", before))

    def active(start: int, end: int) -> bool:
        around = text[max(0, start - 20):end + 25]
        return bool(re.search(r"\bactive\b|\bcurrent(ly)?\b|\bstill taking\b|\bon 31 december", around)) or False

    for surface, name in _concept_index(ctx):
        for m in re.finditer(rf"(?<![\w-]){re.escape(surface)}(?![\w-])", text):
            if not take(m.start(), m.end()):
                continue
            c = ctx.concepts[name]
            if c.kind == "observation":
                if with_obs_value and re.search(r"\b(with|have|has|having)\b[\w\s]{0,20}$", text[:m.start()]) or \
                        re.search(r"^\s*(value|values|measurement|result)", text[m.end():]):
                    crit.append(Criterion(type="observation", codes=c.obs_codes, term=name, negate=negated(m.start())))
                continue
            if c.kind == "formula":
                continue
            neg = negated(m.start())
            for cr in c.criteria:
                cr = cr.model_copy()
                if cr.type == "medication" and active(m.start(), m.end()):
                    cr.active_on = settings.reference_date
                if neg:
                    cr.negate = not cr.negate
                crit.append(cr)

    for noun, crs in POP_NOUNS.items():
        for m in re.finditer(rf"\b{noun}\b", text):
            if take(m.start(), m.end()):
                crit.extend(c.model_copy() for c in crs if all(_key(c) != _key(x) for x in crit))

    crit += _age(text) if not any(c.type == "age" and c.term and "aged" in c.term for c in crit) else []
    for r in REGIONS:
        m = re.search(rf"\b(?:in|from|living in|resident in)\s+{r.lower()}\b", text)
        if m and take(m.start(), m.end()):
            crit.append(Criterion(type="region", value=r, term=r))
    if ctx.store is not None:
        for dh in ctx.store.data_holders():
            m = re.search(rf"\b(?:at|in|from|of|treated at)\s+{re.escape(dh.lower())}\b", text)
            if m and take(m.start(), m.end()):
                crit.append(Criterion(type="data_holder", value=dh, term=dh))

    # undefined clinical terms -> synonyms / code descriptions in the data
    crit += _lookup_terms(ctx, text, consumed, negated, active)
    return _merge([], crit)


def _lookup_terms(ctx, text, consumed, negated, active) -> list[Criterion]:
    out = []
    tables = (("condition", CONDITION_SYNONYMS, "conditions", "ICD-10"),
              ("medication", MEDICATION_SYNONYMS, "medications", "ATC"))
    for ctype, syn, table, system in tables:
        for term in sorted(syn, key=len, reverse=True):
            for v in variants(term):
                for m in re.finditer(rf"(?<![\w-]){re.escape(v)}(?![\w-])", text):
                    if any(consumed[m.start():m.end()]):
                        continue
                    for i in range(m.start(), m.end()):
                        consumed[i] = True
                    codes = syn[term]
                    found = [r["code"] for r in ctx.code_list(table) if any(r["code"].startswith(c) for c in codes)]
                    c = Criterion(type=ctype, codes=codes, term=term, negate=negated(m.start()))
                    if ctype == "medication" and active(m.start(), m.end()):
                        c.active_on = settings.reference_date
                    out.append(c)
                    ctx.mapping.append({"term": term, "system": system, "codes": codes, "how": "synonym list",
                                        "found_in_data": found})
    for term, codes in OBSERVATION_SYNONYMS.items():
        for m in re.finditer(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text):
            if any(consumed[m.start():m.end()]):
                continue
            if re.search(r"\b(with|have|has|having)\b[\w\s]{0,20}$", text[:m.start()]):
                for i in range(m.start(), m.end()):
                    consumed[i] = True
                out.append(Criterion(type="observation", codes=codes, term=term, negate=negated(m.start())))
                ctx.mapping.append({"term": term, "system": "LOINC", "codes": codes, "how": "synonym list"})
    # "with <words>" that match a code description in the data, e.g. "with heart failure"
    for m in re.finditer(r"\bwith (?:an? )?([a-z][a-z \-]{3,40}?)(?=,| and | who | by | in | per |\?|\.| $)", text):
        if any(consumed[m.start(1):m.end(1)]):
            continue
        words = m.group(1).strip()
        for table, ctype, system in (("conditions", "condition", "ICD-10"), ("medications", "medication", "ATC")):
            hits = [r for r in ctx.code_list(table) if r["description"] and words in r["description"].lower()]
            if hits:
                codes = sorted({h["code"] for h in hits})
                out.append(Criterion(type=ctype, codes=codes, term=words, negate=negated(m.start())))
                ctx.mapping.append({"term": words, "system": system, "codes": codes, "how": "code description in data"})
                for i in range(m.start(1), m.end(1)):
                    consumed[i] = True
                break
    return out


# ============================================================ question & report
def subject_of(ctx: ParseContext, question: str) -> list[Criterion]:
    """Who the question is about: population nouns and 'with ...' qualifiers, plus 'aged ...'."""
    q = norm(question).lower()
    crit: list[Criterion] = []
    # qualifier clauses: "patients with atrial fibrillation aged 65 and over", "women with breast cancer"
    for m in re.finditer(r"\b(?:patients|adults|women|men|people|persons|children|those)\b"
                         r"((?:\s+(?:with|aged|who have|who has|living in|from|in|treated at)\b[^,?;]*?)+)"
                         r"(?=,|\?|;| by | per | how | what | and what| in each|$)", q):
        crit = _merge(crit, phrase_criteria(ctx, m.group(0), with_obs_value=False))
    for noun, crs in POP_NOUNS.items():
        if re.search(rf"\b{noun}\b", q):
            crit = _merge(crit, [c.model_copy() for c in crs])
    crit = _merge(crit, _age(q))
    # outcomes (drugs, measurements) are not part of the subject
    return [c for c in crit if c.type not in ("medication", "observation")]


GROUP_WORDS = [
    (r"\b(?:age ?bands?|age ?groups?|bands?|age)\b", "age_group"),
    (r"\b(?:regions?|federal states?|states?|bundesl[äa]nder)\b", "region"),
    (r"\b(?:hospitals?|data[ _]holders?|klinik\w*|sites?|facilit(?:y|ies))\b", "data_holder"),
    (r"\b(?:sex|gender)\b", "sex"),
    (r"\b(?:years?|calendar years?)\b", "year"),
]


def parse_groups(ctx: ParseContext, text: str) -> list[GroupBy]:
    groups: list[GroupBy] = []
    low = text.lower()
    positions = []
    for pat, dim in GROUP_WORDS:
        m = re.search(pat, low)
        if m:
            positions.append((m.start(), dim))
    for _, dim in sorted(positions):
        if any(g.dimension == dim for g in groups):
            continue
        if dim == "age_group":
            bins = ctx.age_bins or _default_bins(low)
            groups.append(GroupBy(dimension="age_group", bins=bins))
        else:
            groups.append(GroupBy(dimension=dim))
    return groups


def _default_bins(text: str) -> list[tuple[int, int | None]]:
    m = re.search(r"(\d+)-year", text)
    step = int(m.group(1)) if m else 10
    return [(lo, lo + step - 1) for lo in range(0, 90, step)] + [(90, None)]


def split_items(report: str) -> list[str]:
    report = re.sub(r",?\s*(?:with |rounded to |to )?(?:one|1|two|2) decimals?(?: place)?\.?$", "", report.strip().rstrip("."))
    report = re.sub(r",?\s*(?:with |rounded to |to )?(?:one|1|two|2) decimals?(?: place)?(?=,|$)", "", report)
    items = []
    for part in [p.strip() for p in report.split(",") if p.strip()]:
        sub = re.split(r"\s+and\s+(?=%|(?:the|their|that|this|its|mean|average|median|share|percentage|proportion|"
                       r"how many|number|count|patients|adults|women|men|people|persons|children|stays|prevalence|rate)\b)",
                       part)
        items += [s.strip() for s in sub if s.strip()]
    return items


@dataclass
class _Built:
    metric: Metric
    base: int | None  # index of the metric this one is a subset of


def build_metric(ctx: ParseContext, item: str, idx: int, subject: list[Criterion], built: list[_Built],
                 groups: list[GroupBy]) -> _Built:
    low = item.lower().strip()
    mid = slug(item, idx)
    ref = REF_PRONOUNS.search(low)
    prev = built[-1] if built else None

    # named formula ("the prevalence")
    for name, c in ctx.concepts.items():
        if c.kind == "formula" and any(re.search(rf"\b{re.escape(v)}\b", low) for v in variants(name)):
            num = _merge(subject, phrase_criteria(ctx, c.formula[0]))
            den = _merge(subject, phrase_criteria(ctx, c.formula[1]))
            return _Built(Metric(id=mid, label=item, kind="percentage", criteria=num, denominator=den,
                                 source_text=c.source), None)

    is_pct = bool(re.match(r"^(%|percent|percentage|share|proportion|rate|the share|that share|this share|its share)", low)) \
        or bool(re.search(r"\bin %|\bshare\b|\bpercentage\b|\bproportion\b", low))
    is_mean = bool(re.search(r"\b(mean|average|avg)\b", low))

    if is_mean:
        obs = _observation_in(ctx, low)
        if ref and prev:
            base_crit = prev.metric.criteria
        else:
            base_crit = _merge(subject, phrase_criteria(ctx, re.sub(r"\b(mean|average|avg)\b.*", "", low)))
        if obs:
            v = ValueSpec(source="observation", codes=obs[0], select=obs[1])
        elif "length of stay" in low or "los" in low.split():
            v = ValueSpec(source="length_of_stay")
        elif re.search(r"\bage\b", low):
            v = ValueSpec(source="age")
        else:
            v = ValueSpec(source="encounter_count")
        unit = "encounters" if v.source == "length_of_stay" else "patients"
        return _Built(Metric(id=mid, label=item, kind="mean", unit=unit, criteria=base_crit, value=v), built.index(prev) if ref and prev else None)

    if is_pct:
        if re.match(r"^(that|this|the|its) share", low) and prev:
            base_i = prev.base if prev.base is not None else 0
            return _Built(Metric(id=mid, label=item, kind="percentage", criteria=prev.metric.criteria,
                                 denominator=built[base_i].metric.criteria), prev.base)
        first = next((b for b in built if b.metric.kind == "count"), None)
        base_crit = first.metric.criteria if first else subject
        extra = phrase_criteria(ctx, re.sub(r"^(%|percent(age)?|share|proportion|rate)\s*(of\s+\w+\s+)?", "", low))
        return _Built(Metric(id=mid, label=item, kind="percentage", criteria=_merge(base_crit, extra),
                             denominator=base_crit), built.index(first) if first else None)

    # count
    stays = ctx.count_stays or bool(re.search(r"\bstays?\b|\bencounters?\b|\bvisits?\b|\badmissions?\b", low))
    if ref and prev and re.search(r"\b(of them|of these|of those|among them)\b", low):
        crit = _merge(prev.metric.criteria, phrase_criteria(ctx, low))
        return _Built(Metric(id=mid, label=item, kind="count", unit=prev.metric.unit, criteria=crit), built.index(prev))
    crit = _merge(subject, phrase_criteria(ctx, low))
    if re.search(r"size of the cohort|cohort size|the cohort", low) and "cohort" in ctx.concepts:
        crit = _merge(subject, ctx.concepts["cohort"].criteria)
    if stays and any(c.type == "encounter" for c in crit) or (stays and ctx.count_stays):
        enc = [c for c in crit if c.type == "encounter"] or [Criterion(type="encounter", term="stay")]
        f, t = ctx.encounter_dates
        enc = [e.model_copy(update={"date_from": e.date_from or f, "date_to": e.date_to or t}) for e in enc]
        crit = [c for c in crit if c.type != "encounter"] + enc
        return _Built(Metric(id=mid, label=item, kind="count", unit="encounters", criteria=crit), None)
    return _Built(Metric(id=mid, label=item, kind="count", criteria=crit), None)


def _observation_in(ctx: ParseContext, low: str) -> tuple[list[str], str] | None:
    for name, c in sorted(ctx.concepts.items(), key=lambda x: -len(x[0])):
        if c.kind == "observation" and any(re.search(rf"(?<![\w-]){re.escape(v)}(?![\w-])", low) for v in variants(name)):
            return c.obs_codes, c.obs_select
    for term, codes in OBSERVATION_SYNONYMS.items():
        if re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", low):
            return codes, "latest"
    return None


def slug(item: str, idx: int) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_")
    s = re.sub(r"^(the|their|that|number_of|how_many_of_them_have|how_many)_", "", s)
    return (s[:48] or f"metric_{idx + 1}")


RECORD_TYPES = {"conditions": ["condition", "diagnos"], "medications": ["medication", "drug", "prescription"],
                "observations": ["observation", "measurement", "lab", "value", "hba1c", "bmi", "blood pressure", "egfr"],
                "encounters": ["encounter", "stay", "visit", "admission"]}


def record_types(ctx: ParseContext, text: str) -> tuple[list[str], list[str]]:
    """Record types an SPE should contain, and observation codes if the request limits them."""
    low = text.lower()
    types = [t for t, words in RECORD_TYPES.items() if any(w in low for w in words)]
    obs_codes = []
    if "observations" in types:
        for name, c in ctx.concepts.items():
            if c.kind == "observation" and name in low:
                obs_codes += c.obs_codes
        for term, codes in OBSERVATION_SYNONYMS.items():
            if re.search(rf"\b{re.escape(term)}\b", low):
                obs_codes += codes
    return types or ["conditions", "medications", "observations", "encounters"], sorted(set(obs_codes))


# ============================================================ main
def parse_request(request: dict, store: DataStore | None) -> Spec:
    ctx = ParseContext(store)
    defs = split_definitions(list(request.get("definitions") or []))
    report_lines = [d for d in defs if re.match(r"report\b", d.lower())]
    for d in defs:
        parse_definition(ctx, d)
    question = norm(str(request.get("question") or ""))

    subject = subject_of(ctx, question)
    report = report_lines[-1] if report_lines else ""
    head, _, items_text = report.partition(":")
    if not items_text:  # "Report the size of the cohort you would make available."
        items_text = re.sub(r"^report\s+", "", head, flags=re.I)
        head = ""
    groups = parse_groups(ctx, head) if head else []
    if not groups:
        m = re.search(r"\b(?:by|per|in each|for each|across)\b(.+)$", question.lower())
        groups = parse_groups(ctx, m.group(1)) if m else []

    built: list[_Built] = []
    for i, item in enumerate(split_items(items_text)):
        built.append(build_metric(ctx, item, i, subject, built, groups))
    metrics = [b.metric for b in built]
    seen = set()
    for m in metrics:  # unique ids
        while m.id in seen:
            m.id += "_2"
        seen.add(m.id)

    population = ctx.concepts["cohort"].criteria if "cohort" in ctx.concepts else (
        metrics[0].criteria if metrics else subject)
    rtypes, obs_codes = record_types(ctx, question)
    notes = ctx.notes + ([f"SPE observations limited to LOINC {', '.join(obs_codes)}"] if obs_codes else [])
    return Spec(request_id=str(request.get("id") or request.get("request_id") or "NEW"),
                population=population, group_by=groups, metrics=metrics, record_types=rtypes,
                spe_observation_codes=obs_codes, notes=notes, term_mapping=_dedupe(ctx.mapping))


def _dedupe(rows: list[dict]) -> list[dict]:
    out, seen = [], set()
    for r in rows:
        k = (r["term"], r["system"], tuple(r["codes"]))
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out

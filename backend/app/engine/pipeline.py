"""End to end: request JSON -> decision -> statistics or SPE -> stored result + audit."""
from __future__ import annotations

import json
import time

from .. import state
from ..datastore import DataStore
from . import permit, spe
from .decision import APPROVE_SPE, APPROVE_STATISTICAL, REJECT, decide
from .parser import parse_request
from .query import answer_table, run_spec


def evaluate(request: dict, store: DataStore, user: dict | None = None, persist: bool = True) -> dict:
    t0 = time.perf_counter()
    rid = str(request.get("id") or request.get("request_id") or f"NEW-{int(time.time())}")
    request = {**request, "id": rid}
    d = decide(request)
    spec = parse_request(request, store) if d.decision != REJECT else None
    result: dict = {
        "request_id": rid,
        "applicant": request.get("applicant"),
        "purpose": request.get("purpose"),
        "requested_as": request.get("requested_as"),
        **d.as_dict(),
        "permit_checklist": permit.checklist(request, d),
        "opted_out_excluded": store.opted_out_count(),
        "small_cell_rule": "Counts below 10 are shown as <10; percentages and means from fewer than 10 patients are suppressed.",
    }
    if d.decision == APPROVE_STATISTICAL and spec is not None:
        metrics = run_spec(store, spec)
        result["answer"] = answer_table(spec, metrics)
        result["statistics"] = [{k: v for k, v in m.items() if k not in ("sql", "params")} for m in metrics]
        result["staff"] = {"spec": spec.model_dump(), "term_mapping": spec.term_mapping,
                           "sql": [{"metric": m["id"], "sql": m.get("sql"), "params": m.get("params")} for m in metrics]}
    elif d.decision == APPROVE_SPE and spec is not None:
        info = spe.create(store, spec, spec.spe_observation_codes)
        result["answer"] = {"cohort_size": info["patient_count"]}
        result["spe"] = info
        result["staff"] = {"spec": spec.model_dump(), "term_mapping": spec.term_mapping}
    else:
        result["answer"] = None
    result["seconds"] = round(time.perf_counter() - t0, 3)

    if persist:
        with state.tx() as c:
            now = state.now()
            c.execute("""INSERT INTO decisions (request_id, submitted_by, applicant, purpose, requested_as, decision,
                         articles, status, result, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(request_id) DO UPDATE SET decision=excluded.decision, articles=excluded.articles,
                         result=excluded.result, status='automatic', updated_at=excluded.updated_at""",
                      (rid, (user or {}).get("id"), json.dumps(request.get("applicant"), ensure_ascii=False),
                       request.get("purpose"), request.get("requested_as"), d.decision, json.dumps(d.articles),
                       "automatic", json.dumps(result, ensure_ascii=False, default=str), now, now))
            if d.decision != REJECT:
                for dh in store.data_holders():
                    c.execute("INSERT OR IGNORE INTO provisions (request_id, data_holder, status) VALUES (?,?,?)",
                              (rid, dh, "requested"))
            state.audit(user, "secondary", "evaluate_request", request_id=rid, outcome=d.decision,
                        details={"articles": d.articles, "seconds": result["seconds"],
                                 "spe_patients": result.get("spe", {}).get("patient_count")}, conn=c)
    return result


def applicant_view(result: dict) -> dict:
    """What the applicant sees: decision, reasons, numbers. No SQL, no spec, no SPE path."""
    keep = ("request_id", "applicant", "purpose", "requested_as", "decision", "articles", "article_titles",
            "matched_step", "explanation", "prohibited_purposes", "answer", "statistics", "small_cell_rule",
            "opted_out_excluded", "seconds")
    out = {k: result.get(k) for k in keep if k in result}
    if result.get("spe"):
        s = result["spe"]
        out["spe"] = {"id": s["id"], "patient_count": s["patient_count"], "record_types": s["record_types"],
                      "download": "blocked"}
    return out

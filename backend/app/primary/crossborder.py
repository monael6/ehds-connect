"""Cross-border access to the Patient Summary (MyHealth@EU, simulated).

The rules run only here in the backend; the UI shows the result in plain language.
  1 requester is not an authorised health professional          -> DENY
  2 national request by the treating hospital                    -> ALLOW
  3 cross-border, identity checked and cross-border consent      -> ALLOW_CROSS_BORDER
  4 cross-border emergency with a reason                         -> ALLOW_EMERGENCY (emergency data only)
  5 anything else                                                -> DENY with reason
"""
from __future__ import annotations

import json

from .. import state
from ..auth import FOREIGN_DOCTOR, HOSPITAL
from ..datastore import DataStore
from . import summary

SECTIONS = {"problems", "medications", "allergies", "results"}


def get_consent(pid: str) -> dict:
    row = state.one("SELECT * FROM consents WHERE patient_id = ?", (pid,))
    if not row:
        return {"patient_id": pid, "cross_border": False, "hidden_sections": [], "since": None}
    row["cross_border"] = bool(row["cross_border"])
    row["hidden_sections"] = json.loads(row["hidden_sections"])
    return row


def set_consent(pid: str, allow: bool, hidden: list[str], user: dict) -> dict:
    hidden = sorted(set(hidden) & SECTIONS)
    old = get_consent(pid)
    since = old["since"] if (allow and old["cross_border"]) else (state.now() if allow else None)
    with state.tx() as c:
        c.execute("""INSERT INTO consents (patient_id, cross_border, hidden_sections, since, updated_at) VALUES (?,?,?,?,?)
                     ON CONFLICT(patient_id) DO UPDATE SET cross_border=excluded.cross_border,
                     hidden_sections=excluded.hidden_sections, since=excluded.since, updated_at=excluded.updated_at""",
                  (pid, int(allow), json.dumps(hidden), since, state.now()))
        state.audit(user, "portal", "consent_cross_border_" + ("granted" if allow else "withdrawn"), patient_id=pid,
                    outcome="stored", details={"hidden_sections": hidden}, conn=c)
    return get_consent(pid)


def decide_access(user: dict, pid: str, *, identity_checked: bool, patient_agrees: bool,
                  emergency: bool, reason: str | None, consent: dict, patient_holder: str | None) -> dict:
    if user["role"] not in (HOSPITAL, FOREIGN_DOCTOR):
        return {"decision": "DENY", "rule": 1, "text": "Access not possible – you are not an authorised health professional."}
    if user["role"] == HOSPITAL:
        return {"decision": "ALLOW", "rule": 2, "text": "Access allowed – treating hospital in Austria."}
    if emergency:
        if reason and reason.strip():
            return {"decision": "ALLOW_EMERGENCY", "rule": 4,
                    "text": "Emergency access – logged, the patient will be informed. Only emergency information is shown."}
        return {"decision": "DENY", "rule": 5, "text": "Emergency access needs a reason."}
    if not identity_checked:
        return {"decision": "DENY", "rule": 5, "text": "Access not possible – identity not checked against an ID document."}
    if not consent["cross_border"]:
        return {"decision": "DENY", "rule": 5, "text": "Access not possible – no consent from the patient for cross-border access."}
    if not patient_agrees:
        return {"decision": "DENY", "rule": 5, "text": "Access not possible – the patient has not agreed on site."}
    return {"decision": "ALLOW_CROSS_BORDER", "rule": 3,
            "text": f"Access allowed – the patient allowed cross-border access on {str(consent['since'])[:10]}."}


def request_summary(store: DataStore, user: dict, pid: str, *, identity: dict | None = None, identity_checked: bool = False,
                    patient_agrees: bool = False, emergency: bool = False, reason: str | None = None,
                    lang: str = "it") -> dict:
    consent = get_consent(pid)
    p = summary.patient(store, pid)
    if not p:
        return {"decision": "DENY", "rule": 5, "text": "Patient not found (NCPeH Austria)."}
    d = decide_access(user, pid, identity_checked=identity_checked, patient_agrees=patient_agrees, emergency=emergency,
                      reason=reason, consent=consent, patient_holder=p["data_holder"])
    route = [{"node": "Ospedale di Firenze (simulated)", "check": "Doctor signed in to the Italian hospital system"},
             {"node": "NCPeH Italy", "check": "Doctor authorised, vouched by NCPeH Italy"},
             {"node": "NCPeH Austria", "check": "Patient found" if p else "Patient not found"},
             {"node": "EHDS Connect (Austria)", "check": d["text"]}]
    body = None
    if d["decision"] in ("ALLOW", "ALLOW_CROSS_BORDER"):
        visible = SECTIONS - set(consent["hidden_sections"]) if d["decision"] == "ALLOW_CROSS_BORDER" else SECTIONS
        body = summary.build(store, pid, lang, visible)
    elif d["decision"] == "ALLOW_EMERGENCY":
        full = summary.build(store, pid, lang, set())
        body = {k: full[k] for k in ("patient", "language", "headings", "emergency", "generated_from")}
    sections = sorted(k for k in SECTIONS if body and k in body)
    state.audit(user, "cross_border", "patient_summary_access", patient_id=pid, outcome=d["decision"],
                details={"rule": d["rule"], "emergency": emergency, "reason": reason, "sections": sections,
                         "identity_document": (identity or {}).get("document_type"), "country": user.get("organisation"),
                         "language": lang})
    return {**d, "route": route, "summary": body, "consent_since": consent["since"],
            "note": "AI support (e.g. spoken translation): planned"}


def accesses(pid: str) -> list[dict]:
    rows = state.audit_rows(patient_id=pid, limit=200)
    out = []
    for r in rows:
        if r["action"] in ("patient_summary_access", "letter_sent", "letter_signed"):
            out.append({"when": r["ts"], "who": r["user_name"], "organisation": r["organisation"], "role": r["role"],
                        "what": r["action"], "outcome": r["outcome"], "sections": r["details"].get("sections"),
                        "emergency": r["details"].get("emergency", False)})
    return out

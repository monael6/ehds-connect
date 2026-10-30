"""Public information: dataset catalogue (HealthDCAT-AP style), register of approved uses,
and facilities whose data is not yet in the catalogue. Contains no patient data;
patient numbers are rounded to hundreds."""
from __future__ import annotations

import json

from . import state
from .datastore import DataStore

FACILITIES_NOT_REGISTERED = [
    {"name": "Rehabilitation clinics (e.g. Reha-Zentrum Bad Hofgastein)", "type": "Rehabilitation clinic",
     "likely_data": ["functional assessments", "therapy sessions", "discharge reports"], "status": "not yet registered"},
    {"name": "GP network Oberösterreich", "type": "Primary care network",
     "likely_data": ["chronic disease management (diabetes, hypertension)", "prescriptions", "vaccinations"],
     "status": "not yet registered"},
    {"name": "Nursing home group Steiermark", "type": "Long-term care",
     "likely_data": ["care levels", "falls", "pressure ulcers", "medication lists"], "status": "not yet registered"},
    {"name": "Laboratory chain (outpatient labs)", "type": "Laboratory",
     "likely_data": ["HbA1c", "eGFR", "lipids", "full blood count"], "status": "not yet registered"},
    {"name": "Austrian cancer registry extensions", "type": "Registry",
     "likely_data": ["tumour stage", "treatment lines", "survival"], "status": "not yet registered"},
]


def _r100(n: int) -> int:
    return int(round(n / 100.0) * 100)


def catalogue(store: DataStore) -> list[dict]:
    out = []
    for dh in store.data_holders():
        n = store.scalar("SELECT count(*) FROM kis.patients WHERE data_holder = ?", [dh]) or 0
        span = store.sql("SELECT min(start_date) a, max(end_date) b FROM kis.encounters WHERE data_holder = ?", [dh])[0]
        stored = state.one("SELECT * FROM catalogue_entries WHERE data_holder = ?", (dh,))
        custom = json.loads(stored["entry"]) if stored else {}
        entry = {
            "@context": "https://healthdcat-ap.eu/context.jsonld",
            "@type": "dcat:Dataset",
            "dct:title": custom.get("title") or f"Clinical records {dh} (synthetic)",
            "dct:description": custom.get("description") or
                f"Pseudonymised diagnoses (ICD-10), prescriptions (ATC), measurements (LOINC) and hospital visits from {dh}.",
            "dct:publisher": dh,
            "dct:temporal": {"start": str(span["a"]), "end": str(span["b"])},
            "healthdcatap:numberOfRecords": _r100(n),
            "healthdcatap:hasCodingSystem": ["ICD-10", "ATC", "LOINC"],
            "healthdcatap:healthCategory": ["EHR data", "medication", "laboratory results", "hospital stays"],
            "dct:accessRights": "Access via the Health Data Access Body (Art. 67-69)",
            "dct:modified": stored["updated_at"] if stored else None,
        }
        out.append({"data_holder": dh, "title": entry["dct:title"], "description": entry["dct:description"],
                    "patients_rounded": entry["healthdcatap:numberOfRecords"], "time_range": entry["dct:temporal"],
                    "record_types": ["conditions", "medications", "observations", "encounters"],
                    "code_systems": entry["healthdcatap:hasCodingSystem"], "jsonld": entry})
    return out


def update_entry(data_holder: str, title: str | None, description: str | None, user: dict) -> None:
    with state.tx() as c:
        c.execute("""INSERT INTO catalogue_entries (data_holder, entry, updated_by, updated_at) VALUES (?,?,?,?)
                     ON CONFLICT(data_holder) DO UPDATE SET entry=excluded.entry, updated_by=excluded.updated_by,
                     updated_at=excluded.updated_at""",
                  (data_holder, json.dumps({"title": title, "description": description}, ensure_ascii=False),
                   user["id"], state.now()))
        state.audit(user, "catalogue", "catalogue_entry_updated", outcome="saved", details={"data_holder": data_holder}, conn=c)


def register() -> list[dict]:
    """Public register of approved data uses: who, why, which type. No numbers."""
    rows = state.query("SELECT request_id, applicant, purpose, decision, status, created_at FROM decisions "
                       "WHERE decision != 'REJECT' ORDER BY created_at DESC")
    out = []
    for r in rows:
        applicant = json.loads(r["applicant"] or "null")
        org = applicant.get("organisation") if isinstance(applicant, dict) else applicant
        out.append({"date": r["created_at"][:10], "request_id": r["request_id"], "applicant_organisation": org,
                    "purpose": r["purpose"],
                    "type": "secure processing environment" if r["decision"] == "APPROVE_SPE" else "statistics",
                    "status": r["status"]})
    return out

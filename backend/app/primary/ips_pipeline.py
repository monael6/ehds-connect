"""IPS pipeline integration for the EHDS Connect backend.

Wraps the patientSummary LLM pipeline (pipeline/) and exposes it through
the connect-frontend auth/state system.  No Keycloak, no HAPI FHIR — the
pipeline outputs are stored as JSON in the local SQLite state DB.

Endpoints added to main.py:
    POST /api/patients/{pid}/ips-pipeline          run (or re-run) the pipeline
    GET  /api/patients/{pid}/ips-pipeline          latest result + status
    POST /api/patients/{pid}/ips-pipeline/approve  clinician approves the draft
"""
from __future__ import annotations

import json
import logging
import re
import sys
import uuid
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .. import state
from . import records

logger = logging.getLogger(__name__)

_NEGATED_RESULT_PATTERN = re.compile(
    r"\b(?:no|none|not|without|negative|absent|excluded|ruled\s+out|kein|keine|ohne|ausgeschlossen)\b",
    re.IGNORECASE,
)
_NEGATED_RESULT_DETAIL = "finding as described in the report; see the source document"


# ── Schema extension for state.sqlite ───────────────────────────────────────
# Added to state.SCHEMA at import time so connect() creates it automatically.
_IPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS ips_drafts (
    id         TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    intermediate TEXT,
    summary_md TEXT,
    fhir_bundle TEXT,
    eval_report TEXT,
    warnings    TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT
);
"""

# Monkey-patch the schema so it is created on first connect()
if "ips_drafts" not in state.SCHEMA:
    state.SCHEMA += _IPS_SCHEMA


# ── Helpers ──────────────────────────────────────────────────────────────────

# pipeline/ lives at the repo root, next to patients/; uvicorn runs from backend/.
_REPO_ROOT = str(records.PATIENTS_DIR.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _patients_dir() -> Path:
    """Directory containing per-patient document bundles (patients/P00X/)."""
    return records.PATIENTS_DIR


def _load_patient_docs(pid: str) -> tuple[dict, list[dict]]:
    """Load patient.json + documents.json from patients/<pid>/."""
    base = _patients_dir() / pid
    pf = base / "patient.json"
    df = base / "documents.json"
    if not pf.exists() or not df.exists():
        raise HTTPException(404, f"No document bundle found for patient '{pid}'. "
                            "Make sure patients/{pid}/patient.json and documents.json exist.")
    return (
        json.loads(pf.read_text(encoding="utf-8")),
        json.loads(df.read_text(encoding="utf-8")),
    )


def _latest_draft(pid: str) -> dict | None:
    return state.one(
        "SELECT * FROM ips_drafts WHERE patient_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (pid,),
    )


def _parse_draft(row: dict) -> dict:
    """Deserialize JSON fields and return a clean response dict."""
    out = dict(row)
    for key in ("intermediate", "fhir_bundle", "eval_report"):
        raw = out.get(key)
        out[key] = json.loads(raw) if raw else None
    out["warnings"] = json.loads(out.get("warnings") or "[]")
    return out


def _field(item: Any, name: str) -> Any:
    value = getattr(item, name, None)
    return value.value if hasattr(value, "value") else value


def _mapped(items: list[Any], fields: dict[str, str]) -> list[dict]:
    return [{target: _field(item, source) for target, source in fields.items()} for item in items]


def _normalize_ingredient(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).strip()


@lru_cache(maxsize=1)
def _atc_name_lookup() -> dict[str, str]:
    path = Path(__file__).resolve().parents[3] / "terminology" / "atc_lookup.json"
    try:
        codes = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("ATC lookup file unavailable: %s", path)
        return {}
    lookup: dict[str, str] = {}
    for code, name in codes.items():
        normalized = _normalize_ingredient(name)
        lookup[normalized] = code
        first_word = normalized.split()[0].strip("()[]{}.,;:") if normalized.split() else ""
        if first_word:
            lookup.setdefault(first_word, code)
    return lookup


_ATC_NAME_ALIASES = {
    "pantoprazole": "pantoprazol",
    "budesonide": "budesonid",
    "budesonide/formoterol": "budesonid/formoterol",
    "furosemide": "furosemid",
    "levothyroxine": "levothyroxin",
    "amlodipine": "amlodipin",
    "acetylsalicylic": "acetylsalicylsaure",
    "acetylsalicylic acid": "acetylsalicylsaure",
    "aspirin": "acetylsalicylsaure",
    "epinephrine": "epinephrin",
    "adrenaline": "epinephrin",
    "adrenalin": "epinephrin",
}


def _atc_for_ingredient(ingredient: str | None) -> str | None:
    if not ingredient:
        return None
    normalized = _normalize_ingredient(ingredient)
    candidates = [normalized]
    if normalized.split():
        candidates.append(normalized.split()[0].strip("()[]{}.,;:"))
    lookup = _atc_name_lookup()
    for candidate in candidates:
        candidate = _ATC_NAME_ALIASES.get(candidate, candidate)
        if candidate in lookup:
            return lookup[candidate]
    return None


def _mapped_medications(items: list[Any], fields: dict[str, str]) -> list[dict]:
    medications = _mapped(items, fields)
    for medication in medications:
        if not medication.get("atc"):
            medication["atc"] = _atc_for_ingredient(medication.get("active_ingredient"))
    return medications


def to_record(intermediate: Any) -> dict:
    """Convert a validated extraction into the record shape used by summary and letters."""
    included = intermediate.included
    active_items = intermediate.all_included_items()
    unverified = []
    for item in active_items:
        if not _field(item, "quote_verified"):
            text = next((_field(item, key) for key in ("text", "substance", "active_ingredient", "vaccine")
                         if _field(item, key)), "")
            unverified.append({"text": text, "sources": _field(item, "source_ids") or []})

    excluded = []
    for item in intermediate.excluded:
        reason = _field(item, "reason")
        text = _field(item, "text")
        excluded.append({
            "text": text,
            "reason": reason,
            "detail": _field(item, "detail"),
            "sources": _field(item, "source_ids") or [],
        })

    key_results = []
    for item in _mapped(included.key_results, {
        "text": "text", "value": "value", "date": "date", "sources": "source_ids",
    }):
        if any(_NEGATED_RESULT_PATTERN.search(str(item.get(field) or "")) for field in ("text", "value")):
            excluded.append({
                "text": item["text"],
                "reason": "negated",
                "detail": _NEGATED_RESULT_DETAIL,
                "sources": item.get("sources") or [],
            })
        else:
            key_results.append(item)

    return {
        "problems_active": _mapped(included.problems_active, {
            "text": "text", "icd10": "icd10_suggested", "snomed": "snomed_suggested",
            "onset": "onset", "sources": "source_ids",
        }),
        "past_history": _mapped(included.past_history, {
            "text": "text", "icd10": "icd10_suggested", "resolved": "resolved", "sources": "source_ids",
        }),
        "allergies_intolerances": _mapped(included.allergies_intolerances, {
            "substance": "substance", "reaction": "reaction", "criticality": "criticality",
            "verification": "verification", "sources": "source_ids",
        }),
        "medication_at_discharge": _mapped_medications(included.medication_at_discharge, {
            "active_ingredient": "active_ingredient", "atc": "atc_suggested", "dose": "dose",
            "status": "status", "sources": "source_ids",
        }),
        "medication_stopped_during_stay": _mapped_medications(included.medication_stopped, {
            "active_ingredient": "active_ingredient", "atc": "atc_suggested", "reason": "reason",
            "sources": "source_ids",
        }),
        "procedures": _mapped(included.procedures, {
            "text": "text", "date": "date", "sources": "source_ids",
        }),
        "medical_devices_implants": _mapped(included.medical_devices, {
            "text": "text", "since": "since", "sources": "source_ids",
        }),
        "immunizations": _mapped(included.immunizations, {
            "vaccine": "vaccine", "date": "date", "sources": "source_ids",
        }),
        "key_results": key_results,
        "must_not_include": excluded,
        "unverified": unverified,
    }


def record_with_latest_draft(rec: dict) -> tuple[dict, dict]:
    """Use the latest AI extraction when it has reached clinician review."""
    row = _latest_draft(rec["patient"]["patient_id"])
    if not row or row["status"] not in ("draft", "approved"):
        return rec, {"by": "reference"}

    draft = _parse_draft(row)
    from pipeline.models import ExtractionIntermediate

    intermediate = ExtractionIntermediate.model_validate(draft["intermediate"])
    eval_report = draft.get("eval_report") or {}
    eval_metadata: dict[str, Any] = {}
    leaks = eval_report.get("must_not_include_leaks")
    if leaks is not None:
        eval_metadata["must_not_include_leaks"] = len(leaks) if isinstance(leaks, list) else leaks
    if "must_not_include_total" in eval_report:
        eval_metadata["must_not_include_total"] = eval_report["must_not_include_total"]
    generated = {
        "by": "ai",
        "model": intermediate.extraction_model,
        "at": draft["created_at"],
        "status": draft["status"],
        "approved_by": draft.get("approved_by"),
        "approved_at": draft.get("approved_at"),
        "eval": eval_metadata,
    }
    return {**rec, "record": to_record(intermediate)}, generated


# ── Core pipeline runner ──────────────────────────────────────────────────────

def run_pipeline(pid: str, user: dict) -> dict:
    """
    Run the document extraction pipeline for patient *pid*.

    Uses the connect-frontend auth user for audit logging.
    Returns the newly created ips_drafts row (parsed).

    Steps that need Keycloak / HAPI FHIR are skipped in this integration
    (steps 1 gate and 7 FHIR validator). The pipeline pseudonymises before
    any LLM call and evaluates against the patient's reference record.
    """
    # Lazy imports — pipeline deps are optional (not in connect-frontend requirements)
    try:
        from pipeline.pseudonymize import pseudonymize_documents
        from pipeline.llm_client import LLMClient
        from pipeline.extract import extract
        from pipeline.verify_quotes import verify_quotes
        from pipeline.terminology import validate_terminology
        from pipeline.fhir_mapping import map_to_fhir
        from pipeline.models import ExtractionIntermediate
    except ImportError as exc:
        raise HTTPException(500, f"Pipeline dependencies not installed: {exc}. "
                            "Run: pip install pydantic pyyaml requests cryptography openai") from exc

    patient_json, documents = _load_patient_docs(pid)
    warnings: list[str] = []

    # Step 2: pseudonymise
    pseudo_docs, pseudo_mapping = pseudonymize_documents(
        patient_json=patient_json, documents=documents, shift_days=0
    )

    # Step 3: LLM extraction
    try:
        llm = LLMClient()
    except (EnvironmentError, ImportError) as exc:
        raise HTTPException(503, f"LLM not configured: {exc}. "
                            "Set LLM_PROVIDER and the matching API key.") from exc

    intermediate: ExtractionIntermediate = extract(pseudo_mapping.patient_token, pseudo_docs, llm)

    # Step 4: quote verification
    intermediate, failed_quotes = verify_quotes(intermediate, pseudo_docs)
    if failed_quotes:
        warnings.append(f"{len(failed_quotes)} quote(s) could not be verified against source documents.")

    # Step 5: terminology validation
    intermediate = validate_terminology(intermediate)

    # Step 6: FHIR mapping (deterministic, no external service)
    fhir_bundle = map_to_fhir(intermediate, patient_json, pseudo_mapping, documents)

    # Step 7: FHIR validation — skipped (no validator_cli.jar in this setup)
    warnings.append("FHIR structural validation skipped (validator_cli.jar not present in this deployment).")

    # Step 8: evaluation against the English reference record (if available)
    eval_report: dict[str, Any] | None = None
    en_path = _patients_dir() / pid / "en.json"
    if en_path.exists():
        try:
            from pipeline.evaluate import evaluate as eval_pipeline
            english_bundle = json.loads(en_path.read_text(encoding="utf-8"))
            reference_record = english_bundle.get("record")
            if isinstance(reference_record, dict):
                report = eval_pipeline(intermediate, reference_record)
                eval_report = report.to_dict()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Evaluation skipped: {exc}")

    # Persist to SQLite
    draft_id = str(uuid.uuid4())
    now = state.now()
    with state.tx() as c:
        c.execute(
            "INSERT INTO ips_drafts (id, patient_id, status, intermediate, summary_md, "
            "fhir_bundle, eval_report, warnings, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                draft_id, pid, "draft",
                intermediate.model_dump_json(),
                None,
                json.dumps(fhir_bundle, ensure_ascii=False),
                json.dumps(eval_report, ensure_ascii=False) if eval_report else None,
                json.dumps(warnings, ensure_ascii=False),
                now, now,
            ),
        )
        state.audit(user, "primary", "ips_pipeline_run", patient_id=pid,
                    outcome="draft", details={"draft_id": draft_id, "warnings": len(warnings)}, conn=c)

    return _parse_draft(state.one("SELECT * FROM ips_drafts WHERE id = ?", (draft_id,)))


# ── Approval ──────────────────────────────────────────────────────────────────

def approve_draft(draft_id: str, user: dict) -> dict:
    row = state.one("SELECT * FROM ips_drafts WHERE id = ?", (draft_id,))
    if not row:
        raise HTTPException(404, "Draft not found")
    if row["status"] == "approved":
        raise HTTPException(409, "Draft is already approved")
    now = state.now()
    with state.tx() as c:
        c.execute(
            "UPDATE ips_drafts SET status='approved', approved_by=?, approved_at=?, updated_at=? WHERE id=?",
            (user["name"], now, now, draft_id),
        )
        state.audit(user, "primary", "ips_draft_approved", patient_id=row["patient_id"],
                    outcome="approved", details={"draft_id": draft_id}, conn=c)
    return _parse_draft(state.one("SELECT * FROM ips_drafts WHERE id = ?", (draft_id,)))

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
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .. import state
from ..config import settings


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

def _patients_dir() -> Path:
    """Directory containing per-patient document bundles (patients/P00X/)."""
    return Path(settings.data_dir).parent / "patients"


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
        "SELECT * FROM ips_drafts WHERE patient_id = ? ORDER BY created_at DESC LIMIT 1",
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


# ── Core pipeline runner ──────────────────────────────────────────────────────

def run_pipeline(pid: str, user: dict) -> dict:
    """
    Run the 9-step IPS pipeline for patient *pid*.

    Uses the connect-frontend auth user for audit logging.
    Returns the newly created ips_drafts row (parsed).

    Steps that need Keycloak / HAPI FHIR are skipped in this integration
    (steps 1 gate, 2 pseudo, 7 FHIR validator, 8 eval only when ground_truth
    exists).  The pipeline still pseudonymises before any LLM call.
    """
    # Lazy imports — pipeline deps are optional (not in connect-frontend requirements)
    try:
        from pipeline.pseudonymize import pseudonymize_documents
        from pipeline.llm_client import LLMClient
        from pipeline.extract import extract
        from pipeline.verify_quotes import verify_quotes
        from pipeline.terminology import validate_terminology
        from pipeline.fhir_mapping import map_to_fhir
        from pipeline.summary import generate_summary
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

    # Step 8: evaluation against ground truth (if available)
    eval_report: dict[str, Any] | None = None
    gt_path = _patients_dir() / pid / "ground_truth_ips.json"
    if gt_path.exists():
        try:
            from pipeline.evaluate import evaluate as eval_pipeline
            report = eval_pipeline(intermediate, gt_path)
            eval_report = report.to_dict()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Evaluation skipped: {exc}")

    # Step 9: discharge summary
    summary_md = generate_summary(intermediate, patient_json, llm)

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
                summary_md,
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

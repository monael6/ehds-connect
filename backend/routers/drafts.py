"""drafts.py – Get and patch the current draft for a patient."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.auth import CurrentPractitioner
from backend.audit import record_audit
from backend.fhir_client import get_fhir_client
from backend.jobs import _jobs, JobStatus

router = APIRouter(tags=["drafts"])


class DraftPatch(BaseModel):
    """Body for PATCH /draft — clinician edits."""
    summary_text: str | None = None
    items_json: dict | None = None   # free-form edited intermediate JSON


@router.get("/api/patients/{patient_id}/draft")
async def get_draft(patient_id: str, practitioner: CurrentPractitioner) -> dict:
    """Return the latest draft Bundle and intermediate JSON for a patient."""
    fhir = get_fhir_client()
    if not await fhir.check_assignment(patient_id, practitioner.practitioner_id):
        raise HTTPException(status_code=403, detail="Access denied.")

    # Find the most recent preliminary Composition
    result = await fhir.search("Composition", {
        "subject": f"Patient/{patient_id}",
        "status": "preliminary",
        "_sort": "-date",
        "_count": "1",
    })
    entries = result.get("entry", [])
    if not entries:
        # Check in-memory jobs (pipeline may have just completed)
        draft_from_job = _find_latest_job_result(patient_id)
        if draft_from_job:
            return draft_from_job
        raise HTTPException(status_code=404, detail="No draft found for this patient.")

    composition = entries[0]["resource"]
    await record_audit("read", practitioner.practitioner_id, patient_id, "Composition",
                       composition.get("id"))
    return {"composition": composition, "status": "preliminary"}


@router.patch("/api/patients/{patient_id}/draft")
async def patch_draft(
    patient_id: str,
    body: DraftPatch,
    practitioner: CurrentPractitioner,
) -> dict:
    """Save clinician edits to the draft."""
    fhir = get_fhir_client()
    if not await fhir.check_assignment(patient_id, practitioner.practitioner_id):
        raise HTTPException(status_code=403, detail="Access denied.")

    # Retrieve the existing draft
    result = await fhir.search("Composition", {
        "subject": f"Patient/{patient_id}",
        "status": "preliminary",
        "_sort": "-date",
        "_count": "1",
    })
    entries = result.get("entry", [])
    if not entries:
        raise HTTPException(status_code=404, detail="No draft to patch.")

    composition = entries[0]["resource"]
    comp_id = composition["id"]

    # Apply edits: store summary text as a note extension
    if body.summary_text is not None:
        _set_extension(composition, "http://ips-hackathon/extensions/summary-text", body.summary_text)
    if body.items_json is not None:
        _set_extension(
            composition,
            "http://ips-hackathon/extensions/edited-items",
            str(body.items_json)[:10000],
        )

    # Mark as edited
    _set_extension(composition, "http://ips-hackathon/extensions/edited-by",
                   practitioner.practitioner_id)

    await fhir.put(f"Composition/{comp_id}", composition)
    await record_audit("update", practitioner.practitioner_id, patient_id, "Composition", comp_id)
    return {"status": "saved", "composition_id": comp_id}


def _set_extension(resource: dict, url: str, value: str) -> None:
    extensions = resource.setdefault("extension", [])
    for ext in extensions:
        if ext.get("url") == url:
            ext["valueString"] = value
            return
    extensions.append({"url": url, "valueString": value})


def _find_latest_job_result(patient_fhir_id: str) -> dict | None:
    """Look for a completed in-memory job for this patient."""
    for job in sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True):
        if job.patient_fhir_id == patient_fhir_id and job.status == JobStatus.completed:
            return job.result
    return None

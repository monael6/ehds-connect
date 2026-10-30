"""history.py – Version history and diff endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.auth import CurrentPractitioner
from backend.audit import record_audit
from backend.fhir_client import get_fhir_client

router = APIRouter(tags=["history"])


@router.get("/api/patients/{patient_id}/history")
async def get_history(patient_id: str, practitioner: CurrentPractitioner) -> dict:
    """Return all Composition versions for a patient (draft + approved)."""
    fhir = get_fhir_client()
    if not await fhir.check_assignment(patient_id, practitioner.practitioner_id):
        raise HTTPException(status_code=403, detail="Access denied.")

    result = await fhir.search("Composition", {
        "subject": f"Patient/{patient_id}",
        "_sort": "-date",
        "_count": "50",
    })
    versions = []
    for entry in result.get("entry", []):
        r = entry["resource"]
        versions.append({
            "id": r.get("id"),
            "status": r.get("status"),
            "date": r.get("date"),
            "author": r.get("author", []),
            "title": r.get("title", ""),
        })

    await record_audit("read", practitioner.practitioner_id, patient_id, "Composition")
    return {"versions": versions}


@router.get("/api/patients/{patient_id}/history/{version_id}")
async def get_version(
    patient_id: str,
    version_id: str,
    practitioner: CurrentPractitioner,
) -> dict:
    """Return a specific Composition version."""
    fhir = get_fhir_client()
    if not await fhir.check_assignment(patient_id, practitioner.practitioner_id):
        raise HTTPException(status_code=403, detail="Access denied.")

    composition = await fhir.read("Composition", version_id)
    await record_audit("read", practitioner.practitioner_id, patient_id, "Composition", version_id)
    return composition

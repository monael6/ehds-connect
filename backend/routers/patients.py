"""patients.py – Patient list and detail endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.auth import CurrentPractitioner
from backend.audit import record_audit
from backend.fhir_client import get_fhir_client

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("")
async def list_patients(practitioner: CurrentPractitioner) -> dict:
    """Return patients assigned to the logged-in practitioner."""
    fhir = get_fhir_client()
    # Find CareTeams where this practitioner is a participant
    care_teams = await fhir.search("CareTeam", {
        "participant": f"Practitioner/{practitioner.practitioner_id}",
        "_include": "CareTeam:subject",
    })
    patients = []
    for entry in care_teams.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Patient":
            pid = resource.get("id")
            if pid:
                await record_audit("read", practitioner.practitioner_id, pid, "Patient", pid)
                patients.append(_summarize_patient(resource))
    return {"patients": patients}


@router.get("/{patient_id}")
async def get_patient(patient_id: str, practitioner: CurrentPractitioner) -> dict:
    fhir = get_fhir_client()
    patient = await fhir.read("Patient", patient_id)
    if not await fhir.check_assignment(patient_id, practitioner.practitioner_id):
        raise HTTPException(status_code=403, detail="Access denied: not assigned to this patient.")
    await record_audit("read", practitioner.practitioner_id, patient_id, "Patient", patient_id)
    return patient


def _summarize_patient(resource: dict) -> dict:
    name = resource.get("name", [{}])[0]
    return {
        "id": resource.get("id"),
        "family": name.get("family", ""),
        "given": " ".join(name.get("given", [])),
        "birthDate": resource.get("birthDate", ""),
        "gender": resource.get("gender", ""),
    }

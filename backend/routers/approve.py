"""
approve.py – Approve a draft: re-map → validate → save final Bundle.

SECURITY:
  - The author is taken ONLY from the validated OIDC token (practitioner.practitioner_id).
  - Approval is blocked if validation has errors.
  - The approved Composition gets status "final" and a legal attester.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.auth import CurrentPractitioner
from backend.audit import record_audit
from backend.fhir_client import get_fhir_client
from pipeline.validate import validate_bundle

router = APIRouter(tags=["approve"])


class ApprovalRequest(BaseModel):
    reviewed_and_confirmed: bool   # Must be True — clinician ticked the checkbox


@router.post("/api/patients/{patient_id}/approve")
async def approve_draft(
    patient_id: str,
    body: ApprovalRequest,
    practitioner: CurrentPractitioner,
) -> dict:
    """
    Approve the current draft:
      1. Check no red items (quote_verified=False) remain
      2. Re-validate with FHIR Validator
      3. If validation passes: save final Composition + Provenance + AuditEvent
    """
    if not body.reviewed_and_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Freigabe verweigert: Bestätigung durch Arzt fehlt (reviewed_and_confirmed muss true sein).",
        )

    fhir = get_fhir_client()
    if not await fhir.check_assignment(patient_id, practitioner.practitioner_id):
        raise HTTPException(status_code=403, detail="Access denied.")

    # Load current preliminary Composition
    result = await fhir.search("Composition", {
        "subject": f"Patient/{patient_id}",
        "status": "preliminary",
        "_sort": "-date",
        "_count": "1",
        "_revinclude": "Bundle:composition",
    })
    entries = result.get("entry", [])
    if not entries:
        raise HTTPException(status_code=404, detail="No draft found.")

    composition = entries[0]["resource"]
    comp_id = composition["id"]

    # Check for red items
    bundle_result = await fhir.search("Bundle", {
        "composition": f"Composition/{comp_id}",
    })
    bundle_entries = bundle_result.get("entry", [])
    if bundle_entries:
        bundle = bundle_entries[0]["resource"]
        red_items = _find_red_items(bundle)
        if red_items:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Freigabe verweigert: Es gibt noch rot markierte Einträge (Zitate nicht verifiziert). Bitte prüfen Sie alle roten Einträge vor der Freigabe.",
                    "red_items": red_items,
                },
            )

        # Re-validate with FHIR Validator
        val_report = validate_bundle(bundle)
        if val_report.errors:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Freigabe verweigert: FHIR-Validierung hat Fehler.",
                    "validation_errors": [
                        {"location": e.location, "message": e.message}
                        for e in val_report.errors
                    ],
                },
            )

    # All checks passed — update Composition to final
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    composition["status"] = "final"
    composition["author"] = [{"reference": f"Practitioner/{practitioner.practitioner_id}"}]
    composition["attester"] = [{
        "mode": "legal",
        "time": now,
        "party": {"reference": f"Practitioner/{practitioner.practitioner_id}"},
    }]

    await fhir.put(f"Composition/{comp_id}", composition)

    # Write Provenance for the approval action
    provenance = {
        "resourceType": "Provenance",
        "target": [{"reference": f"Composition/{comp_id}"}],
        "recorded": now,
        "reason": [{"display": "Klinische Freigabe durch approving Arzt"}],
        "agent": [
            {
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                                     "code": "author", "display": "Author"}]},
                "who": {"reference": f"Practitioner/{practitioner.practitioner_id}"},
            },
            {
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                                     "code": "verifier", "display": "Verifier"}]},
                "who": {"reference": f"Practitioner/{practitioner.practitioner_id}"},
            },
        ],
    }
    await fhir.post("Provenance", provenance)
    await record_audit("update", practitioner.practitioner_id, patient_id, "Composition", comp_id)

    return {
        "status": "approved",
        "composition_id": comp_id,
        "approved_by": practitioner.practitioner_id,
        "approved_at": now,
    }


def _find_red_items(bundle: dict) -> list[str]:
    """Return list of item descriptions with status-light = red."""
    red = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        for ext in resource.get("extension", []):
            if (ext.get("url") == "http://ips-hackathon/extensions/status-light"
                    and ext.get("valueString") == "red"):
                text = (
                    resource.get("code", {}).get("text")
                    or resource.get("description", "")
                    or resource.get("id", "unknown")
                )
                red.append(text)
    return red

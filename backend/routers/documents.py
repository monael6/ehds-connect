"""documents.py – Source document endpoints."""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException

from backend.auth import CurrentPractitioner
from backend.audit import record_audit
from backend.fhir_client import get_fhir_client

router = APIRouter(prefix="/api/patients/{patient_id}/documents", tags=["documents"])


async def _check_assignment(patient_id: str, practitioner_id: str) -> None:
    fhir = get_fhir_client()
    if not await fhir.check_assignment(patient_id, practitioner_id):
        raise HTTPException(status_code=403, detail="Access denied: not assigned to this patient.")


@router.get("")
async def list_documents(patient_id: str, practitioner: CurrentPractitioner) -> dict:
    await _check_assignment(patient_id, practitioner.practitioner_id)
    fhir = get_fhir_client()
    result = await fhir.search("DocumentReference", {
        "subject": f"Patient/{patient_id}",
        "_sort": "date",
        "_count": "200",
    })
    docs = []
    for entry in result.get("entry", []):
        r = entry.get("resource", {})
        docs.append({
            "id": r.get("id"),
            "source_doc_id": _get_extension(r, "http://ips-hackathon/extensions/source-doc-id"),
            "type": r.get("type", {}).get("text", ""),
            "date": r.get("date", ""),
            "description": r.get("description", ""),
        })
    await record_audit("read", practitioner.practitioner_id, patient_id, "DocumentReference")
    return {"documents": docs}


@router.get("/{doc_id}")
async def get_document(
    patient_id: str, doc_id: str, practitioner: CurrentPractitioner
) -> dict:
    await _check_assignment(patient_id, practitioner.practitioner_id)
    fhir = get_fhir_client()
    doc_ref = await fhir.read("DocumentReference", doc_id)

    # Decode base64 content
    content = doc_ref.get("content", [{}])[0].get("attachment", {})
    data_b64 = content.get("data", "")
    text = base64.b64decode(data_b64).decode("utf-8") if data_b64 else ""

    await record_audit("read", practitioner.practitioner_id, patient_id, "DocumentReference", doc_id)
    return {
        "id": doc_ref.get("id"),
        "source_doc_id": _get_extension(doc_ref, "http://ips-hackathon/extensions/source-doc-id"),
        "type": doc_ref.get("type", {}).get("text", ""),
        "date": doc_ref.get("date", ""),
        "description": doc_ref.get("description", ""),
        "text": text,
        "fachrichtung": _get_extension(doc_ref, "http://ips-hackathon/extensions/fachrichtung"),
    }


def _get_extension(resource: dict, url: str) -> str:
    for ext in resource.get("extension", []):
        if ext.get("url") == url:
            return ext.get("valueString", "")
    return ""

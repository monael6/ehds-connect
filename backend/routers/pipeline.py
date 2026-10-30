"""pipeline.py – Start and poll async pipeline jobs."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.auth import CurrentPractitioner
from backend.audit import record_audit
from backend.fhir_client import get_fhir_client
from backend.jobs import JobStatus, create_job, get_job, run_pipeline_job

router = APIRouter(tags=["pipeline"])


@router.post("/api/patients/{patient_id}/pipeline")
async def start_pipeline(
    patient_id: str,
    practitioner: CurrentPractitioner,
    background_tasks: BackgroundTasks,
) -> dict:
    """Start the AI pipeline for a patient. Returns immediately with a job_id."""
    fhir = get_fhir_client()
    if not await fhir.check_assignment(patient_id, practitioner.practitioner_id):
        raise HTTPException(status_code=403, detail="Access denied.")

    # Load patient and documents from FHIR
    patient_resource = await fhir.read("Patient", patient_id)
    docs_result = await fhir.search("DocumentReference", {
        "subject": f"Patient/{patient_id}",
        "_count": "500",
    })

    import base64
    documents: list[dict] = []
    for entry in docs_result.get("entry", []):
        r = entry["resource"]
        content = r.get("content", [{}])[0].get("attachment", {})
        data_b64 = content.get("data", "")
        text = base64.b64decode(data_b64).decode("utf-8") if data_b64 else ""
        source_id = _get_ext(r, "http://ips-hackathon/extensions/source-doc-id") or r.get("id", "")
        documents.append({
            "id": source_id,
            "typ": r.get("type", {}).get("text", ""),
            "datum": r.get("date", ""),
            "titel": r.get("description", ""),
            "text": text,
            "autor_rolle": "",
            "einrichtung": "",
            "fachrichtung": _get_ext(r, "http://ips-hackathon/extensions/fachrichtung"),
        })

    # Convert FHIR Patient to our patient_json format
    patient_json = _fhir_patient_to_json(patient_resource)

    job = create_job(patient_id, practitioner.practitioner_id)
    background_tasks.add_task(run_pipeline_job, job, patient_json, documents)

    await record_audit("create", practitioner.practitioner_id, patient_id, "PipelineJob", job.job_id)
    return {"job_id": job.job_id, "status": job.status.value}


@router.get("/api/jobs/{job_id}")
async def poll_job(job_id: str, practitioner: CurrentPractitioner) -> dict:
    """Poll a pipeline job's status and progress."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    # Only the practitioner who started the job may poll it
    if job.practitioner_id != practitioner.practitioner_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return job.to_dict()


def _get_ext(resource: dict, url: str) -> str:
    for ext in resource.get("extension", []):
        if ext.get("url") == url:
            return ext.get("valueString", "")
    return ""


def _fhir_patient_to_json(r: dict) -> dict:
    name = r.get("name", [{}])[0]
    gender_map = {"female": "weiblich", "male": "maennlich", "other": "divers"}
    identifiers = {
        i["system"]: i["value"]
        for i in r.get("identifier", [])
        if "system" in i and "value" in i
    }
    return {
        "patient_id": identifiers.get("http://ips-hackathon/patients", r.get("id", "")),
        "vorname": " ".join(name.get("given", [])),
        "nachname": name.get("family", ""),
        "geburtsdatum": r.get("birthDate", ""),
        "geschlecht": gender_map.get(r.get("gender", ""), ""),
        "fiktive_versicherungsnummer": identifiers.get("http://ips-hackathon/versicherung", ""),
        "wohnort_bundesland": r.get("address", [{}])[0].get("state", ""),
    }

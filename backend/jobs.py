"""
jobs.py – Async pipeline job runner.

Manages background pipeline jobs and their status.
Jobs are kept in-memory (sufficient for hackathon; production would use Redis/Celery).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


@dataclass
class PipelineJob:
    job_id: str
    patient_fhir_id: str
    practitioner_id: str
    status: JobStatus = JobStatus.pending
    progress: int = 0        # 0–100
    step: str = ""
    error: str = ""
    result: dict | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "patient_fhir_id": self.patient_fhir_id,
            "status": self.status.value,
            "progress": self.progress,
            "step": self.step,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# In-memory store: job_id → PipelineJob
_jobs: dict[str, PipelineJob] = {}


def create_job(patient_fhir_id: str, practitioner_id: str) -> PipelineJob:
    job_id = str(uuid.uuid4())
    job = PipelineJob(
        job_id=job_id,
        patient_fhir_id=patient_fhir_id,
        practitioner_id=practitioner_id,
    )
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> PipelineJob | None:
    return _jobs.get(job_id)


async def run_pipeline_job(job: PipelineJob, patient_json: dict, documents: list[dict]) -> None:
    """
    Run the full pipeline as a background asyncio task.
    Updates job.progress and job.step as it goes.
    Stores the FHIR bundle in job.result on success.
    """
    import json as json_mod
    from pipeline.extract import extract
    from pipeline.fhir_mapping import map_to_fhir
    from pipeline.llm_client import LLMClient
    from pipeline.models import ExtractionIntermediate
    from pipeline.pseudonymize import pseudonymize_documents
    from pipeline.terminology import validate_terminology
    from pipeline.validate import validate_bundle
    from pipeline.verify_quotes import verify_quotes

    job.status = JobStatus.running

    try:
        # Step 2
        job.step = "Pseudonymisierung"
        job.progress = 10
        pseudo_docs, mapping = pseudonymize_documents(patient_json, documents)

        # Step 3
        job.step = "KI-Extraktion"
        job.progress = 25
        llm = LLMClient()
        # Run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        intermediate: ExtractionIntermediate = await loop.run_in_executor(
            None, extract, mapping.patient_token, pseudo_docs, llm
        )

        # Step 4
        job.step = "Zitat-Verifikation"
        job.progress = 50
        intermediate, _ = verify_quotes(intermediate, pseudo_docs)

        # Step 5
        job.step = "Terminologie-Validierung"
        job.progress = 60
        intermediate = validate_terminology(intermediate)

        # Step 6
        job.step = "FHIR-Mapping"
        job.progress = 75
        bundle = map_to_fhir(intermediate, patient_json, mapping, documents)

        # Step 7
        job.step = "FHIR-Validierung"
        job.progress = 90
        val_report = validate_bundle(bundle)

        job.result = {
            "bundle": bundle,
            "intermediate": json_mod.loads(intermediate.model_dump_json()),
            "validation": val_report.to_dict(),
            "patient_token": mapping.patient_token,
        }
        job.status = JobStatus.completed
        job.progress = 100
        job.step = "Abgeschlossen"
        job.completed_at = datetime.now(timezone.utc).isoformat()
        logger.info("Job %s completed for patient %s", job.job_id, job.patient_fhir_id)

    except Exception as exc:
        job.status = JobStatus.failed
        job.error = str(exc)[:500]
        job.completed_at = datetime.now(timezone.utc).isoformat()
        logger.error("Job %s failed: %s", job.job_id, exc)

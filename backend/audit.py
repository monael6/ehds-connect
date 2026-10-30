"""
audit.py – Write FHIR AuditEvent resources for every read/write of patient data.

SECURITY: AuditEvents contain WHO, WHEN, WHICH PATIENT TOKEN, WHICH ACTION.
They NEVER contain clinical content, names, diagnoses, or document text.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.fhir_client import get_fhir_client

logger = logging.getLogger(__name__)


async def record_audit(
    action: str,          # "read" | "create" | "update" | "delete"
    practitioner_id: str,
    patient_fhir_id: str,
    resource_type: str,
    resource_id: str | None = None,
    outcome: str = "0",   # "0" = success, "8" = serious failure (FHIR audit codes)
) -> None:
    """Write a FHIR AuditEvent. Failures are logged but do not block the main operation."""
    try:
        event: dict = {
            "resourceType": "AuditEvent",
            "type": {
                "system": "http://dicom.nema.org/resources/ontology/DCM",
                "code": "110100",
                "display": "Application Activity",
            },
            "action": action[0].upper(),   # R, C, U, D
            "recorded": datetime.now(timezone.utc).isoformat(),
            "outcome": outcome,
            "agent": [
                {
                    "who": {"reference": f"Practitioner/{practitioner_id}"},
                    "requestor": True,
                }
            ],
            "source": {
                "observer": {"display": "IPS-Hackathon-Backend"},
            },
            "entity": [
                {
                    "what": {
                        "reference": (
                            f"{resource_type}/{resource_id}"
                            if resource_id
                            else f"Patient/{patient_fhir_id}"
                        )
                    },
                    "type": {
                        "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                        "code": "2",
                        "display": "System Object",
                    },
                    # patient reference for tracking — no clinical content
                    "role": {
                        "system": "http://terminology.hl7.org/CodeSystem/object-role",
                        "code": "1",
                        "display": "Patient",
                    },
                }
            ],
        }
        client = get_fhir_client()
        await client.post("AuditEvent", event)
    except Exception as exc:
        # Audit logging failure must not block clinical operations
        logger.error("Failed to write AuditEvent: %s", exc)

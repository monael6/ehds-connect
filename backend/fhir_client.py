"""
fhir_client.py – Internal HAPI FHIR server client.

Only the backend calls this. The FHIR server is on the internal Docker network.
No patient data is logged.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)


class FHIRClient:
    def __init__(self) -> None:
        self._base = get_settings().fhir_base_url.rstrip("/")
        self._headers = {
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
        }

    async def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self._base}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=self._headers, params=params)
            r.raise_for_status()
            return r.json()

    async def post(self, path: str, body: dict) -> dict:
        url = f"{self._base}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=self._headers, json=body)
            r.raise_for_status()
            return r.json()

    async def put(self, path: str, body: dict) -> dict:
        url = f"{self._base}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.put(url, headers=self._headers, json=body)
            r.raise_for_status()
            return r.json()

    async def search(self, resource_type: str, params: dict) -> dict:
        return await self.get(resource_type, params=params)

    async def read(self, resource_type: str, resource_id: str) -> dict:
        return await self.get(f"{resource_type}/{resource_id}")

    async def transaction(self, bundle: dict) -> dict:
        return await self.post("", bundle)

    async def get_patient_by_identifier(self, patient_id: str) -> dict | None:
        """Find a Patient by the hackathon identifier system."""
        result = await self.search("Patient", {
            "identifier": f"http://ips-hackathon/patients|{patient_id}"
        })
        entries = result.get("entry", [])
        if not entries:
            return None
        return entries[0]["resource"]

    async def get_care_team_practitioners(self, patient_fhir_id: str) -> list[str]:
        """Return list of Practitioner IDs assigned to a patient via CareTeam."""
        result = await self.search("CareTeam", {"subject": f"Patient/{patient_fhir_id}"})
        practitioner_ids: list[str] = []
        for entry in result.get("entry", []):
            ct = entry["resource"]
            for participant in ct.get("participant", []):
                member_ref = participant.get("member", {}).get("reference", "")
                if member_ref.startswith("Practitioner/"):
                    practitioner_ids.append(member_ref.split("/")[-1])
        return practitioner_ids

    async def check_assignment(self, patient_fhir_id: str, practitioner_id: str) -> bool:
        """Return True if the practitioner is assigned to this patient."""
        assigned = await self.get_care_team_practitioners(patient_fhir_id)
        return practitioner_id in assigned


_client: FHIRClient | None = None


def get_fhir_client() -> FHIRClient:
    global _client
    if _client is None:
        _client = FHIRClient()
    return _client

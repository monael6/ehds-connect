"""Tests for document-based Patient Summary generation without live LLM calls."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app import datastore
from app.main import app
from app import state
from pipeline.models import (
    ActiveProblem,
    ExcludedItem,
    ExclusionReason,
    ExtractionIntermediate,
    IncludedSection,
    KeyResult,
)


@pytest.fixture
def client(store):
    datastore.set_store(store)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _headers(client: TestClient, user_id: str) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"user_id": user_id}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _intermediate() -> ExtractionIntermediate:
    return ExtractionIntermediate(
        patient_token="PT-test",
        extraction_model="mock-model",
        extraction_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        included=IncludedSection(
            problems_active=[
                ActiveProblem(
                    text="Acute ankle sprain",
                    source_ids=["P001-D004"],
                    quote="Distorsion des Sprunggelenks",
                    quote_verified=True,
                )
            ],
            key_results=[
                KeyResult(
                    text="Potassium",
                    value="4.1 mmol/L",
                    source_ids=["P001-D004"],
                    quote="Kalium 4,1 mmol/l",
                    quote_verified=False,
                )
            ],
        ),
        excluded=[
            ExcludedItem(
                text="Heart disease",
                reason=ExclusionReason.family_history,
                source_ids=["P001-D004"],
                quote="Herzerkrankung des Vaters",
            )
        ],
    )


def _pipeline_patches(intermediate: ExtractionIntermediate):
    pseudo_docs = [{"id": "P001-D004", "text": "[PAT-NAME] clinical note", "typ": "Aufnahmebefund",
                    "datum": "2024-01-01T00:00"}]
    pseudo_mapping = MagicMock(patient_token="PT-test")
    llm = MagicMock()
    report = MagicMock(to_dict=MagicMock(return_value={
        "overall_precision": 0.91,
        "overall_recall": 0.82,
        "overall_f1": 0.86,
        "must_not_include_leaks": [],
    }))
    extract = patch("pipeline.extract.extract", return_value=intermediate)
    return (
        patch("app.primary.ips_pipeline._load_patient_docs", return_value=(
            {"patient_id": "P001", "vorname": "Test", "nachname": "Patient",
             "geburtsdatum": "1990-01-01", "geschlecht": "weiblich"},
            [{"id": "P001-D004", "text": "Deutscher Aufnahmebefund", "typ": "Aufnahmebefund",
              "datum": "2024-01-01T00:00"}],
        )),
        patch("pipeline.pseudonymize.pseudonymize_documents", return_value=(pseudo_docs, pseudo_mapping)),
        extract,
        patch("pipeline.verify_quotes.verify_quotes", return_value=(intermediate, [])),
        patch("pipeline.terminology.validate_terminology", return_value=intermediate),
        patch("pipeline.fhir_mapping.map_to_fhir", return_value={"resourceType": "Bundle", "entry": []}),
        patch("pipeline.evaluate.evaluate", return_value=report),
        patch("pipeline.llm_client.LLMClient", return_value=llm),
    ), pseudo_docs, llm


def test_hospital_it_cannot_access_any_ips_pipeline_endpoint(client):
    headers = _headers(client, "u-gruber")
    assert client.post("/api/patients/P001/ips-pipeline", headers=headers).status_code == 403
    assert client.get("/api/patients/P001/ips-pipeline", headers=headers).status_code == 403
    assert client.post("/api/patients/P001/ips-pipeline/approve", headers=headers).status_code == 403


def test_pipeline_returns_503_without_openai_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    response = client.post("/api/patients/P001/ips-pipeline", headers=_headers(client, "u-berger"))
    assert response.status_code == 503
    assert "OPENAI_API_KEY is not set" in response.json()["detail"]


def test_mocked_run_drives_summary_letter_and_approval(client):
    headers = _headers(client, "u-berger")
    patches, pseudo_docs, llm = _pipeline_patches(_intermediate())
    with patches[0], patches[1], patches[2] as extract, patches[3], patches[4], patches[5], patches[6], patches[7]:
        response = client.post("/api/patients/P001/ips-pipeline", headers=headers)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["status"] == "draft"
    assert draft["summary_md"] is None
    assert draft["fhir_bundle"]["resourceType"] == "Bundle"
    assert extract.call_args.args == ("PT-test", pseudo_docs, llm)

    summary_response = client.get("/api/patients/P001/summary?lang=en", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["generated"]["by"] == "ai"
    assert summary["generated"]["status"] == "draft"
    assert summary["generated"]["eval"] == {
        "overall_precision": 0.91,
        "overall_recall": 0.82,
        "overall_f1": 0.86,
        "must_not_include_leaks": 0,
    }
    assert any(p["label"] == "Acute ankle sprain" and p["code"] == "P001-problem-0"
               for p in summary["problems"])
    check_texts = [check["text"] for check in summary["checks"]]
    assert any("Heart disease (family history, not the patient's own illness)" in text for text in check_texts)
    assert any(
        text == "Potassium: the AI could not find this statement word-for-word in the source documents. Please review the sources."
        for text in check_texts
    )
    assert all("ruled out" not in text.lower() for text in check_texts)

    letter_response = client.post("/api/discharge-letters", json={"patient_id": "P001"}, headers=headers)
    assert letter_response.status_code == 200
    letter = letter_response.json()
    diagnoses = next(section for section in letter["content"]["sections"] if section["key"] == "diagnosen")
    assert any(item["text"] == "Acute ankle sprain" for item in diagnoses["items"])

    approved = client.post("/api/patients/P001/ips-pipeline/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == "Dr. Markus Berger"
    second_approval = client.post("/api/patients/P001/ips-pipeline/approve", headers=headers)
    assert second_approval.status_code == 409

    updated_summary = client.get("/api/patients/P001/summary?lang=en", headers=headers).json()
    assert updated_summary["generated"]["status"] == "approved"


def test_bundle_patients_without_drafts_use_reference_records(client):
    headers = _headers(client, "u-berger")
    for patient_id in ("P001", "P002", "P003", "P004", "P005", "P006"):
        response = client.get(f"/api/patients/{patient_id}/summary?lang=en", headers=headers)
        assert response.status_code == 200
        assert response.json()["generated"] == {"by": "reference"}
        assert state.one("SELECT id FROM ips_drafts WHERE patient_id = ?", (patient_id,)) is None

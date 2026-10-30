"""Tests for document-based Patient Summary generation without live LLM calls."""
from __future__ import annotations

import json
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
    MedicationAtDischarge,
)
from pipeline.evaluate import evaluate as evaluate_reference
from pipeline.verify_quotes import _normalize, verify_quotes


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
            medication_at_discharge=[
                MedicationAtDischarge(active_ingredient="Ramipril", dose="5 mg", quote_verified=True),
                MedicationAtDischarge(active_ingredient="Metoprolol", dose="47.5 mg", quote_verified=True),
                MedicationAtDischarge(active_ingredient="Apixaban", dose="5 mg", quote_verified=True),
                MedicationAtDischarge(active_ingredient="Pantoprazole", dose="40 mg", quote_verified=True),
                MedicationAtDischarge(active_ingredient="Unlisted medicine", dose="1 tablet", quote_verified=True),
            ],
        ),
        excluded=[
            ExcludedItem(
                text="Heart disease in the patient's father",
                reason=ExclusionReason.family_history,
                detail="Reported in a cardiology family history note",
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
        "sections": [{"section": "problems_active", "true_positives": 1, "false_positives": 0, "false_negatives": 0}],
        "overall_precision": 0.91,
        "overall_recall": 0.82,
        "overall_f1": 0.86,
        "must_not_include_leaks": [],
        "must_not_include_total": len(json.loads((_REPO_ROOT / "patients/P001/en.json").read_text())["record"]["must_not_include"]),
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


def test_quote_verification_normalizes_quote_variants():
    for character in "'\"„“”‚‘’«»‹›`":
        assert _normalize(f"{character}quote{character}") == _normalize('"quote"')

    intermediate = ExtractionIntermediate(
        patient_token="PT-test",
        extraction_model="mock-model",
        extraction_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        included=IncludedSection(
            problems_active=[
                ActiveProblem(
                    text="Patient-reported intolerance",
                    source_ids=["P001-D005"],
                    quote="'immer schlecht geworden davon'",
                )
            ]
        ),
    )
    result, failed = verify_quotes(
        intermediate,
        [{"id": "P001-D005", "text": 'Patient said: "immer schlecht geworden davon".'}],
    )
    assert result.included.problems_active[0].quote_verified is True
    assert failed == []


def test_evaluation_accepts_english_reference_record():
    reference = json.loads((_REPO_ROOT / "patients/P001/en.json").read_text(encoding="utf-8"))["record"]
    report = evaluate_reference(_intermediate(), reference)
    assert report.patient_id == "P001"
    assert report.to_dict()["must_not_include_total"] == len(reference["must_not_include"])


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
    intermediate = _intermediate()
    patches, pseudo_docs, llm = _pipeline_patches(intermediate)
    with patches[0], patches[1], patches[2] as extract, patches[3], patches[4], patches[5], patches[6] as evaluate_mock, patches[7]:
        response = client.post("/api/patients/P001/ips-pipeline", headers=headers)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["status"] == "draft"
    assert draft["summary_md"] is None
    assert draft["fhir_bundle"]["resourceType"] == "Bundle"
    assert extract.call_args.args == ("PT-test", pseudo_docs, llm)
    english_record = json.loads((_REPO_ROOT / "patients/P001/en.json").read_text(encoding="utf-8"))["record"]
    assert evaluate_mock.call_args.args == (intermediate, english_record)
    assert draft["eval_report"]["must_not_include_total"] == len(english_record["must_not_include"])
    pipeline_get = client.get("/api/patients/P001/ips-pipeline", headers=headers).json()
    assert pipeline_get["eval_report"] == draft["eval_report"]
    assert "overall_precision" in pipeline_get["eval_report"] and pipeline_get["eval_report"]["sections"]

    summary_response = client.get("/api/patients/P001/summary?lang=en", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["generated"]["by"] == "ai"
    assert summary["generated"]["status"] == "draft"
    assert summary["generated"]["eval"] == {
        "must_not_include_leaks": 0,
        "must_not_include_total": len(english_record["must_not_include"]),
    }
    assert any(p["label"] == "Acute ankle sprain" and p["code"] == "P001-problem-0"
               for p in summary["problems"])
    medication_codes = {m["label"]: m["code"] for m in summary["medications"]}
    assert medication_codes == {
        "Ramipril": "C09AA05",
        "Metoprolol": "C07AB02",
        "Apixaban": "B01AF02",
        "Pantoprazole": "A02BC02",
        "Unlisted medicine": "P001-med-4",
    }
    check_texts = [check["text"] for check in summary["checks"]]
    assert any(
        text == "Heart disease in the patient's father (family history, not the patient's own illness) – "
        "Reported in a cardiology family history note. Please review the sources."
        for text in check_texts
    )
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

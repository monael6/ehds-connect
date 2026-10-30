"""Tests for the IPS pipeline integration endpoints.

These tests verify the API contract without running the actual LLM.
The pipeline.extract module is mocked to return a minimal ExtractionIntermediate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# pipeline/ lives at repo root, one level above backend/
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from fastapi.testclient import TestClient

from app import state
from app.main import app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def in_memory_db(tmp_path):
    """Each test gets a fresh in-memory SQLite DB + a minimal user seeded."""
    state.connect(":memory:")
    state._conn.executescript(state.SCHEMA)
    with state.tx() as c:
        c.execute("INSERT INTO users (id,name,role,organisation,data_holder,sign_in_method) "
                  "VALUES ('u-huber','Dr. Anna Huber','hospital','Klinikum West','Klinikum West','SSO')")
        c.execute("INSERT INTO sessions (token,user_id,created_at) VALUES ('test-token','u-huber','2026-01-01T00:00:00')")
    yield
    # teardown: state module reuses _conn; reset for next test
    state._conn = None


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}


def _minimal_intermediate():
    """Return the smallest valid ExtractionIntermediate."""
    from datetime import datetime, timezone
    from pipeline.models import (
        ExtractionIntermediate, IncludedSection, AllergyIntolerance,
        Verification, Criticality,
    )
    inc = IncludedSection(
        allergies_intolerances=[
            AllergyIntolerance(
                substance="Penicillin",
                reaction="Exanthem",
                criticality=Criticality.high,
                verification=Verification.confirmed,
                source_ids=["P003-D005"],
                quote="Allergie Penicillin bekannt",
            )
        ],
    )
    return ExtractionIntermediate(
        patient_token="PT-test",
        extraction_model="mock",
        extraction_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        included=inc,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestGetIpsPipelineNotFound:
    def test_404_when_no_draft(self, client, auth_headers):
        # Authorization bypassed via _own_patient_or_bundle mock
        with patch("app.main._own_patient_or_bundle", return_value=None):
            r = client.get("/api/patients/p-test/ips-pipeline", headers=auth_headers)
        assert r.status_code == 404
        assert "POST" in r.json()["detail"]


class TestRunIpsPipelineMocked:
    def test_201_creates_draft(self, client, auth_headers, tmp_path):
        """POST /api/patients/{pid}/ips-pipeline returns 201 with a draft when pipeline is mocked."""
        inter = _minimal_intermediate()

        with (
            patch("app.main._own_patient_or_bundle", return_value={"patient_id": "P003", "data_holder": "Klinikum West"}),
            patch("app.primary.ips_pipeline._load_patient_docs", return_value=(
                {"patient_id": "P003", "vorname": "Sabine", "nachname": "Gruber",
                 "geburtsdatum": "1993-03-15", "geschlecht": "weiblich"},
                [{"id": "P003-D005", "text": "Allergie Penicillin bekannt", "typ": "Pflegebericht", "datum": "2024-07-08T14:00"}],
            )),
            # Lazy imports inside run_pipeline → patch at the pipeline package level
            patch("pipeline.pseudonymize.pseudonymize_documents", return_value=(
                [{"id": "P003-D005", "text": "[PAT-NAME] Allergie Pen bekannt", "typ": "Pflegebericht", "datum": "2024-07-08T14:00"}],
                MagicMock(patient_token="PT-abc123"),
            )),
            patch("pipeline.extract.extract", return_value=inter),
            patch("pipeline.verify_quotes.verify_quotes", return_value=(inter, [])),
            patch("pipeline.terminology.validate_terminology", return_value=inter),
            patch("pipeline.fhir_mapping.map_to_fhir", return_value={"resourceType": "Bundle", "entry": []}),
            patch("pipeline.summary.generate_summary", return_value="# Entlassungsbrief\n\nKein Befund."),
            patch("pipeline.llm_client.LLMClient", return_value=MagicMock()),
        ):
            r = client.post("/api/patients/P003/ips-pipeline", headers=auth_headers)

        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "draft"
        assert body["patient_id"] == "P003"
        assert body["summary_md"] is not None
        assert isinstance(body["warnings"], list)
        assert body["fhir_bundle"]["resourceType"] == "Bundle"

    def test_draft_retrievable_after_run(self, client, auth_headers):
        """After POST, GET returns the same draft."""
        inter = _minimal_intermediate()

        with (
            patch("app.main._own_patient_or_bundle", return_value={"patient_id": "P003", "data_holder": "Klinikum West"}),
            patch("app.primary.ips_pipeline._load_patient_docs", return_value=(
                {"patient_id": "P003", "vorname": "Sabine", "nachname": "Gruber",
                 "geburtsdatum": "1993-03-15", "geschlecht": "weiblich"},
                [{"id": "P003-D005", "text": "Allergie Penicillin bekannt", "typ": "Pflegebericht", "datum": "2024-07-08T14:00"}],
            )),
            patch("pipeline.pseudonymize.pseudonymize_documents", return_value=(
                [{"id": "P003-D005", "text": "[PAT-NAME] Allergie Pen bekannt", "typ": "Pflegebericht", "datum": "2024-07-08T14:00"}],
                MagicMock(patient_token="PT-abc123"),
            )),
            patch("pipeline.extract.extract", return_value=inter),
            patch("pipeline.verify_quotes.verify_quotes", return_value=(inter, [])),
            patch("pipeline.terminology.validate_terminology", return_value=inter),
            patch("pipeline.fhir_mapping.map_to_fhir", return_value={"resourceType": "Bundle", "entry": []}),
            patch("pipeline.summary.generate_summary", return_value="# Draft"),
            patch("pipeline.llm_client.LLMClient", return_value=MagicMock()),
        ):
            post_r = client.post("/api/patients/P003/ips-pipeline", headers=auth_headers)
            assert post_r.status_code == 201

        with patch("app.main._own_patient_or_bundle", return_value={"patient_id": "P003", "data_holder": "Klinikum West"}):
            get_r = client.get("/api/patients/P003/ips-pipeline", headers=auth_headers)

        assert get_r.status_code == 200
        assert get_r.json()["status"] == "draft"


class TestApproveIpsPipeline:
    def _create_draft(self, pid="P003"):
        """Insert a draft directly into SQLite."""
        import uuid
        draft_id = str(uuid.uuid4())
        now = state.now()
        with state.tx() as c:
            c.execute(
                "INSERT INTO ips_drafts (id, patient_id, status, summary_md, fhir_bundle, warnings, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (draft_id, pid, "draft", "# Draft", '{"resourceType":"Bundle"}', "[]", now, now),
            )
        return draft_id

    def test_approve_sets_status(self, client, auth_headers):
        self._create_draft()
        with patch("app.main._own_patient_or_bundle", return_value={"patient_id": "P003", "data_holder": "Klinikum West"}):
            r = client.post("/api/patients/P003/ips-pipeline/approve", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "approved"
        assert body["approved_by"] == "Dr. Anna Huber"

    def test_double_approve_returns_409(self, client, auth_headers):
        self._create_draft()
        with patch("app.main._own_patient_or_bundle", return_value={"patient_id": "P003", "data_holder": "Klinikum West"}):
            client.post("/api/patients/P003/ips-pipeline/approve", headers=auth_headers)
            r = client.post("/api/patients/P003/ips-pipeline/approve", headers=auth_headers)
        assert r.status_code == 409

    def test_approve_unauthenticated_returns_401(self, client):
        self._create_draft()
        r = client.post("/api/patients/P003/ips-pipeline/approve")
        assert r.status_code == 401


class TestIpsPipelineLlmNotConfigured:
    def test_503_when_no_llm_key(self, client, auth_headers):
        """Returns 503 when LLM is not configured."""
        with (
            patch("app.main._own_patient_or_bundle", return_value={"patient_id": "P003", "data_holder": "Klinikum West"}),
            patch("app.primary.ips_pipeline._load_patient_docs", return_value=(
                {"patient_id": "P003", "vorname": "X", "nachname": "Y",
                 "geburtsdatum": "1993-01-01", "geschlecht": "weiblich"},
                [],
            )),
            patch("pipeline.pseudonymize.pseudonymize_documents", return_value=(
                [], MagicMock(patient_token="PT-x")
            )),
            # LLMClient raises EnvironmentError when key is missing
            patch("pipeline.llm_client.LLMClient", side_effect=EnvironmentError("OPENAI_API_KEY is not set")),
        ):
            r = client.post("/api/patients/P003/ips-pipeline", headers=auth_headers)
        assert r.status_code == 503
        assert "LLM" in r.json()["detail"]

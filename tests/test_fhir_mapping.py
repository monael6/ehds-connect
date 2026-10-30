"""Tests for FHIR mapping."""

import json
from datetime import datetime, timezone

import pytest

from pipeline.fhir_mapping import map_to_fhir
from pipeline.models import (
    ActiveProblem,
    AllergyIntolerance,
    Criticality,
    ExtractionIntermediate,
    IncludedSection,
    MedicationAtDischarge,
    MedStatus,
    Verification,
)
from pipeline.pseudonymize import PseudoMapping


PATIENT = {
    "patient_id": "P001",
    "vorname": "Hermine",
    "nachname": "Bruckner",
    "geburtsdatum": "1952-04-17",
    "geschlecht": "weiblich",
    "fiktive_versicherungsnummer": "FAKE-7241-170452",
    "wohnort_bundesland": "Niederösterreich",
}

DOCS = [
    {"id": "P001-D004", "typ": "Aufnahmebefund", "datum": "2024-09-02T16:05",
     "titel": "Aufnahme", "text": "Schenkelhalsfraktur re."},
]


def _make_mapping() -> PseudoMapping:
    return PseudoMapping(
        patient_token="PT-test01",
        real_name="Hermine Bruckner",
        real_dob="1952-04-17",
        real_insurance="FAKE-7241-170452",
    )


def _make_intermediate(**kwargs) -> ExtractionIntermediate:
    return ExtractionIntermediate(
        patient_token="PT-test01",
        extraction_model="test",
        extraction_timestamp=datetime.now(timezone.utc),
        included=IncludedSection(**kwargs),
    )


def _build_bundle(**kwargs) -> dict:
    inter = _make_intermediate(**kwargs)
    return map_to_fhir(inter, PATIENT, _make_mapping(), DOCS)


# ── Bundle structure ──────────────────────────────────────────────────────────

def test_bundle_is_document_type():
    bundle = _build_bundle()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "document"


def test_bundle_has_ips_profile():
    bundle = _build_bundle()
    profiles = bundle["meta"]["profile"]
    assert any("ips" in p for p in profiles)


def test_composition_is_first_entry():
    bundle = _build_bundle()
    first = bundle["entry"][0]["resource"]
    assert first["resourceType"] == "Composition"


def test_composition_status_is_preliminary():
    """Composition must NEVER be final from the pipeline — clinician approval required."""
    bundle = _build_bundle()
    comp = bundle["entry"][0]["resource"]
    assert comp["status"] == "preliminary"


def test_patient_entry_present():
    bundle = _build_bundle()
    resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "Patient" in resource_types


# ── Required sections present with emptyReason when no data ─────────────────

def test_required_sections_present_even_when_empty():
    bundle = _build_bundle()  # no clinical items
    comp = bundle["entry"][0]["resource"]
    section_loincs = {
        s["code"]["coding"][0]["code"]
        for s in comp["section"]
        if s.get("code", {}).get("coding")
    }
    assert "11450-4" in section_loincs   # Problems
    assert "48765-2" in section_loincs   # Allergies
    assert "10160-0" in section_loincs   # Medications


def test_empty_sections_have_empty_reason():
    bundle = _build_bundle()
    comp = bundle["entry"][0]["resource"]
    for section in comp["section"]:
        if not section.get("entry"):
            assert "emptyReason" in section, f"Section {section.get('title')} missing emptyReason"


# ── Problems ──────────────────────────────────────────────────────────────────

def test_condition_created_for_active_problem():
    problems = [ActiveProblem(
        text="Schenkelhalsfraktur rechts",
        icd10_suggested="S72.00",
        source_ids=["P001-D004"],
        quote="Schenkelhalsfraktur re.",
        quote_verified=True,
        code_validated=True,
    )]
    bundle = _build_bundle(problems_active=problems)
    resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "Condition" in resource_types


def test_condition_clinical_status_is_active():
    problems = [ActiveProblem(text="Hypertonie", source_ids=["P001-D004"], quote="")]
    bundle = _build_bundle(problems_active=problems)
    conditions = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Condition"]
    assert conditions[0]["clinicalStatus"]["coding"][0]["code"] == "active"


# ── Allergies ─────────────────────────────────────────────────────────────────

def test_allergy_intolerance_created():
    allergies = [AllergyIntolerance(
        substance="Penicillin",
        reaction="Urtikaria",
        criticality=Criticality.high,
        verification=Verification.confirmed,
        source_ids=["P001-D005"],
        quote="Pen-Allergie",
        quote_verified=True,
        code_validated=True,
    )]
    bundle = _build_bundle(allergies_intolerances=allergies)
    resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "AllergyIntolerance" in resource_types


def test_allergy_criticality_high_mapped():
    allergies = [AllergyIntolerance(
        substance="Latex", criticality=Criticality.high,
        verification=Verification.confirmed,
        source_ids=["P001-D006"], quote=""
    )]
    bundle = _build_bundle(allergies_intolerances=allergies)
    ai = next(e["resource"] for e in bundle["entry"]
              if e["resource"]["resourceType"] == "AllergyIntolerance")
    assert ai["criticality"] == "high"


# ── Medications ───────────────────────────────────────────────────────────────

def test_medication_statement_created():
    meds = [MedicationAtDischarge(
        active_ingredient="Ramipril",
        atc_suggested="C09AA05",
        dose="5mg 1-0-0",
        status=MedStatus.unchanged,
        source_ids=["P001-D004"],
        quote="Ramipril 5mg",
        quote_verified=True,
        code_validated=True,
    )]
    bundle = _build_bundle(medication_at_discharge=meds)
    resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "MedicationStatement" in resource_types
    assert "Medication" in resource_types


# ── Provenance ────────────────────────────────────────────────────────────────

def test_provenance_created_for_item_with_source():
    problems = [ActiveProblem(
        text="Hypertonie", source_ids=["P001-D004"], quote="Hypertonie",
        quote_verified=True, code_validated=True,
    )]
    bundle = _build_bundle(problems_active=problems)
    resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "Provenance" in resource_types


# ── AI notice ──────────────────────────────────────────────────────────────────

def test_ai_notice_in_composition():
    bundle = _build_bundle()
    comp = bundle["entry"][0]["resource"]
    extensions = {e["url"]: e for e in comp.get("extension", [])}
    assert "http://ips-hackathon/extensions/ai-generated" in extensions
    assert extensions["http://ips-hackathon/extensions/ai-generated"]["valueBoolean"] is True


def test_bundle_is_valid_json():
    bundle = _build_bundle()
    dumped = json.dumps(bundle)
    loaded = json.loads(dumped)
    assert loaded["resourceType"] == "Bundle"

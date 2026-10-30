"""Tests for quote verification."""

from pipeline.models import ActiveProblem, AllergyIntolerance, ExtractionIntermediate
from pipeline.verify_quotes import verify_quotes
from datetime import datetime, timezone


def _make_intermediate(problems=None, allergies=None, excluded=None) -> ExtractionIntermediate:
    from pipeline.models import IncludedSection, ExcludedItem, ExclusionReason
    return ExtractionIntermediate(
        patient_token="PT-abc123",
        extraction_model="test",
        extraction_timestamp=datetime.now(timezone.utc),
        included=IncludedSection(
            problems_active=problems or [],
            allergies_intolerances=allergies or [],
        ),
        excluded=excluded or [],
    )


DOCS = [
    {
        "id": "P001-D004",
        "text": "Medialer Schenkelhalsfraktur re. bestätigt (Garden III). Pat. kooperativ.",
    },
    {
        "id": "P001-D005",
        "text": "Pat. berichtet, sie verträge kein ASS – sei ihr immer schlecht geworden.",
    },
]


def test_exact_quote_verified():
    problem = ActiveProblem(
        text="Schenkelhalsfraktur",
        source_ids=["P001-D004"],
        quote="Medialer Schenkelhalsfraktur re. bestätigt (Garden III).",
    )
    inter = _make_intermediate(problems=[problem])
    inter, failed = verify_quotes(inter, DOCS)
    assert inter.included.problems_active[0].quote_verified is True
    assert len(failed) == 0


def test_quote_not_found_in_doc():
    problem = ActiveProblem(
        text="Herzinsuffizienz",
        source_ids=["P001-D004"],
        quote="Chronische Herzinsuffizienz EF 35%",  # not in docs
    )
    inter = _make_intermediate(problems=[problem])
    inter, failed = verify_quotes(inter, DOCS)
    assert inter.included.problems_active[0].quote_verified is False
    assert len(failed) == 1


def test_quote_found_in_second_source_doc():
    allergy = AllergyIntolerance(
        substance="ASS",
        source_ids=["P001-D004", "P001-D005"],
        quote="sie verträge kein ASS",
    )
    inter = _make_intermediate(allergies=[allergy])
    inter, failed = verify_quotes(inter, DOCS)
    assert inter.included.allergies_intolerances[0].quote_verified is True
    assert len(failed) == 0


def test_empty_quote_is_unverified_but_not_failed():
    problem = ActiveProblem(
        text="Hypertonie",
        source_ids=["P001-D004"],
        quote="",  # no quote provided
    )
    inter = _make_intermediate(problems=[problem])
    inter, failed = verify_quotes(inter, DOCS)
    assert inter.included.problems_active[0].quote_verified is False
    assert len(failed) == 0  # no quote = not in failed list


def test_case_insensitive_match():
    problem = ActiveProblem(
        text="Fraktur",
        source_ids=["P001-D004"],
        quote="MEDIALER SCHENKELHALSFRAKTUR RE.",
    )
    inter = _make_intermediate(problems=[problem])
    inter, failed = verify_quotes(inter, DOCS)
    assert inter.included.problems_active[0].quote_verified is True


def test_verification_summary_recomputed():
    p1 = ActiveProblem(text="A", source_ids=["P001-D004"],
                       quote="Medialer Schenkelhalsfraktur")
    p2 = ActiveProblem(text="B", source_ids=["P001-D004"],
                       quote="DOES NOT EXIST IN ANY DOCUMENT")
    inter = _make_intermediate(problems=[p1, p2])
    inter, failed = verify_quotes(inter, DOCS)
    assert inter.verification_summary.quote_verified == 1
    assert inter.verification_summary.quote_failed == 1

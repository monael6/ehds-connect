"""
terminology.py – Step 5: Terminology validation (deterministic).

Validates ICD-10-GM, ATC, and SNOMED CT codes suggested by the LLM
against local lookup tables (terminology/ directory).

Policy:
  - If a suggested code IS in the lookup → accepted, code_validated = True,
    display text taken from the lookup (not the LLM's text).
  - If a suggested code is NOT in the lookup → code set to null,
    code_validated = False, item keeps its .text as code.text only.
  - Unknown codes NEVER silently pass into the FHIR Bundle.

The lookup tables are intentionally small for the hackathon (covering the
codes used in the synthetic dataset). Production would use a full
terminology server (FHIR $validate-code operation).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pipeline.models import (
    ActiveProblem,
    AllergyIntolerance,
    ExtractionIntermediate,
    MedicalDevice,
    MedicationAtDischarge,
    MedicationStopped,
    PastHistory,
    Procedure,
)

logger = logging.getLogger(__name__)

_TERMINOLOGY_DIR = Path(__file__).parent.parent / "terminology"


def _load_lookup(filename: str) -> dict[str, str]:
    path = _TERMINOLOGY_DIR / filename
    if not path.exists():
        logger.warning("Terminology file not found: %s", path)
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# Lazy-loaded singletons
_icd10: dict[str, str] | None = None
_atc: dict[str, str] | None = None
_snomed: dict[str, str] | None = None


def _get_icd10() -> dict[str, str]:
    global _icd10
    if _icd10 is None:
        _icd10 = _load_lookup("icd10_lookup.json")
    return _icd10


def _get_atc() -> dict[str, str]:
    global _atc
    if _atc is None:
        _atc = _load_lookup("atc_lookup.json")
    return _atc


def _get_snomed() -> dict[str, str]:
    global _snomed
    if _snomed is None:
        _snomed = _load_lookup("snomed_stub.json")
    return _snomed


class ValidatedCode:
    """Result of a single code validation."""
    __slots__ = ("system", "code", "display", "validated")

    def __init__(self, system: str, code: str | None, display: str, validated: bool) -> None:
        self.system = system
        self.code = code
        self.display = display
        self.validated = validated


def validate_icd10(code: str | None, fallback_text: str) -> ValidatedCode:
    if not code:
        return ValidatedCode("http://hl7.org/fhir/sid/icd-10", None, fallback_text, False)
    lookup = _get_icd10()
    # Try exact match, then with GM suffix stripped
    display = lookup.get(code) or lookup.get(code.rstrip("!+*"))
    if display:
        return ValidatedCode("http://hl7.org/fhir/sid/icd-10", code, display, True)
    logger.debug("ICD-10 code not found in lookup: %s", code)
    return ValidatedCode("http://hl7.org/fhir/sid/icd-10", None, fallback_text, False)


def validate_atc(code: str | None, fallback_text: str) -> ValidatedCode:
    if not code:
        return ValidatedCode("http://www.whocc.no/atc", None, fallback_text, False)
    lookup = _get_atc()
    display = lookup.get(code)
    if display:
        return ValidatedCode("http://www.whocc.no/atc", code, display, True)
    logger.debug("ATC code not found in lookup: %s", code)
    return ValidatedCode("http://www.whocc.no/atc", None, fallback_text, False)


def validate_snomed(code: str | None, fallback_text: str) -> ValidatedCode:
    if not code:
        return ValidatedCode("http://snomed.info/sct", None, fallback_text, False)
    lookup = _get_snomed()
    display = lookup.get(code)
    if display:
        return ValidatedCode("http://snomed.info/sct", code, display, True)
    logger.debug("SNOMED code not found in lookup: %s", code)
    return ValidatedCode("http://snomed.info/sct", None, fallback_text, False)


def validate_terminology(intermediate: ExtractionIntermediate) -> ExtractionIntermediate:
    """
    Validate all suggested codes in the intermediate JSON.
    Mutates the intermediate in-place (sets code_validated flags).
    Returns the updated intermediate.
    """
    validated_count = 0
    rejected_count = 0

    def _check_icd(item: Any, text_attr: str = "text") -> None:
        nonlocal validated_count, rejected_count
        code = getattr(item, "icd10_suggested", None)
        result = validate_icd10(code, getattr(item, text_attr, ""))
        if result.validated:
            validated_count += 1
        else:
            if code:
                rejected_count += 1
                logger.info("ICD-10 %s rejected → text-only for: %s", code, getattr(item, text_attr, "")[:60])
            item.icd10_suggested = None

    def _check_atc(item: Any) -> None:
        nonlocal validated_count, rejected_count
        code = getattr(item, "atc_suggested", None)
        text = getattr(item, "active_ingredient", "") or getattr(item, "text", "")
        result = validate_atc(code, text)
        if result.validated:
            validated_count += 1
        else:
            if code:
                rejected_count += 1
                logger.info("ATC %s rejected → text-only for: %s", code, text[:60])
            item.atc_suggested = None

    # Problems
    for item in intermediate.included.problems_active:
        _check_icd(item)
        if item.icd10_suggested:
            item.code_validated = True

    for item in intermediate.included.past_history:
        _check_icd(item)
        if item.icd10_suggested:
            item.code_validated = True

    # Medications
    for item in intermediate.included.medication_at_discharge:
        _check_atc(item)
        if item.atc_suggested:
            item.code_validated = True

    for item in intermediate.included.medication_stopped:
        _check_atc(item)
        if item.atc_suggested:
            item.code_validated = True

    # Allergies — no standard code in the simplified dataset, mark as validated if text present
    for item in intermediate.included.allergies_intolerances:
        item.code_validated = bool(item.substance)

    # Procedures, devices, results — no codes to validate for now
    for item in (
        intermediate.included.procedures
        + intermediate.included.medical_devices
        + intermediate.included.key_results
        + intermediate.included.immunizations
    ):
        item.code_validated = True  # text-only, no code required

    intermediate.recompute_summary()
    logger.info(
        "Terminology validation: %d validated, %d rejected/unknown",
        validated_count,
        rejected_count,
    )
    return intermediate

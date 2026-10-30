"""
models.py – Pydantic models for the intermediate extraction JSON.

This is the contract between the LLM (Step 3) and all downstream
deterministic steps (quote verification, terminology, FHIR mapping).

The LLM fills ONLY the *_suggested fields and text/quote fields.
quote_verified and code_validated are set by deterministic steps.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class Criticality(str, Enum):
    low = "low"
    high = "high"
    unknown = "unknown"


class Verification(str, Enum):
    confirmed = "confirmed"
    unconfirmed = "unconfirmed"


class MedStatus(str, Enum):
    new = "new"
    changed = "changed"
    unchanged = "unchanged"


class ExclusionReason(str, Enum):
    ruled_out = "ruled_out"
    family_history = "family_history"
    unconfirmed = "unconfirmed"
    negated = "negated"


# ── Base item ─────────────────────────────────────────────────────────────────

class BaseItem(BaseModel):
    source_ids: list[str] = Field(default_factory=list)
    quote: str = ""                     # verbatim text from the source doc
    quote_verified: bool = False        # set by verify_quotes.py
    code_validated: bool = False        # set by terminology.py


# ── Included items ────────────────────────────────────────────────────────────

class ActiveProblem(BaseItem):
    text: str
    icd10_suggested: str | None = None
    snomed_suggested: str | None = None
    onset: str | None = None            # YYYY-MM-DD or YYYY


class PastHistory(BaseItem):
    text: str
    icd10_suggested: str | None = None
    resolved: str | None = None         # YYYY or null


class AllergyIntolerance(BaseItem):
    substance: str
    reaction: str | None = None
    criticality: Criticality = Criticality.unknown
    verification: Verification = Verification.unconfirmed


class MedicationAtDischarge(BaseItem):
    active_ingredient: str
    atc_suggested: str | None = None
    dose: str | None = None
    status: MedStatus = MedStatus.unchanged


class MedicationStopped(BaseItem):
    active_ingredient: str
    atc_suggested: str | None = None
    reason: str | None = None


class Procedure(BaseItem):
    text: str
    date: str | None = None             # YYYY-MM-DD


class MedicalDevice(BaseItem):
    text: str
    since: str | None = None            # YYYY-MM-DD


class Immunization(BaseItem):
    vaccine: str
    date: str | None = None


class KeyResult(BaseItem):
    text: str
    value: str | None = None
    date: str | None = None


# ── Excluded items ────────────────────────────────────────────────────────────

class ExcludedItem(BaseItem):
    text: str
    reason: ExclusionReason
    detail: str | None = None           # free-text explanation


# ── Verification summary ──────────────────────────────────────────────────────

class VerificationSummary(BaseModel):
    total_items: int = 0
    quote_verified: int = 0
    quote_failed: int = 0
    code_validated: int = 0
    code_unvalidated: int = 0


# ── Top-level intermediate document ──────────────────────────────────────────

class IncludedSection(BaseModel):
    problems_active: list[ActiveProblem] = Field(default_factory=list)
    past_history: list[PastHistory] = Field(default_factory=list)
    allergies_intolerances: list[AllergyIntolerance] = Field(default_factory=list)
    medication_at_discharge: list[MedicationAtDischarge] = Field(default_factory=list)
    medication_stopped: list[MedicationStopped] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    medical_devices: list[MedicalDevice] = Field(default_factory=list)
    immunizations: list[Immunization] = Field(default_factory=list)
    key_results: list[KeyResult] = Field(default_factory=list)


class ExtractionIntermediate(BaseModel):
    patient_token: str                  # pseudonymized token, never real name
    extraction_model: str
    extraction_timestamp: datetime
    pseudonymized: bool = True
    included: IncludedSection = Field(default_factory=IncludedSection)
    excluded: list[ExcludedItem] = Field(default_factory=list)
    verification_summary: VerificationSummary = Field(default_factory=VerificationSummary)

    def all_included_items(self) -> list[BaseItem]:
        """Flat list of all included items (for batch processing)."""
        sec = self.included
        result: list[Any] = []
        for field in [
            sec.problems_active, sec.past_history, sec.allergies_intolerances,
            sec.medication_at_discharge, sec.medication_stopped, sec.procedures,
            sec.medical_devices, sec.immunizations, sec.key_results,
        ]:
            result.extend(field)
        return result

    def recompute_summary(self) -> None:
        items = self.all_included_items() + self.excluded
        total = len(items)
        verified = sum(1 for i in items if i.quote_verified)
        failed = sum(1 for i in items if not i.quote_verified and i.quote)
        validated = sum(1 for i in self.all_included_items() if i.code_validated)
        unvalidated = sum(
            1 for i in self.all_included_items()
            if not i.code_validated and (
                getattr(i, "icd10_suggested", None)
                or getattr(i, "atc_suggested", None)
                or getattr(i, "snomed_suggested", None)
            )
        )
        self.verification_summary = VerificationSummary(
            total_items=total,
            quote_verified=verified,
            quote_failed=failed,
            code_validated=validated,
            code_unvalidated=unvalidated,
        )

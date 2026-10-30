"""Structured interpretation of a request ("spec").

The parser (engine/parser.py) turns the plain-English definitions of a request
into this spec; the query generator (engine/query.py) turns the spec into SQL.
Nothing is written by hand per request.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Criterion(BaseModel):
    """One condition a patient (or stay) must meet."""
    type: Literal["condition", "medication", "observation", "encounter", "sex", "age", "region", "data_holder"]
    codes: list[str] = Field(default_factory=list, description="code prefixes, e.g. E11, A10BA, 4548-4")
    term: str | None = Field(None, description="plain-English term from the request")
    op: Literal[">", ">=", "<", "<=", "=", "!="] | None = None
    value: float | str | None = None
    value_max: float | None = None
    observation_select: Literal["any", "latest", "max", "min", "mean"] = "any"
    inpatient: bool | None = None
    encounter_type: str | None = None
    primary_icd10: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    active_on: str | None = Field(None, description="medication active on this date (start <= d, end empty or >= d)")
    negate: bool = False


class GroupBy(BaseModel):
    dimension: Literal["sex", "age_group", "data_holder", "region", "year", "medication", "condition"]
    # age_group bins as [lo, hi] inclusive; hi None = open end
    bins: list[tuple[int, int | None]] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    # categories that must always be shown (empty groups too)
    categories: list[str] = Field(default_factory=list)
    # for dimension medication/condition: one group per criterion
    members: list[Criterion] = Field(default_factory=list)


class ValueSpec(BaseModel):
    source: Literal["observation", "age", "length_of_stay", "encounter_count"]
    codes: list[str] = Field(default_factory=list)
    select: Literal["latest", "mean", "max", "min", "first"] = "latest"


class Metric(BaseModel):
    id: str
    label: str
    kind: Literal["count", "percentage", "mean"]
    unit: Literal["patients", "encounters"] = "patients"
    criteria: list[Criterion] = Field(default_factory=list)     # who (or which stays) are counted
    denominator: list[Criterion] = Field(default_factory=list)  # percentage: base population
    value: ValueSpec | None = None                              # mean: what is averaged
    group_by: list[GroupBy] | None = None                       # overrides spec.group_by
    source_text: str | None = None


class Spec(BaseModel):
    request_id: str
    population: list[Criterion] = Field(default_factory=list)  # cohort (SPE) / subject of the question
    group_by: list[GroupBy] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    record_types: list[str] = Field(default_factory=list)     # for SPE
    spe_observation_codes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    term_mapping: list[dict] = Field(default_factory=list)

"""
pseudonymize.py – Step 2: Pseudonymization before any LLM call.

Replaces identifiable entities in document texts with stable tokens:
  - Patient name        → [PAT-NAME]
  - Date of birth       → [PAT-DOB]
  - Insurance number    → [PAT-INSID]
  - Facility names      → [FAC-001], [FAC-002], …
  - Person names (staff)→ [PERS-001], [PERS-002], …  (regex-based heuristic)

The mapping table is kept IN MEMORY ONLY and is never written to disk.
It is returned alongside the pseudonymized texts so that Step 6 (FHIR mapping)
can re-identify the patient resource from the real demographics.

Date shifting: if shift_days is non-zero, all ISO dates and German-format dates
are shifted by that many days (optional, off by default for synthetic mode).

Usage:
    from pipeline.pseudonymize import pseudonymize_documents

    pseudo_docs, mapping = pseudonymize_documents(
        patient_json=patient,
        documents=docs,
        shift_days=0,
    )
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from typing import Any


# ── Regex patterns for identifiable data ──────────────────────────────────────

# Austrian insurance number (real: NNNN-NNNNNN; synthetic: FAKE-NNNN-NNNNNN)
_INSURANCE_RE = re.compile(r"\b(?:FAKE-)?[A-Z0-9]{4}-\d{6,}\b")

# ISO dates: YYYY-MM-DD and YYYY-MM-DDTHH:MM
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?:T\d{2}:\d{2})?\b")

# German-format dates: DD.MM.YYYY and DD.MM.YYYY (with optional day-of-week)
_DE_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")

# "geb. DD.MM.YYYY" or "*DD.MM.YYYY"
_DOB_INLINE_RE = re.compile(r"(?:geb\.\s*|(?<=\*))\d{1,2}\.\d{1,2}\.\d{4}")

# Names in "Nachname Vorname" or "Dr. Vorname Nachname" patterns (heuristic)
_DR_NAME_RE = re.compile(
    r"\b(?:Dr\.|OA|FA|DGKP|Mag\.|Prof\.)\s+[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*"
)


@dataclass
class PseudoMapping:
    """
    In-memory mapping between real values and pseudonymized tokens.
    NEVER serialise this to disk or logs.
    """
    patient_token: str                          # e.g. "PT-a3f9b2"
    real_name: str
    real_dob: str
    real_insurance: str
    facility_map: dict[str, str] = field(default_factory=dict)   # real → token
    person_map: dict[str, str] = field(default_factory=dict)     # real → token
    _fac_counter: int = field(default=0, repr=False)
    _pers_counter: int = field(default=0, repr=False)

    def facility_token(self, real: str) -> str:
        if real not in self.facility_map:
            self._fac_counter += 1
            self.facility_map[real] = f"[FAC-{self._fac_counter:03d}]"
        return self.facility_map[real]

    def person_token(self, real: str) -> str:
        if real not in self.person_map:
            self._pers_counter += 1
            self.person_map[real] = f"[PERS-{self._pers_counter:03d}]"
        return self.person_map[real]


def _make_patient_token() -> str:
    return "PT-" + secrets.token_hex(3)


def _shift_iso_date(m: re.Match, shift_days: int) -> str:
    if shift_days == 0:
        return m.group(0)
    from datetime import date, timedelta
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        shifted = d + timedelta(days=shift_days)
        original = m.group(0)
        # Preserve time part if present
        time_part = original[10:] if len(original) > 10 else ""
        return shifted.isoformat() + time_part
    except ValueError:
        return m.group(0)


def _shift_de_date(m: re.Match, shift_days: int) -> str:
    if shift_days == 0:
        return m.group(0)
    from datetime import date, timedelta
    try:
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        shifted = d + timedelta(days=shift_days)
        return f"{shifted.day:02d}.{shifted.month:02d}.{shifted.year}"
    except ValueError:
        return m.group(0)


# Known facility names from the synthetic dataset (can be extended)
_KNOWN_FACILITIES = [
    "Landesklinikum Musterstadt",
    "Ordination Dr. Elfriede Strohmayr, Musterstadt",
    "Ordination Dr. Petra Holzmann, Graz-Süd",
    "Ordination Dr. Andreas Weiss, Wels",
    "Ordination Dr. Stefan Huber, Innsbruck",
    "Krankenhaus St. Pölten Süd",
    "LKH Graz Süd-West",
    "Klinikum Linz-Nord",
    "Kinderkrankenhaus Musterstadt",
    "Ambulatorium Atemwegszentrum Wien-Nord",
    "Universitätsklinik Salzburg",
    "Landeskrankenhaus Innsbruck",
    "Ärztlicher Bereitschaftsdienst Wien 22",
]


def _pseudonymize_text(
    text: str,
    patient: dict[str, Any],
    mapping: PseudoMapping,
    shift_days: int,
) -> str:
    result = text

    # 1. Replace patient name (both orders)
    vorname = patient.get("vorname", "")
    nachname = patient.get("nachname", "")
    if vorname and nachname:
        # "Nachname Vorname" and "Vorname Nachname"
        for pat_name in [f"{nachname} {vorname}", f"{vorname} {nachname}", nachname, vorname]:
            if len(pat_name) > 3:  # avoid replacing very short strings
                result = result.replace(pat_name, "[PAT-NAME]")

    # 2. Replace insurance number
    ins = patient.get("fiktive_versicherungsnummer", "")
    if ins:
        result = result.replace(ins, "[PAT-INSID]")
    result = _INSURANCE_RE.sub("[PAT-INSID]", result)

    # 3. Replace date of birth inline (geb. or *)
    dob = patient.get("geburtsdatum", "")
    if dob:
        # Convert YYYY-MM-DD to DD.MM.YYYY for German text
        try:
            y, mo, d = dob.split("-")
            de_dob = f"{int(d):02d}.{int(mo):02d}.{y}"
            result = result.replace(de_dob, "[PAT-DOB]")
        except ValueError:
            pass
        result = result.replace(dob, "[PAT-DOB]")
    result = _DOB_INLINE_RE.sub("[PAT-DOB]", result)

    # 4. Shift or replace dates
    if shift_days != 0:
        result = _ISO_DATE_RE.sub(lambda m: _shift_iso_date(m, shift_days), result)
        result = _DE_DATE_RE.sub(lambda m: _shift_de_date(m, shift_days), result)

    # 5. Replace known facility names
    for facility in _KNOWN_FACILITIES:
        if facility in result:
            result = result.replace(facility, mapping.facility_token(facility))

    # 6. Replace Dr./OA/DGKP person names (heuristic)
    def _replace_person(m: re.Match) -> str:
        return mapping.person_token(m.group(0))

    result = _DR_NAME_RE.sub(_replace_person, result)

    return result


def pseudonymize_documents(
    patient_json: dict[str, Any],
    documents: list[dict[str, Any]],
    shift_days: int = 0,
) -> tuple[list[dict[str, Any]], PseudoMapping]:
    """
    Pseudonymize a list of document dicts.

    Returns:
        pseudo_docs: list of document dicts with .text replaced
        mapping:     PseudoMapping object (keep in memory only!)
    """
    mapping = PseudoMapping(
        patient_token=_make_patient_token(),
        real_name=f"{patient_json.get('vorname','')} {patient_json.get('nachname','')}".strip(),
        real_dob=patient_json.get("geburtsdatum", ""),
        real_insurance=patient_json.get("fiktive_versicherungsnummer", ""),
    )

    pseudo_docs: list[dict[str, Any]] = []
    for doc in documents:
        pseudo_doc = dict(doc)  # shallow copy; we only replace .text
        pseudo_doc["text"] = _pseudonymize_text(
            doc.get("text", ""), patient_json, mapping, shift_days
        )
        # Also pseudonymize author/einrichtung fields (less critical but good practice)
        for field_name in ("einrichtung", "autor_rolle"):
            val = doc.get(field_name, "")
            if val:
                for facility in _KNOWN_FACILITIES:
                    if facility in val:
                        pseudo_doc[field_name] = val.replace(
                            facility, mapping.facility_token(facility)
                        )
        pseudo_docs.append(pseudo_doc)

    return pseudo_docs, mapping


def redact_for_log(text: str, mapping: PseudoMapping) -> str:
    """Ensure no real patient data leaks into a log string."""
    result = text
    result = result.replace(mapping.real_name, "[PAT-NAME]")
    result = result.replace(mapping.real_dob, "[PAT-DOB]")
    result = result.replace(mapping.real_insurance, "[PAT-INSID]")
    for real, token in mapping.facility_map.items():
        result = result.replace(real, token)
    return result

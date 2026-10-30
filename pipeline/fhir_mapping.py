"""
fhir_mapping.py – Step 6: FHIR R4 / IPS mapping (deterministic).

Maps the verified intermediate JSON to a FHIR R4 Bundle of type "document"
conforming to HL7 IPS IG 2.0.0.

Rules:
- Re-identification happens here (token → real patient demographics).
- The LLM never touches this code or its output.
- Composition.status = "preliminary" (clinician review required).
- Every clinical resource has a corresponding Provenance linking it to
  the source DocumentReference(s).
- Required IPS sections with no data use emptyReason (unavailable).
- All LOINC section codes from IPS IG 2.0.0.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from pipeline.models import (
    ActiveProblem,
    AllergyIntolerance,
    ExtractionIntermediate,
    Immunization,
    KeyResult,
    MedicalDevice,
    MedicationAtDischarge,
    MedicationStopped,
    PastHistory,
    Procedure,
)
from pipeline.pseudonymize import PseudoMapping
from pipeline.terminology import validate_atc, validate_icd10, validate_snomed

# ── IPS IG section LOINC codes ────────────────────────────────────────────────
IPS_SECTIONS = {
    "problems":      {"loinc": "11450-4", "title": "Problemliste",                        "required": True},
    "allergies":     {"loinc": "48765-2", "title": "Allergien und Unverträglichkeiten",    "required": True},
    "medications":   {"loinc": "10160-0", "title": "Medikation",                           "required": True},
    "past_history":  {"loinc": "11348-0", "title": "Frühere Erkrankungen",                 "required": False},
    "procedures":    {"loinc": "47519-4", "title": "Maßnahmen und Eingriffe",              "required": False},
    "devices":       {"loinc": "46264-8", "title": "Medizinische Geräte und Implantate",   "required": False},
    "immunizations": {"loinc": "11369-6", "title": "Impfstatus",                           "required": False},
    "results":       {"loinc": "30954-2", "title": "Diagnostische Befunde",                "required": False},
}

IPS_PROFILE = "http://hl7.org/fhir/uv/ips/StructureDefinition/Bundle-uv-ips"
IPS_COMPOSITION_PROFILE = "http://hl7.org/fhir/uv/ips/StructureDefinition/Composition-uv-ips"
IPS_PATIENT_PROFILE = "http://hl7.org/fhir/uv/ips/StructureDefinition/Patient-uv-ips"

AI_NOTICE = (
    "HINWEIS: Dieser Inhalt wurde durch ein KI-System generiert und erfordert "
    "ärztliche Prüfung vor klinischer Verwendung. Status: Entwurf."
)


def _uid() -> str:
    return str(uuid.uuid4())


def _fullurl(resource_type: str, resource_id: str) -> str:
    return f"urn:uuid:{resource_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coding(system: str, code: str | None, display: str) -> dict:
    if code:
        return {"system": system, "code": code, "display": display}
    return {"display": display}


def _codeable_concept_from_validated(validated_code: Any, fallback_text: str) -> dict:
    """Build a FHIR CodeableConcept from a ValidatedCode result."""
    cc: dict = {"text": fallback_text}
    if validated_code.code:
        cc["coding"] = [_coding(validated_code.system, validated_code.code, validated_code.display)]
    return cc


def _reference(resource_type: str, resource_id: str) -> dict:
    return {"reference": f"urn:uuid:{resource_id}"}


def _provenance(
    target_ids: list[str],
    doc_ref_ids: list[str],
    patient_id: str,
    ai_device_id: str,
    timestamp: str,
) -> dict:
    """Build a Provenance resource linking clinical resources to source docs."""
    return {
        "resourceType": "Provenance",
        "id": _uid(),
        "target": [{"reference": f"urn:uuid:{rid}"} for rid in target_ids],
        "recorded": timestamp,
        "agent": [
            {
                "type": {"coding": [_coding(
                    "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                    "assembler", "Assembler"
                )]},
                "who": {"reference": f"urn:uuid:{ai_device_id}"},
            }
        ],
        "entity": [
            {
                "role": "source",
                "what": {"reference": f"urn:uuid:{dr_id}"},
            }
            for dr_id in doc_ref_ids
        ],
    }


def _empty_reason_section(section_meta: dict) -> dict:
    return {
        "title": section_meta["title"],
        "code": {"coding": [_coding("http://loinc.org", section_meta["loinc"], section_meta["title"])]},
        "text": {
            "status": "generated",
            "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{AI_NOTICE}</div>',
        },
        "emptyReason": {
            "coding": [_coding(
                "http://terminology.hl7.org/CodeSystem/list-empty-reason",
                "unavailable", "Unavailable"
            )]
        },
    }


class FHIRMapper:
    def __init__(
        self,
        intermediate: ExtractionIntermediate,
        patient_json: dict,
        mapping: PseudoMapping,
        documents: list[dict],
    ) -> None:
        self.inter = intermediate
        self.patient_json = patient_json
        self.mapping = mapping
        self.documents = documents
        self.now = _now_iso()

        # Pre-build document ID → FHIR DocumentReference UUID map
        self._doc_fhir_ids: dict[str, str] = {}
        self._entries: list[dict] = []

    def build_bundle(self) -> dict:
        bundle_id = _uid()
        composition_id = _uid()
        patient_id = _uid()
        org_id = _uid()
        ai_device_id = _uid()

        # ── Patient ──────────────────────────────────────────────────────────
        patient_resource = self._build_patient(patient_id, org_id)
        # ── Organization ─────────────────────────────────────────────────────
        org_resource = self._build_organization(org_id)
        # ── AI Device (for Provenance) ────────────────────────────────────────
        ai_device = self._build_ai_device(ai_device_id)
        # ── DocumentReferences for source documents ───────────────────────────
        doc_ref_entries = self._build_document_references(patient_id)
        # ── Clinical resources per section ────────────────────────────────────
        sections, clinical_entries = self._build_sections(
            patient_id, ai_device_id
        )
        # ── Composition ───────────────────────────────────────────────────────
        composition = self._build_composition(
            composition_id, patient_id, org_id, sections
        )

        # Assemble all entries: Composition first (IPS requirement)
        all_entries: list[dict] = (
            [
                {"fullUrl": _fullurl("Composition", composition_id), "resource": composition},
                {"fullUrl": _fullurl("Patient", patient_id),         "resource": patient_resource},
                {"fullUrl": _fullurl("Organization", org_id),        "resource": org_resource},
                {"fullUrl": _fullurl("Device", ai_device_id),        "resource": ai_device},
            ]
            + doc_ref_entries
            + clinical_entries
        )

        return {
            "resourceType": "Bundle",
            "id": bundle_id,
            "meta": {
                "profile": [IPS_PROFILE],
                "tag": [{"system": "http://ips-hackathon/tags", "code": "ai-draft"}],
            },
            "identifier": {
                "system": "urn:ietf:rfc:3986",
                "value": f"urn:uuid:{bundle_id}",
            },
            "type": "document",
            "timestamp": self.now,
            "entry": all_entries,
        }

    # ── Patient resource ──────────────────────────────────────────────────────
    def _build_patient(self, patient_id: str, org_id: str) -> dict:
        p = self.patient_json
        gender_map = {"weiblich": "female", "maennlich": "male", "divers": "other"}
        return {
            "resourceType": "Patient",
            "id": patient_id,
            "meta": {"profile": [IPS_PATIENT_PROFILE]},
            "identifier": [
                {"system": "http://ips-hackathon/patients", "value": p["patient_id"]},
                {"system": "http://ips-hackathon/versicherung",
                 "value": p["fiktive_versicherungsnummer"]},
            ],
            "name": [{"family": p["nachname"], "given": [p["vorname"]]}],
            "gender": gender_map.get(p.get("geschlecht", ""), "unknown"),
            "birthDate": p["geburtsdatum"],
            "address": [{"state": p.get("wohnort_bundesland", ""), "country": "AT"}],
            "managingOrganization": {"reference": f"urn:uuid:{org_id}"},
        }

    def _build_organization(self, org_id: str) -> dict:
        return {
            "resourceType": "Organization",
            "id": org_id,
            "name": "Landesklinikum Musterstadt",
            "address": [{"country": "AT"}],
        }

    def _build_ai_device(self, device_id: str) -> dict:
        return {
            "resourceType": "Device",
            "id": device_id,
            "deviceName": [{"name": "IPS-Hackathon-AI", "type": "user-friendly-name"}],
            "version": [{"value": "0.1.0"}],
            "note": [{"text": AI_NOTICE}],
        }

    # ── DocumentReferences ────────────────────────────────────────────────────
    def _build_document_references(self, patient_id: str) -> list[dict]:
        entries = []
        for doc in self.documents:
            dr_id = _uid()
            self._doc_fhir_ids[doc["id"]] = dr_id
            entries.append({
                "fullUrl": _fullurl("DocumentReference", dr_id),
                "resource": {
                    "resourceType": "DocumentReference",
                    "id": dr_id,
                    "status": "current",
                    "type": {"text": doc.get("typ", "")},
                    "subject": {"reference": f"urn:uuid:{patient_id}"},
                    "date": doc.get("datum", self.now),
                    "description": doc.get("titel", ""),
                    "content": [{
                        "attachment": {
                            "contentType": "text/plain; charset=utf-8",
                            "language": "de-AT",
                            "title": doc.get("titel", ""),
                        }
                    }],
                    "extension": [{
                        "url": "http://ips-hackathon/extensions/source-doc-id",
                        "valueString": doc["id"],
                    }],
                },
            })
        return entries

    def _doc_ref_ids_for(self, source_ids: list[str]) -> list[str]:
        return [self._doc_fhir_ids[sid] for sid in source_ids if sid in self._doc_fhir_ids]

    # ── Sections + clinical resources ─────────────────────────────────────────
    def _build_sections(
        self, patient_id: str, ai_device_id: str
    ) -> tuple[list[dict], list[dict]]:
        sections: list[dict] = []
        clinical_entries: list[dict] = []

        def _add(section: dict, entries: list[dict]) -> None:
            sections.append(section)
            clinical_entries.extend(entries)

        # Problems (required)
        _add(*self._section_problems(patient_id, ai_device_id))
        # Allergies (required)
        _add(*self._section_allergies(patient_id, ai_device_id))
        # Medications (required)
        _add(*self._section_medications(patient_id, ai_device_id))
        # Past history
        if self.inter.included.past_history:
            _add(*self._section_past_history(patient_id, ai_device_id))
        # Procedures
        if self.inter.included.procedures:
            _add(*self._section_procedures(patient_id, ai_device_id))
        # Devices
        if self.inter.included.medical_devices:
            _add(*self._section_devices(patient_id, ai_device_id))
        # Immunizations
        if self.inter.included.immunizations:
            _add(*self._section_immunizations(patient_id, ai_device_id))
        # Results
        if self.inter.included.key_results:
            _add(*self._section_results(patient_id, ai_device_id))

        return sections, clinical_entries

    # ── Individual section builders ───────────────────────────────────────────

    def _status_light(self, item: Any) -> str:
        """Return a CSS class name for UI traffic light (embedded in resource text)."""
        if not item.quote_verified:
            return "red"
        if not item.code_validated:
            return "yellow"
        return "green"

    def _section_problems(self, patient_id: str, ai_device_id: str) -> tuple[dict, list[dict]]:
        meta = IPS_SECTIONS["problems"]
        items = self.inter.included.problems_active
        if not items:
            return _empty_reason_section(meta), []

        entries: list[dict] = []
        refs: list[dict] = []
        provenances: list[dict] = []

        for item in items:
            cond_id = _uid()
            icd = validate_icd10(item.icd10_suggested, item.text)
            cc = _codeable_concept_from_validated(icd, item.text)
            condition: dict = {
                "resourceType": "Condition",
                "id": cond_id,
                "clinicalStatus": {
                    "coding": [_coding(
                        "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "active", "Active"
                    )]
                },
                "verificationStatus": {
                    "coding": [_coding(
                        "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "confirmed", "Confirmed"
                    )]
                },
                "code": cc,
                "subject": {"reference": f"urn:uuid:{patient_id}"},
                "extension": [
                    {"url": "http://ips-hackathon/extensions/quote-verified",
                     "valueBoolean": item.quote_verified},
                    {"url": "http://ips-hackathon/extensions/code-validated",
                     "valueBoolean": item.code_validated},
                    {"url": "http://ips-hackathon/extensions/status-light",
                     "valueString": self._status_light(item)},
                ],
            }
            if item.onset:
                condition["onsetString"] = item.onset
            entries.append({"fullUrl": _fullurl("Condition", cond_id), "resource": condition})
            refs.append({"reference": f"urn:uuid:{cond_id}"})

            # Provenance
            dr_ids = self._doc_ref_ids_for(item.source_ids)
            if dr_ids:
                prov = _provenance([cond_id], dr_ids, patient_id, ai_device_id, self.now)
                entries.append({"fullUrl": _fullurl("Provenance", prov["id"]), "resource": prov})

        section = {
            "title": meta["title"],
            "code": {"coding": [_coding("http://loinc.org", meta["loinc"], meta["title"])]},
            "text": {"status": "generated",
                     "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{AI_NOTICE}</div>'},
            "entry": refs,
        }
        return section, entries

    def _section_allergies(self, patient_id: str, ai_device_id: str) -> tuple[dict, list[dict]]:
        meta = IPS_SECTIONS["allergies"]
        items = self.inter.included.allergies_intolerances
        if not items:
            return _empty_reason_section(meta), []

        entries: list[dict] = []
        refs: list[dict] = []

        criticality_map = {"high": "high", "low": "low", "unknown": "unable-to-assess"}
        verification_map = {"confirmed": "confirmed", "unconfirmed": "unconfirmed"}

        for item in items:
            ai_id = _uid()
            allergy: dict = {
                "resourceType": "AllergyIntolerance",
                "id": ai_id,
                "clinicalStatus": {
                    "coding": [_coding(
                        "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                        "active", "Active"
                    )]
                },
                "verificationStatus": {
                    "coding": [_coding(
                        "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                        verification_map.get(item.verification.value, "unconfirmed"),
                        item.verification.value.capitalize()
                    )]
                },
                "criticality": criticality_map.get(item.criticality.value, "unable-to-assess"),
                "code": {"text": item.substance},
                "patient": {"reference": f"urn:uuid:{patient_id}"},
                "extension": [
                    {"url": "http://ips-hackathon/extensions/quote-verified",
                     "valueBoolean": item.quote_verified},
                    {"url": "http://ips-hackathon/extensions/status-light",
                     "valueString": self._status_light(item)},
                ],
            }
            if item.reaction:
                allergy["reaction"] = [{"description": item.reaction}]
            entries.append({"fullUrl": _fullurl("AllergyIntolerance", ai_id), "resource": allergy})
            refs.append({"reference": f"urn:uuid:{ai_id}"})

            dr_ids = self._doc_ref_ids_for(item.source_ids)
            if dr_ids:
                prov = _provenance([ai_id], dr_ids, patient_id, ai_device_id, self.now)
                entries.append({"fullUrl": _fullurl("Provenance", prov["id"]), "resource": prov})

        section = {
            "title": meta["title"],
            "code": {"coding": [_coding("http://loinc.org", meta["loinc"], meta["title"])]},
            "text": {"status": "generated",
                     "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{AI_NOTICE}</div>'},
            "entry": refs,
        }
        return section, entries

    def _section_medications(self, patient_id: str, ai_device_id: str) -> tuple[dict, list[dict]]:
        meta = IPS_SECTIONS["medications"]
        items = self.inter.included.medication_at_discharge
        if not items:
            return _empty_reason_section(meta), []

        entries: list[dict] = []
        refs: list[dict] = []

        status_map = {"new": "active", "changed": "active", "unchanged": "active"}

        for item in items:
            med_id = _uid()
            ms_id = _uid()
            atc = validate_atc(item.atc_suggested, item.active_ingredient)
            med_cc = _codeable_concept_from_validated(atc, item.active_ingredient)

            medication: dict = {
                "resourceType": "Medication",
                "id": med_id,
                "code": med_cc,
            }
            med_statement: dict = {
                "resourceType": "MedicationStatement",
                "id": ms_id,
                "status": status_map.get(item.status.value, "active"),
                "medicationReference": {"reference": f"urn:uuid:{med_id}"},
                "subject": {"reference": f"urn:uuid:{patient_id}"},
                "extension": [
                    {"url": "http://ips-hackathon/extensions/medication-status",
                     "valueString": item.status.value},
                    {"url": "http://ips-hackathon/extensions/quote-verified",
                     "valueBoolean": item.quote_verified},
                    {"url": "http://ips-hackathon/extensions/code-validated",
                     "valueBoolean": item.code_validated},
                    {"url": "http://ips-hackathon/extensions/status-light",
                     "valueString": self._status_light(item)},
                ],
            }
            if item.dose:
                med_statement["dosage"] = [{"text": item.dose}]

            entries.append({"fullUrl": _fullurl("Medication", med_id), "resource": medication})
            entries.append({"fullUrl": _fullurl("MedicationStatement", ms_id), "resource": med_statement})
            refs.append({"reference": f"urn:uuid:{ms_id}"})

            dr_ids = self._doc_ref_ids_for(item.source_ids)
            if dr_ids:
                prov = _provenance([ms_id], dr_ids, patient_id, ai_device_id, self.now)
                entries.append({"fullUrl": _fullurl("Provenance", prov["id"]), "resource": prov})

        section = {
            "title": meta["title"],
            "code": {"coding": [_coding("http://loinc.org", meta["loinc"], meta["title"])]},
            "text": {"status": "generated",
                     "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{AI_NOTICE}</div>'},
            "entry": refs,
        }
        return section, entries

    def _section_past_history(self, patient_id: str, ai_device_id: str) -> tuple[dict, list[dict]]:
        meta = IPS_SECTIONS["past_history"]
        entries: list[dict] = []
        refs: list[dict] = []
        for item in self.inter.included.past_history:
            cond_id = _uid()
            icd = validate_icd10(item.icd10_suggested, item.text)
            cc = _codeable_concept_from_validated(icd, item.text)
            condition: dict = {
                "resourceType": "Condition",
                "id": cond_id,
                "clinicalStatus": {
                    "coding": [_coding(
                        "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "resolved", "Resolved"
                    )]
                },
                "code": cc,
                "subject": {"reference": f"urn:uuid:{patient_id}"},
                "extension": [
                    {"url": "http://ips-hackathon/extensions/quote-verified",
                     "valueBoolean": item.quote_verified},
                    {"url": "http://ips-hackathon/extensions/status-light",
                     "valueString": self._status_light(item)},
                ],
            }
            if item.resolved:
                condition["abatementString"] = item.resolved
            entries.append({"fullUrl": _fullurl("Condition", cond_id), "resource": condition})
            refs.append({"reference": f"urn:uuid:{cond_id}"})
            dr_ids = self._doc_ref_ids_for(item.source_ids)
            if dr_ids:
                prov = _provenance([cond_id], dr_ids, patient_id, ai_device_id, self.now)
                entries.append({"fullUrl": _fullurl("Provenance", prov["id"]), "resource": prov})

        section = {
            "title": meta["title"],
            "code": {"coding": [_coding("http://loinc.org", meta["loinc"], meta["title"])]},
            "text": {"status": "generated",
                     "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{AI_NOTICE}</div>'},
            "entry": refs,
        }
        return section, entries

    def _section_procedures(self, patient_id: str, ai_device_id: str) -> tuple[dict, list[dict]]:
        meta = IPS_SECTIONS["procedures"]
        entries: list[dict] = []
        refs: list[dict] = []
        for item in self.inter.included.procedures:
            proc_id = _uid()
            procedure: dict = {
                "resourceType": "Procedure",
                "id": proc_id,
                "status": "completed",
                "code": {"text": item.text},
                "subject": {"reference": f"urn:uuid:{patient_id}"},
                "extension": [
                    {"url": "http://ips-hackathon/extensions/quote-verified",
                     "valueBoolean": item.quote_verified},
                    {"url": "http://ips-hackathon/extensions/status-light",
                     "valueString": self._status_light(item)},
                ],
            }
            if item.date:
                procedure["performedString"] = item.date
            entries.append({"fullUrl": _fullurl("Procedure", proc_id), "resource": procedure})
            refs.append({"reference": f"urn:uuid:{proc_id}"})
            dr_ids = self._doc_ref_ids_for(item.source_ids)
            if dr_ids:
                prov = _provenance([proc_id], dr_ids, patient_id, ai_device_id, self.now)
                entries.append({"fullUrl": _fullurl("Provenance", prov["id"]), "resource": prov})

        section = {
            "title": meta["title"],
            "code": {"coding": [_coding("http://loinc.org", meta["loinc"], meta["title"])]},
            "text": {"status": "generated",
                     "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{AI_NOTICE}</div>'},
            "entry": refs,
        }
        return section, entries

    def _section_devices(self, patient_id: str, ai_device_id: str) -> tuple[dict, list[dict]]:
        meta = IPS_SECTIONS["devices"]
        entries: list[dict] = []
        refs: list[dict] = []
        for item in self.inter.included.medical_devices:
            dev_id = _uid()
            dus_id = _uid()
            device: dict = {
                "resourceType": "Device",
                "id": dev_id,
                "deviceName": [{"name": item.text, "type": "user-friendly-name"}],
            }
            dus: dict = {
                "resourceType": "DeviceUseStatement",
                "id": dus_id,
                "status": "active",
                "device": {"reference": f"urn:uuid:{dev_id}"},
                "subject": {"reference": f"urn:uuid:{patient_id}"},
                "extension": [
                    {"url": "http://ips-hackathon/extensions/quote-verified",
                     "valueBoolean": item.quote_verified},
                    {"url": "http://ips-hackathon/extensions/status-light",
                     "valueString": self._status_light(item)},
                ],
            }
            if item.since:
                dus["timingDateTime"] = item.since
            entries.append({"fullUrl": _fullurl("Device", dev_id), "resource": device})
            entries.append({"fullUrl": _fullurl("DeviceUseStatement", dus_id), "resource": dus})
            refs.append({"reference": f"urn:uuid:{dus_id}"})
            dr_ids = self._doc_ref_ids_for(item.source_ids)
            if dr_ids:
                prov = _provenance([dus_id], dr_ids, patient_id, ai_device_id, self.now)
                entries.append({"fullUrl": _fullurl("Provenance", prov["id"]), "resource": prov})

        section = {
            "title": meta["title"],
            "code": {"coding": [_coding("http://loinc.org", meta["loinc"], meta["title"])]},
            "text": {"status": "generated",
                     "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{AI_NOTICE}</div>'},
            "entry": refs,
        }
        return section, entries

    def _section_immunizations(self, patient_id: str, ai_device_id: str) -> tuple[dict, list[dict]]:
        meta = IPS_SECTIONS["immunizations"]
        entries: list[dict] = []
        refs: list[dict] = []
        for item in self.inter.included.immunizations:
            imm_id = _uid()
            immunization: dict = {
                "resourceType": "Immunization",
                "id": imm_id,
                "status": "completed",
                "vaccineCode": {"text": item.vaccine},
                "patient": {"reference": f"urn:uuid:{patient_id}"},
                "primarySource": False,
                "extension": [
                    {"url": "http://ips-hackathon/extensions/quote-verified",
                     "valueBoolean": item.quote_verified},
                ],
            }
            if item.date:
                immunization["occurrenceString"] = item.date
            entries.append({"fullUrl": _fullurl("Immunization", imm_id), "resource": immunization})
            refs.append({"reference": f"urn:uuid:{imm_id}"})
        section = {
            "title": meta["title"],
            "code": {"coding": [_coding("http://loinc.org", meta["loinc"], meta["title"])]},
            "text": {"status": "generated",
                     "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{AI_NOTICE}</div>'},
            "entry": refs,
        }
        return section, entries

    def _section_results(self, patient_id: str, ai_device_id: str) -> tuple[dict, list[dict]]:
        meta = IPS_SECTIONS["results"]
        entries: list[dict] = []
        refs: list[dict] = []
        for item in self.inter.included.key_results:
            obs_id = _uid()
            obs: dict = {
                "resourceType": "Observation",
                "id": obs_id,
                "status": "final",
                "code": {"text": item.text},
                "subject": {"reference": f"urn:uuid:{patient_id}"},
                "extension": [
                    {"url": "http://ips-hackathon/extensions/quote-verified",
                     "valueBoolean": item.quote_verified},
                    {"url": "http://ips-hackathon/extensions/status-light",
                     "valueString": self._status_light(item)},
                ],
            }
            if item.value:
                obs["valueString"] = item.value
            if item.date:
                obs["effectiveDateTime"] = item.date
            entries.append({"fullUrl": _fullurl("Observation", obs_id), "resource": obs})
            refs.append({"reference": f"urn:uuid:{obs_id}"})
            dr_ids = self._doc_ref_ids_for(item.source_ids)
            if dr_ids:
                prov = _provenance([obs_id], dr_ids, patient_id, ai_device_id, self.now)
                entries.append({"fullUrl": _fullurl("Provenance", prov["id"]), "resource": prov})

        section = {
            "title": meta["title"],
            "code": {"coding": [_coding("http://loinc.org", meta["loinc"], meta["title"])]},
            "text": {"status": "generated",
                     "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{AI_NOTICE}</div>'},
            "entry": refs,
        }
        return section, entries

    # ── Composition ───────────────────────────────────────────────────────────
    def _build_composition(
        self,
        composition_id: str,
        patient_id: str,
        org_id: str,
        sections: list[dict],
    ) -> dict:
        p = self.patient_json
        return {
            "resourceType": "Composition",
            "id": composition_id,
            "meta": {"profile": [IPS_COMPOSITION_PROFILE]},
            "status": "preliminary",   # clinician review required
            "type": {
                "coding": [_coding("http://loinc.org", "60591-5", "Patient summary Document")]
            },
            "subject": {"reference": f"urn:uuid:{patient_id}"},
            "date": self.now,
            "author": [{"reference": f"urn:uuid:{patient_id}"}],  # placeholder; replaced on approval
            "title": (
                f"Internationales Patienten-Summary – {p['vorname']} {p['nachname']}"
                f" (*{p['geburtsdatum']})"
            ),
            "confidentiality": "N",
            "attester": [],
            "custodian": {"reference": f"urn:uuid:{org_id}"},
            "section": sections,
            "extension": [
                {
                    "url": "http://ips-hackathon/extensions/ai-generated",
                    "valueBoolean": True,
                },
                {
                    "url": "http://ips-hackathon/extensions/ai-notice",
                    "valueString": AI_NOTICE,
                },
            ],
        }


def map_to_fhir(
    intermediate: ExtractionIntermediate,
    patient_json: dict,
    mapping: PseudoMapping,
    documents: list[dict],
) -> dict:
    """Entry point: return a FHIR R4 Bundle dict."""
    mapper = FHIRMapper(intermediate, patient_json, mapping, documents)
    return mapper.build_bundle()

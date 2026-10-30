"""
extract.py – Step 3: LLM extraction.

Sends pseudonymized document texts to the LLM and receives an intermediate
JSON conforming to the ExtractionIntermediate schema.

Key design rules:
- The LLM NEVER sees patient.json or ground_truth_ips.json.
- The LLM NEVER writes FHIR JSON.
- LLM output is parsed defensively with up to MAX_RETRIES retries on
  invalid or schema-violating JSON.
- The prompt instructs the LLM to put negated/ruled-out/family-history
  items in the 'excluded' list, NEVER in 'included'.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from pipeline.llm_client import LLMClient
from pipeline.models import ExtractionIntermediate

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are a clinical document analysis engine that extracts structured 
clinical information from German hospital documents to populate an International Patient 
Summary (IPS) according to HL7 FHIR R4 / IPS IG 2.0.0.

CRITICAL RULES:
0. You extract KEY POINTS, not conclusions. Every free-text field restates what a document says as a short key point. You never interpret, diagnose, weigh documents against each other, or decide whether something is present, confirmed, ruled out, related or correct. Do not use words such as "ruled out", "excluded", "confirmed", "unrelated", "incorrect", "likely" or "suggests" unless you attribute them to the document that says them (for example "CT report: no embolism described").
1. You MUST return ONLY valid JSON conforming to the schema below. No prose, no markdown.
2. Every item MUST include a verbatim quote from the source document and the source document ID(s).
3. Items that are NEGATED, RULED OUT in a later document, FAMILY HISTORY, or UNCONFIRMED (patient-reported but not clinically confirmed) go into 'excluded', not into 'included'. You do not make diagnoses: every 'excluded' item is shown to the treating doctor for review, so keep the wording neutral and factual. Exception: allergies and intolerances reported by the patient go into allergies_intolerances with verification "unconfirmed" (not into 'excluded'), so they stay visible.
4. For medications: track the full lifecycle (start, dose change, stop). Stopped medications 
   belong in medication_stopped, not medication_at_discharge.
5. ICD-10, SNOMED CT, and ATC codes are SUGGESTIONS ONLY — mark them with the _suggested suffix.
   If unsure of a code, set it to null rather than inventing one. Give the ATC code for every medication you can identify with confidence.
6. The patient data has been pseudonymized. Use the pseudonymized tokens as-is.
7. Write every free-text field (text, substance, reaction, active_ingredient, dose, reason, detail, value) in clear clinical English. The 'quote' field is the only exception: copy it verbatim, in the original German, from the source document. Use plain English clinical terms (for example "Allergic asthma", "Liver MRI"), not German or Latin labels.
8. For every 'excluded' item, write 'text' as a short key point of what the document says, attributed to the document type (for example "Admission note: no previous hip surgery documented" or "CT report: no embolism described"), not just the name of the condition. Set 'detail' to null.
9. Negative findings (for example "no pulmonary embolism") are neither key_results nor problems. If relevant, put them in 'excluded' with reason "negated" so the treating doctor sees them.

EXCLUSION REASONS (use exactly these values):
  ruled_out        – diagnosis explicitly excluded/negatived in a later authoritative document
  family_history   – condition of a family member, not the patient
  unconfirmed      – patient-reported, never clinically confirmed or documented by a clinician
  negated          – explicitly negated in the same document ("kein Hinweis auf", "ausgeschlossen")

OUTPUT JSON SCHEMA:
{
  "included": {
    "problems_active": [
      {"text": "...", "icd10_suggested": "...|null", "snomed_suggested": "...|null",
       "onset": "YYYY-MM-DD|null", "source_ids": ["DOC-ID"], "quote": "verbatim text"}
    ],
    "past_history": [
      {"text": "...", "icd10_suggested": "...|null", "resolved": "YYYY|null",
       "source_ids": [], "quote": "..."}
    ],
    "allergies_intolerances": [
      {"substance": "...", "reaction": "...|null",
       "criticality": "low|high|unknown", "verification": "confirmed|unconfirmed",
       "source_ids": [], "quote": "..."}
    ],
    "medication_at_discharge": [
      {"active_ingredient": "...", "atc_suggested": "...|null", "dose": "...|null",
       "status": "new|changed|unchanged", "source_ids": [], "quote": "..."}
    ],
    "medication_stopped": [
      {"active_ingredient": "...", "atc_suggested": "...|null", "reason": "...|null",
       "source_ids": [], "quote": "..."}
    ],
    "procedures": [
      {"text": "...", "date": "YYYY-MM-DD|null", "source_ids": [], "quote": "..."}
    ],
    "medical_devices": [
      {"text": "...", "since": "YYYY-MM-DD|null", "source_ids": [], "quote": "..."}
    ],
    "immunizations": [
      {"vaccine": "...", "date": "YYYY-MM-DD|null", "source_ids": [], "quote": "..."}
    ],
    "key_results": [
      {"text": "...", "value": "...|null", "date": "YYYY-MM-DD|null",
       "source_ids": [], "quote": "..."}
    ]
  },
  "excluded": [
    {"text": "...", "reason": "ruled_out|family_history|unconfirmed|negated",
     "detail": "...|null", "source_ids": [], "quote": "..."}
  ]
}"""


def _build_user_prompt(patient_token: str, pseudo_docs: list[dict[str, Any]]) -> str:
    lines = [
        f"Patient token: {patient_token}",
        f"Total documents: {len(pseudo_docs)}",
        "",
        "Extract all clinically relevant information from the following hospital documents.",
        "Documents are in German and sorted chronologically. Answer in English; quotes stay verbatim in German.",
        "Pay special attention to:",
        "  - Allergies mentioned ONLY in nursing notes",
        "  - Diagnoses that are suspected and later ruled out",
        "  - Medications that were started, changed, or stopped",
        "  - Negations and family history that must NOT enter the active problem list",
        "  - Patient-reported items that were never clinically confirmed",
        "",
        "=== DOCUMENTS ===",
    ]
    for doc in pseudo_docs:
        lines.append(
            f"\n--- Document ID: {doc['id']} | Type: {doc.get('typ','')} | "
            f"Date: {doc.get('datum','')} | Title: {doc.get('titel','')} ---"
        )
        lines.append(doc.get("text", ""))
    return "\n".join(lines)


def _parse_llm_json(raw: str) -> dict[str, Any]:
    """Parse LLM response, stripping any accidental markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip ```json … ``` fences
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def extract(
    patient_token: str,
    pseudo_docs: list[dict[str, Any]],
    llm_client: LLMClient | None = None,
) -> ExtractionIntermediate:
    """
    Call the LLM and return a validated ExtractionIntermediate.

    Retries up to MAX_RETRIES times on JSON or schema errors.
    """
    if llm_client is None:
        llm_client = LLMClient()

    user_prompt = _build_user_prompt(patient_token, pseudo_docs)
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("LLM extraction attempt %d/%d for token %s", attempt, MAX_RETRIES, patient_token)
        try:
            raw = llm_client.complete(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=8192,
            )
            data = _parse_llm_json(raw)

            # Inject metadata fields the LLM doesn't produce
            data["patient_token"] = patient_token
            data["extraction_model"] = llm_client._model
            data["extraction_timestamp"] = datetime.now(timezone.utc).isoformat()
            data["pseudonymized"] = True

            intermediate = ExtractionIntermediate.model_validate(data)
            logger.info(
                "Extraction succeeded: %d included items, %d excluded",
                len(intermediate.all_included_items()),
                len(intermediate.excluded),
            )
            return intermediate

        except json.JSONDecodeError as exc:
            last_error = exc
            logger.warning("Attempt %d: invalid JSON from LLM: %s", attempt, exc)
        except ValidationError as exc:
            last_error = exc
            logger.warning("Attempt %d: schema validation failed: %s", attempt, exc)
        except Exception as exc:
            last_error = exc
            logger.warning("Attempt %d: unexpected error: %s", attempt, exc)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    raise RuntimeError(
        f"LLM extraction failed after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    ) from last_error

"""
summary.py – Step 9: Draft discharge summary in German.

Generates a Markdown discharge summary where every sentence references
the source document IDs it was derived from. The summary is marked as
AI-generated draft requiring clinical review.

The LLM is called one more time here — still with pseudonymized tokens,
re-identified only in the output file writing (run.py).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pipeline.llm_client import LLMClient
from pipeline.models import ExtractionIntermediate

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM_PROMPT = """Du bist ein klinisches Dokumentationssystem. Deine Aufgabe ist es, 
auf Basis der extrahierten strukturierten Informationen einen deutschsprachigen 
Arztbrief-Entwurf (Entlassungsbrief / Zusammenfassung) zu erstellen.

PFLICHTREGELN:
1. Jeder Satz, der eine klinische Tatsache enthält, MUSS am Ende in eckigen Klammern 
   die Quelldokument-IDs angeben, z.B. [P001-D004, P001-D009].
2. Ausgeschlossene Diagnosen (Verdachtsdiagnosen, Familienanamnese, unbestätigte Angaben) 
   dürfen NICHT in den aktiven Diagnosen erscheinen.
3. Der Brief MUSS mit diesem Hinweis beginnen:
   > ⚠️ KI-GENERIERTER ENTWURF – Ärztliche Prüfung und Freigabe erforderlich. Kein klinischer Einsatz ohne Prüfung.
4. Verwende österreichischen medizinischen Stil: klar, prägnant, mit gängigen Abkürzungen.
5. Gib NUR den Markdown-Text zurück, keine JSON-Verpackung."""


def _build_summary_prompt(intermediate: ExtractionIntermediate) -> str:
    lines = [
        "Erstelle einen Entlassungsbrief-Entwurf auf Basis der folgenden extrahierten Informationen.",
        f"Patient-Token: {intermediate.patient_token}",
        "",
        "## Aktive Probleme:",
    ]
    for item in intermediate.included.problems_active:
        lines.append(f"- {item.text} (Quellen: {', '.join(item.source_ids)})")

    lines.append("\n## Frühere Erkrankungen:")
    for item in intermediate.included.past_history:
        lines.append(f"- {item.text} (Quellen: {', '.join(item.source_ids)})")

    lines.append("\n## Allergien/Unverträglichkeiten:")
    for item in intermediate.included.allergies_intolerances:
        lines.append(
            f"- {item.substance}: {item.reaction or 'keine Reaktion dokumentiert'}, "
            f"Bestätigung: {item.verification.value} (Quellen: {', '.join(item.source_ids)})"
        )

    lines.append("\n## Medikation bei Entlassung:")
    for item in intermediate.included.medication_at_discharge:
        lines.append(f"- {item.active_ingredient} {item.dose or ''} [{item.status.value}] (Quellen: {', '.join(item.source_ids)})")

    lines.append("\n## Während des Aufenthalts gestoppte Medikamente:")
    for item in intermediate.included.medication_stopped:
        lines.append(f"- {item.active_ingredient}: {item.reason or '–'} (Quellen: {', '.join(item.source_ids)})")

    lines.append("\n## Durchgeführte Maßnahmen/Eingriffe:")
    for item in intermediate.included.procedures:
        lines.append(f"- {item.text} am {item.date or 'unbekannt'} (Quellen: {', '.join(item.source_ids)})")

    lines.append("\n## Medizinische Geräte/Implantate:")
    for item in intermediate.included.medical_devices:
        lines.append(f"- {item.text} seit {item.since or 'unbekannt'} (Quellen: {', '.join(item.source_ids)})")

    lines.append("\n## Wichtige Befunde:")
    for item in intermediate.included.key_results:
        lines.append(f"- {item.text}: {item.value or '–'} ({item.date or '–'}) (Quellen: {', '.join(item.source_ids)})")

    lines.append("\n## Ausgeschlossene Einträge (NICHT in den Diagnosen):")
    for item in intermediate.excluded:
        lines.append(f"- {item.text} [Grund: {item.reason.value}]")

    return "\n".join(lines)


def generate_summary(
    intermediate: ExtractionIntermediate,
    patient_json: dict,
    llm_client: LLMClient | None = None,
) -> str:
    """
    Generate a German discharge summary draft with source references.
    Returns a Markdown string.
    """
    if llm_client is None:
        llm_client = LLMClient()

    user_prompt = _build_summary_prompt(intermediate)

    logger.info("Generating discharge summary draft for token %s", intermediate.patient_token)
    try:
        draft = llm_client.complete(
            system_prompt=_SUMMARY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=4096,
        )
    except Exception as exc:
        logger.error("Summary generation failed: %s", exc)
        draft = (
            "> ⚠️ KI-GENERIERTER ENTWURF – Ärztliche Prüfung und Freigabe erforderlich.\n\n"
            f"**Fehler bei der Zusammenfassungsgenerierung:** {exc}\n\n"
            "Bitte Zusammenfassung manuell erstellen."
        )

    # Re-identify patient name in the summary header (tokens replaced with real name)
    real_name = f"{patient_json.get('vorname','')} {patient_json.get('nachname','')}".strip()
    real_dob = patient_json.get("geburtsdatum", "")
    draft = draft.replace(intermediate.patient_token, f"{real_name} (*{real_dob})")

    # Prepend metadata header
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = (
        f"# Entlassungsbrief-Entwurf\n\n"
        f"> ⚠️ **KI-GENERIERTER ENTWURF** – Ärztliche Prüfung und Freigabe erforderlich.  \n"
        f"> Kein klinischer Einsatz ohne ärztliche Prüfung. Status: **ENTWURF**\n\n"
        f"**Patient:** {real_name}  \n"
        f"**Geburtsdatum:** {real_dob}  \n"
        f"**Erstellt:** {timestamp}  \n"
        f"**Erstellt durch:** KI-System (IPS-Hackathon-AI v0.1.0)  \n\n"
        f"---\n\n"
    )
    return header + draft

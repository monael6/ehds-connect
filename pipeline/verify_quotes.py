"""
verify_quotes.py – Step 4: Quote verification (deterministic).

For every item in the intermediate JSON that has a quote, checks whether
the verbatim quote appears in at least one of the referenced source documents.

Items with failing quotes are flagged (quote_verified = False) so that:
  - They appear as red status lights in the UI
  - The FHIR mapper records them as requiring review
  - They do NOT silently end up in a validated FHIR bundle

Returns the mutated intermediate object and a list of failed items.
"""

from __future__ import annotations

import logging
import unicodedata
from typing import Any

from pipeline.models import BaseItem, ExtractionIntermediate

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Normalize whitespace and unicode for loose matching."""
    text = unicodedata.normalize("NFC", text)
    # Collapse whitespace
    return " ".join(text.split())


def _quote_in_doc(quote: str, doc_text: str) -> bool:
    """Case-insensitive, whitespace-normalized substring check."""
    if not quote or not doc_text:
        return False
    return _normalize(quote).lower() in _normalize(doc_text).lower()


def verify_quotes(
    intermediate: ExtractionIntermediate,
    documents: list[dict[str, Any]],
) -> tuple[ExtractionIntermediate, list[dict[str, Any]]]:
    """
    Verify that every item's quote appears verbatim in its source document(s).

    Args:
        intermediate: The extraction result from the LLM.
        documents:    The (pseudonymized) document list, same as sent to LLM.

    Returns:
        (updated_intermediate, failed_items)
        failed_items is a list of dicts describing items with unverified quotes.
    """
    doc_by_id: dict[str, str] = {
        doc["id"]: doc.get("text", "") for doc in documents
    }

    failed: list[dict[str, Any]] = []

    all_items: list[BaseItem] = (
        intermediate.all_included_items() + intermediate.excluded  # type: ignore[arg-type]
    )

    for item in all_items:
        quote = item.quote.strip() if item.quote else ""
        if not quote:
            # No quote provided — mark as unverified but don't add to failed
            item.quote_verified = False
            continue

        verified = False
        for source_id in item.source_ids:
            doc_text = doc_by_id.get(source_id, "")
            if _quote_in_doc(quote, doc_text):
                verified = True
                break

        item.quote_verified = verified

        if not verified:
            item_text = getattr(item, "text", None) or getattr(item, "substance", None) or \
                        getattr(item, "active_ingredient", None) or getattr(item, "vaccine", None) or ""
            failed.append({
                "item_text": item_text,
                "quote": quote[:120],
                "source_ids": item.source_ids,
                "item_type": type(item).__name__,
            })
            logger.warning(
                "Quote verification FAILED for %s: %r (sources: %s)",
                type(item).__name__,
                quote[:80],
                item.source_ids,
            )

    if failed:
        logger.warning(
            "%d item(s) have unverified quotes and will be flagged in the output.",
            len(failed),
        )
    else:
        logger.info("All quotes verified successfully.")

    intermediate.recompute_summary()
    return intermediate, failed

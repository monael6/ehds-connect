"""
evaluate.py – Step 8: Evaluation against ground truth (synthetic mode only).

Compares the intermediate JSON with ground_truth_ips.json and reports:
  - Precision and recall per section
  - Whether any must_not_include item leaked into the IPS

GROUND TRUTH IS NEVER PASSED TO THE LLM.
It is only loaded here, after the LLM has run, for offline evaluation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.models import ExtractionIntermediate

logger = logging.getLogger(__name__)


@dataclass
class SectionMetrics:
    section: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def to_dict(self) -> dict:
        return {
            "section": self.section,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "f1": round(self.f1, 3),
        }


@dataclass
class EvaluationReport:
    patient_id: str
    sections: list[SectionMetrics] = field(default_factory=list)
    must_not_include_leaks: list[dict] = field(default_factory=list)
    overall_precision: float = 0.0
    overall_recall: float = 0.0
    overall_f1: float = 0.0

    def to_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "sections": [s.to_dict() for s in self.sections],
            "must_not_include_leaks": self.must_not_include_leaks,
            "overall_precision": round(self.overall_precision, 3),
            "overall_recall": round(self.overall_recall, 3),
            "overall_f1": round(self.overall_f1, 3),
        }


def _text_set(items: list[dict], key: str = "text") -> set[str]:
    """Normalised lowercase set of texts for fuzzy matching."""
    return {item.get(key, "").lower().strip() for item in items if item.get(key)}


def _extract_section_texts(intermediate: ExtractionIntermediate, section: str) -> set[str]:
    mapping = {
        "problems_active":        [(i.text,) for i in intermediate.included.problems_active],
        "past_history":           [(i.text,) for i in intermediate.included.past_history],
        "allergies_intolerances": [(i.substance,) for i in intermediate.included.allergies_intolerances],
        "medication_at_discharge":[(i.active_ingredient,) for i in intermediate.included.medication_at_discharge],
        "medication_stopped":     [(i.active_ingredient,) for i in intermediate.included.medication_stopped],
        "procedures":             [(i.text,) for i in intermediate.included.procedures],
        "medical_devices":        [(i.text,) for i in intermediate.included.medical_devices],
        "immunizations":          [(i.vaccine,) for i in intermediate.included.immunizations],
        "key_results":            [(i.text,) for i in intermediate.included.key_results],
    }
    return {t[0].lower().strip() for t in mapping.get(section, []) if t[0]}


def _gt_section_texts(ground_truth: dict, section: str) -> set[str]:
    """Extract normalised texts from ground truth section."""
    gt_key_map = {
        "problems_active":         ("problems_active", "text"),
        "past_history":            ("past_history", "text"),
        "allergies_intolerances":  ("allergies_intolerances", "substance"),
        "medication_at_discharge": ("medication_at_discharge", "active_ingredient"),
        "medication_stopped":      ("medication_stopped_during_stay", "active_ingredient"),
        "procedures":              ("procedures", "text"),
        "medical_devices":         ("medical_devices_implants", "text"),
        "immunizations":           ("immunizations", "vaccine"),
        "key_results":             ("key_results", "text"),
    }
    gt_key, item_key = gt_key_map.get(section, (section, "text"))
    items = ground_truth.get(gt_key, [])
    return {item.get(item_key, "").lower().strip() for item in items if item.get(item_key)}


def _check_must_not_include(
    intermediate: ExtractionIntermediate,
    must_not: list[dict],
) -> list[dict]:
    """Return any must_not_include items that appear in included sections."""
    all_included_texts: set[str] = set()
    for item in intermediate.all_included_items():
        for attr in ("text", "substance", "active_ingredient", "vaccine"):
            val = getattr(item, attr, None)
            if val:
                all_included_texts.add(val.lower().strip())

    leaks = []
    for forbidden in must_not:
        text = forbidden.get("text", "").lower().strip()
        if not text:
            continue
        # Check substring match (a leaked item might have a slightly different phrasing)
        for included_text in all_included_texts:
            if text in included_text or included_text in text:
                leaks.append({
                    "forbidden_text": forbidden.get("text"),
                    "reason": forbidden.get("reason"),
                    "matched_in_ips": included_text,
                })
                break
    return leaks


SECTIONS = [
    "problems_active",
    "past_history",
    "allergies_intolerances",
    "medication_at_discharge",
    "medication_stopped",
    "procedures",
    "medical_devices",
    "immunizations",
    "key_results",
]


def evaluate(
    intermediate: ExtractionIntermediate,
    ground_truth_path: Path,
) -> EvaluationReport:
    """
    Compare intermediate extraction against ground truth.

    ground_truth_path must NOT be passed to any LLM — this is called
    after all LLM steps have completed.
    """
    if not ground_truth_path.exists():
        logger.warning("Ground truth file not found: %s", ground_truth_path)
        return EvaluationReport(patient_id="unknown")

    ground_truth: dict = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    patient_id = ground_truth.get("patient_id", "unknown")
    report = EvaluationReport(patient_id=patient_id)

    # Per-section metrics
    all_tp = all_fp = all_fn = 0
    for section in SECTIONS:
        predicted = _extract_section_texts(intermediate, section)
        expected = _gt_section_texts(ground_truth, section)

        # Simple exact/substring matching (normalised)
        tp = len(predicted & expected)
        fp = len(predicted - expected)
        fn = len(expected - predicted)

        metrics = SectionMetrics(
            section=section,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
        )
        report.sections.append(metrics)
        all_tp += tp
        all_fp += fp
        all_fn += fn

    # Overall
    overall_prec = all_tp / (all_tp + all_fp) if (all_tp + all_fp) else 0.0
    overall_rec  = all_tp / (all_tp + all_fn) if (all_tp + all_fn) else 0.0
    report.overall_precision = overall_prec
    report.overall_recall = overall_rec
    report.overall_f1 = (
        2 * overall_prec * overall_rec / (overall_prec + overall_rec)
        if (overall_prec + overall_rec) else 0.0
    )

    # Must-not-include leaks
    must_not = ground_truth.get("must_not_include", [])
    report.must_not_include_leaks = _check_must_not_include(intermediate, must_not)

    if report.must_not_include_leaks:
        logger.warning(
            "EVALUATION: %d must_not_include item(s) leaked into the IPS!",
            len(report.must_not_include_leaks),
        )
    logger.info(
        "Evaluation: precision=%.3f recall=%.3f f1=%.3f",
        report.overall_precision, report.overall_recall, report.overall_f1,
    )
    return report

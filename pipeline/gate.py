"""
gate.py – Step 1: Data-protection gate.

Runs before any LLM call or output is written.
Enforces GDPR Art. 9 requirements for health data processing.

Modes:
  synthetic     – allowed with any configured LLM provider
  pseudonymized – requires deployment.yaml with all GDPR checks passed
  real          – same as pseudonymized, additional "real" flag must be set

The gate also runs a heuristic check on input data to detect potentially
real data even when --mode synthetic is declared.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml  # PyYAML

Mode = Literal["synthetic", "pseudonymized", "real"]

# ── Austrian insurance number pattern: XXXX-NNNNNN ────────────────────────────
# Synthetic IDs in this dataset all start with "FAKE-"
_REAL_INSURANCE_RE = re.compile(r"\b\d{4}-\d{6}\b")
# Real-looking Austrian names (heuristic: common Austrian surnames)
_REAL_NAME_INDICATORS = [
    "sozialversicherungsnummer",
    "svnr",
    "geburtsname",
    "pass-nr",
    "personalausweis",
]


@dataclass
class GateResult:
    allowed: bool
    mode: Mode
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ── Required deployment.yaml keys ─────────────────────────────────────────────
_REQUIRED_DEPLOYMENT_KEYS = [
    "legal_basis_documented",
    "data_processing_agreement_art28",
    "processing_location_eu_or_onpremises",
    "no_training_on_submitted_data",
    "limited_data_retention",
    "dpia_art35_completed",
    "responsible_person",
]


def run_gate(
    mode: Mode,
    patient_id: str,
    document_texts: list[str],
    deployment_yaml_path: Path | None = None,
) -> GateResult:
    """
    Run the data-protection gate.

    Raises SystemExit on hard failure (missing GDPR requirements).
    Returns GateResult with warnings for soft issues.
    """
    result = GateResult(allowed=False, mode=mode)

    if mode == "synthetic":
        result = _check_synthetic(result, patient_id, document_texts)
    elif mode in ("pseudonymized", "real"):
        result = _check_non_synthetic(result, mode, deployment_yaml_path)
    else:
        result.errors.append(f"Unknown mode '{mode}'. Must be synthetic | pseudonymized | real.")
        _fail(result)

    return result


def _check_synthetic(result: GateResult, patient_id: str, texts: list[str]) -> GateResult:
    """For synthetic mode: warn if data looks real."""
    suspicious: list[str] = []

    for text in texts:
        # Check for real-looking insurance numbers (not FAKE-*)
        # Use finditer so we can inspect the prefix in the original string
        for m in _REAL_INSURANCE_RE.finditer(text):
            prefix = text[max(0, m.start() - 5):m.start()]
            if "FAKE" not in prefix:
                suspicious.append(f"Possible real insurance number: {m.group()!r}")

        # Check for indicator keywords
        lower = text.lower()
        for kw in _REAL_NAME_INDICATORS:
            if kw in lower:
                suspicious.append(f"Indicator keyword found: {kw!r}")

    if suspicious:
        result.warnings.append(
            "WARNING: Input data in 'synthetic' mode shows signs of real patient data. "
            "Processing continues but you should verify the data is truly synthetic.\n"
            "Indicators found:\n" + "\n".join(f"  - {s}" for s in suspicious[:5])
        )

    result.allowed = True
    return result


def _check_non_synthetic(
    result: GateResult,
    mode: Mode,
    deployment_yaml_path: Path | None,
) -> GateResult:
    """For pseudonymized/real mode: enforce deployment.yaml requirements."""
    if deployment_yaml_path is None:
        deployment_yaml_path = Path("deployment.yaml")

    if not deployment_yaml_path.exists():
        result.errors.append(
            f"Mode '{mode}' requires deployment.yaml at {deployment_yaml_path} but file not found.\n"
            "Copy deployment.yaml.example to deployment.yaml and fill in all required fields."
        )
        _fail(result)
        return result

    try:
        config = yaml.safe_load(deployment_yaml_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        result.errors.append(f"Could not parse deployment.yaml: {exc}")
        _fail(result)
        return result

    missing: list[str] = []
    for key in _REQUIRED_DEPLOYMENT_KEYS:
        val = config.get(key)
        if not val or val in (False, "false", "", "TODO", "FILL_IN"):
            missing.append(key)

    if mode == "real":
        if not config.get("real_patient_data_explicitly_approved"):
            missing.append("real_patient_data_explicitly_approved")

    if missing:
        result.errors.append(
            f"GDPR compliance check FAILED for mode '{mode}'.\n"
            "The following required items are missing or not confirmed in deployment.yaml:\n"
            + "\n".join(f"  ✗ {k}" for k in missing)
            + "\n\nThis tool will NOT process real or pseudonymized patient data "
            "without documented GDPR compliance.\n"
            "See docs/DATA_PROTECTION.md for guidance."
        )
        _fail(result)

    responsible = config.get("responsible_person", "")
    result.warnings.append(
        f"Mode '{mode}' authorised. Responsible person: {responsible}"
    )
    result.allowed = True
    return result


def _fail(result: GateResult) -> None:
    print("\n" + "=" * 70, file=sys.stderr)
    print("DATA PROTECTION GATE: ACCESS DENIED", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    for err in result.errors:
        print(f"\n{err}", file=sys.stderr)
    print("\n" + "=" * 70, file=sys.stderr)
    sys.exit(1)

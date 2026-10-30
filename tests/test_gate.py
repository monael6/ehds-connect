"""Tests for the data protection gate."""

import sys
import tempfile
from pathlib import Path

import pytest

from pipeline.gate import run_gate, GateResult


# ── Synthetic mode ─────────────────────────────────────────────────────────────

def test_synthetic_mode_passes_with_clean_data():
    result = run_gate("synthetic", "P001", ["Pat. stellt sich vor."])
    assert result.allowed is True


def test_synthetic_mode_warns_on_real_looking_insurance_number():
    result = run_gate("synthetic", "P001", ["SVNr: 1234-567890 Pat. Mustermann"])
    assert result.allowed is True
    assert any("signs of real patient data" in w for w in result.warnings)


def test_synthetic_mode_passes_with_fake_insurance_number():
    result = run_gate("synthetic", "P001", ["FAKE-7241-170452"])
    # FAKE prefix should not trigger warning
    assert result.allowed is True
    assert not any("real patient data" in w for w in result.warnings)


# ── Non-synthetic mode ─────────────────────────────────────────────────────────

def test_pseudonymized_mode_fails_without_deployment_yaml(tmp_path):
    """Calling pseudonymized mode without deployment.yaml must exit."""
    nonexistent = tmp_path / "nonexistent.yaml"
    with pytest.raises(SystemExit) as exc_info:
        run_gate("pseudonymized", "P001", ["text"], deployment_yaml_path=nonexistent)
    assert exc_info.value.code == 1


def test_pseudonymized_mode_fails_with_incomplete_deployment_yaml(tmp_path):
    """deployment.yaml missing required keys must fail."""
    yaml_file = tmp_path / "deployment.yaml"
    yaml_file.write_text("legal_basis_documented: true\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        run_gate("pseudonymized", "P001", ["text"], deployment_yaml_path=yaml_file)
    assert exc_info.value.code == 1


def test_pseudonymized_mode_passes_with_complete_deployment_yaml(tmp_path):
    """Complete deployment.yaml must allow processing."""
    yaml_content = """
legal_basis_documented: true
data_processing_agreement_art28: true
processing_location_eu_or_onpremises: true
no_training_on_submitted_data: true
limited_data_retention: true
dpia_art35_completed: true
responsible_person: Dr. Test Person
"""
    yaml_file = tmp_path / "deployment.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    result = run_gate("pseudonymized", "P001", ["text"], deployment_yaml_path=yaml_file)
    assert result.allowed is True


def test_real_mode_requires_explicit_approval(tmp_path):
    """Real mode needs real_patient_data_explicitly_approved."""
    yaml_content = """
legal_basis_documented: true
data_processing_agreement_art28: true
processing_location_eu_or_onpremises: true
no_training_on_submitted_data: true
limited_data_retention: true
dpia_art35_completed: true
responsible_person: Dr. Test
"""
    yaml_file = tmp_path / "deployment.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    with pytest.raises(SystemExit):
        run_gate("real", "P001", ["text"], deployment_yaml_path=yaml_file)


def test_real_mode_passes_with_explicit_approval(tmp_path):
    yaml_content = """
legal_basis_documented: true
data_processing_agreement_art28: true
processing_location_eu_or_onpremises: true
no_training_on_submitted_data: true
limited_data_retention: true
dpia_art35_completed: true
responsible_person: Dr. Test
real_patient_data_explicitly_approved: true
"""
    yaml_file = tmp_path / "deployment.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    result = run_gate("real", "P001", ["text"], deployment_yaml_path=yaml_file)
    assert result.allowed is True


def test_invalid_mode_exits():
    with pytest.raises(SystemExit):
        run_gate("unknown_mode", "P001", [])  # type: ignore[arg-type]

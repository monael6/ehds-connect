"""
validate.py – Step 7: FHIR Bundle validation.

Calls the official HL7 FHIR Validator CLI (validator_cli.jar) against:
  - hl7.fhir.uv.ips#2.0.0     (IPS IG)
  - hl7.fhir.at.aps#latest     (Austrian Patient Summary IG, stretch goal)

The jar is NOT bundled in this repo — it must be downloaded separately.
See README.md for download instructions.

Returns a ValidationReport with errors, warnings and information messages.
If the jar is not present, returns a report with status "skipped".
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

JAR_PATH = Path("validator_cli.jar")
IPS_PACKAGE = "hl7.fhir.uv.ips#2.0.0"
AT_APS_PACKAGE = "hl7.fhir.at.aps#latest"


@dataclass
class ValidationIssue:
    severity: str        # error | warning | information
    location: str
    message: str


@dataclass
class ValidationReport:
    status: Literal["passed", "failed", "skipped", "error"]
    validator_version: str = ""
    packages: list[str] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    raw_output: str = ""

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "validator_version": self.validator_version,
            "packages": self.packages,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [
                {"severity": i.severity, "location": i.location, "message": i.message}
                for i in self.issues
            ],
        }


def validate_bundle(
    bundle: dict,
    include_at_aps: bool = False,
) -> ValidationReport:
    """
    Validate a FHIR Bundle against the IPS IG.

    Falls back to 'skipped' if validator_cli.jar is not present.
    """
    if not JAR_PATH.exists():
        logger.warning(
            "validator_cli.jar not found at %s. Validation skipped. "
            "Download from https://github.com/hapifhir/org.hl7.fhir.core/releases",
            JAR_PATH,
        )
        return ValidationReport(
            status="skipped",
            raw_output="validator_cli.jar not found. Download it to enable validation.",
        )

    if not shutil.which("java"):
        logger.warning("Java not found on PATH. Validation skipped.")
        return ValidationReport(status="skipped", raw_output="Java not found on PATH.")

    packages = [IPS_PACKAGE]
    if include_at_aps:
        packages.append(AT_APS_PACKAGE)

    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", encoding="utf-8", delete=False) as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
        bundle_path = Path(f.name)

    try:
        cmd = [
            "java", "-jar", str(JAR_PATH.resolve()),
            str(bundle_path),
            "-version", "4.0",
            "-ig", IPS_PACKAGE,
            "-output-style", "compact",
            "-json",
        ]
        if include_at_aps:
            cmd += ["-ig", AT_APS_PACKAGE]

        logger.info("Running FHIR validator: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        raw = result.stdout + result.stderr
        report = _parse_validator_output(raw, packages)
        return report

    except subprocess.TimeoutExpired:
        return ValidationReport(status="error", raw_output="Validator timed out after 120s.")
    except Exception as exc:
        return ValidationReport(status="error", raw_output=str(exc))
    finally:
        bundle_path.unlink(missing_ok=True)


def _parse_validator_output(raw: str, packages: list[str]) -> ValidationReport:
    """Parse the compact JSON output of the FHIR validator CLI."""
    issues: list[ValidationIssue] = []
    has_error = False
    validator_version = ""

    # The validator outputs JSON lines; try to parse
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            # Version line
            if "version" in obj and isinstance(obj.get("version"), str):
                validator_version = obj["version"]
            # Issue line
            if "severity" in obj:
                sev = obj.get("severity", "").lower()
                if sev == "error":
                    has_error = True
                issues.append(ValidationIssue(
                    severity=sev,
                    location=obj.get("location", ""),
                    message=obj.get("message", line),
                ))
        except json.JSONDecodeError:
            # Fallback: treat as plain text
            lower = line.lower()
            if "error" in lower:
                has_error = True
                issues.append(ValidationIssue("error", "", line))
            elif "warning" in lower:
                issues.append(ValidationIssue("warning", "", line))

    status: Literal["passed", "failed", "skipped", "error"] = "failed" if has_error else "passed"
    return ValidationReport(
        status=status,
        validator_version=validator_version,
        packages=packages,
        issues=issues,
        raw_output=raw[:4000],  # truncate for storage
    )

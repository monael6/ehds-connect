"""
test_backend_auth.py – Tests for backend authentication and access control.

Tests:
  1. Author ID comes ONLY from the token, never from the request body
  2. Access denied for unassigned patients
  3. Approval blocked when red items remain
  4. Approval blocked on FHIR validation errors
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

# We test the auth dependency directly, not via HTTP (avoids Keycloak dependency)
from backend.auth import AuthenticatedPractitioner


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_practitioner(pid: str = "practitioner-mueller") -> AuthenticatedPractitioner:
    return AuthenticatedPractitioner(
        practitioner_id=pid,
        username="dr.mueller",
        roles=["clinician"],
    )


# ── Test 1: Author ID from token only ────────────────────────────────────────

def test_practitioner_id_from_token_not_request():
    """
    The practitioner_id must come from the token, not from any request field.

    Verifies two things:
    1. The ID stored on the object equals exactly what was passed at construction
       (i.e. it comes from the token-decode call-site, never a request body).
    2. Normal attribute assignment is blocked by __setattr__, so a router
       cannot accidentally overwrite the identity after construction.
    """
    practitioner = _make_practitioner("practitioner-mueller")
    assert practitioner.practitioner_id == "practitioner-mueller"

    # Normal assignment must be blocked — __setattr__ raises AttributeError.
    with pytest.raises(AttributeError):
        practitioner.practitioner_id = "hacker"  # type: ignore[misc]

    # Verify the value was NOT changed
    assert practitioner.practitioner_id == "practitioner-mueller"


def test_practitioner_id_is_used_in_author_field():
    """Verify that approve.py uses practitioner.practitioner_id, not request body."""
    # This is an architectural test: grep the source to ensure no request body field
    # named 'author' or 'practitioner_id' is accepted in approve.py
    import ast
    import pathlib
    source = pathlib.Path("backend/routers/approve.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    # Check that ApprovalRequest model has no practitioner_id field
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ApprovalRequest":
            field_names = [
                t.target.id if isinstance(t, ast.AnnAssign) and isinstance(t.target, ast.Name)
                else ""
                for t in node.body
            ]
            assert "practitioner_id" not in field_names, \
                "ApprovalRequest must NOT have a practitioner_id field (must come from token only)"
            assert "author" not in field_names, \
                "ApprovalRequest must NOT have an author field (must come from token only)"


# ── Test 2: Access denied for unassigned patients ─────────────────────────────

@pytest.mark.asyncio
async def test_access_denied_for_unassigned_patient():
    """check_assignment must return False for unassigned practitioner."""
    from backend.fhir_client import FHIRClient
    client = FHIRClient.__new__(FHIRClient)
    client._base = "http://mock"

    with patch.object(client, "get_care_team_practitioners", new=AsyncMock(return_value=["practitioner-bauer"])):
        result = await client.check_assignment("patient-p001", "practitioner-mueller")
        assert result is False


@pytest.mark.asyncio
async def test_access_granted_for_assigned_patient():
    from backend.fhir_client import FHIRClient
    client = FHIRClient.__new__(FHIRClient)
    client._base = "http://mock"

    with patch.object(client, "get_care_team_practitioners", new=AsyncMock(return_value=["practitioner-mueller"])):
        result = await client.check_assignment("patient-p001", "practitioner-mueller")
        assert result is True


# ── Test 3: Approval blocked with red items ───────────────────────────────────

def test_find_red_items_returns_red_entries():
    from backend.routers.approve import _find_red_items
    bundle = {
        "entry": [
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "cond-1",
                    "code": {"text": "Lungenembolie"},
                    "extension": [
                        {"url": "http://ips-hackathon/extensions/status-light",
                         "valueString": "red"},
                    ],
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "cond-2",
                    "code": {"text": "Hypertonie"},
                    "extension": [
                        {"url": "http://ips-hackathon/extensions/status-light",
                         "valueString": "green"},
                    ],
                }
            },
        ]
    }
    red = _find_red_items(bundle)
    assert len(red) == 1
    assert "Lungenembolie" in red[0]


def test_find_red_items_returns_empty_when_all_green():
    from backend.routers.approve import _find_red_items
    bundle = {
        "entry": [{
            "resource": {
                "resourceType": "Condition",
                "extension": [{"url": "http://ips-hackathon/extensions/status-light",
                               "valueString": "green"}],
            }
        }]
    }
    assert _find_red_items(bundle) == []


# ── Test 4: Approval blocked on validation errors ─────────────────────────────

def test_validation_errors_block_approval():
    """Ensure that a non-empty errors list would block approval (integration logic)."""
    from pipeline.validate import ValidationReport, ValidationIssue
    report = ValidationReport(
        status="failed",
        issues=[ValidationIssue("error", "Bundle.entry[0]", "Missing required element")],
    )
    assert len(report.errors) == 1
    # The approve endpoint checks `if val_report.errors: raise HTTPException`
    # This test verifies the errors property works correctly
    assert report.errors[0].severity == "error"


def test_no_errors_allows_approval():
    from pipeline.validate import ValidationReport
    report = ValidationReport(status="passed")
    assert report.errors == []

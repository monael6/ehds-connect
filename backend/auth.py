"""
auth.py – OIDC token validation and practitioner resolution.

SECURITY CONTRACT:
  - The practitioner (clinician) identity used for authoring is taken ONLY
    from the validated OIDC access token (claim fhir_practitioner_id).
  - It is NEVER taken from a request body, form field, or query parameter.
  - Every endpoint that writes clinical data must call get_current_practitioner().
"""

from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from backend.config import get_settings

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer()

# In-memory JWKS cache (refresh on 401)
_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        r = await client.get(settings.jwks_uri, timeout=10)
        r.raise_for_status()
        _jwks_cache = r.json()
    return _jwks_cache


async def _decode_token(token: str) -> dict:
    """Validate and decode a Keycloak access token."""
    settings = get_settings()
    try:
        jwks = await _get_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
            issuer=settings.issuer,
            options={"verify_aud": False},  # Keycloak may use 'account' audience
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as exc:
        logger.warning("Token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthenticatedPractitioner:
    """Resolved practitioner from a validated OIDC token.

    Uses __slots__ to make the class immutable after construction:
    any attempt to set an attribute via object.__setattr__ from outside
    the __init__ raises AttributeError, enforcing that the practitioner
    identity can NEVER be overridden from a request body.
    """
    __slots__ = ("practitioner_id", "username", "roles")

    def __init__(self, practitioner_id: str, username: str, roles: list[str]) -> None:
        object.__setattr__(self, "practitioner_id", practitioner_id)
        object.__setattr__(self, "username", username)
        object.__setattr__(self, "roles", roles)

    def __setattr__(self, name: str, value: object) -> None:  # type: ignore[override]
        raise AttributeError(
            f"AuthenticatedPractitioner is immutable — cannot set '{name}'. "
            "The practitioner identity is fixed at token-decode time."
        )

    def has_role(self, role: str) -> bool:
        return role in self.roles  # type: ignore[operator]


async def get_current_practitioner(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> AuthenticatedPractitioner:
    """
    FastAPI dependency: validate token and return the authenticated practitioner.
    The practitioner ID comes ONLY from the token claim 'fhir_practitioner_id'.
    """
    payload = await _decode_token(credentials.credentials)

    practitioner_id: str | None = payload.get("fhir_practitioner_id")
    if not practitioner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not contain fhir_practitioner_id claim. "
                   "Ensure the Keycloak realm is configured correctly.",
        )

    username: str = payload.get("preferred_username", "")
    realm_access: dict = payload.get("realm_access", {})
    roles: list[str] = realm_access.get("roles", [])

    if "clinician" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have the 'clinician' role.",
        )

    return AuthenticatedPractitioner(
        practitioner_id=practitioner_id,
        username=username,
        roles=roles,
    )


# Alias for use as a type annotation in routers
CurrentPractitioner = Annotated[AuthenticatedPractitioner, Depends(get_current_practitioner)]

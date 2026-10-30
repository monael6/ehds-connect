"""
config.py – Settings loaded from environment variables.
"""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    fhir_base_url: str = os.environ.get("FHIR_BASE_URL", "http://hapi-fhir:8080/fhir")
    keycloak_url: str = os.environ.get("KEYCLOAK_URL", "http://keycloak:8180")
    keycloak_realm: str = os.environ.get("KEYCLOAK_REALM", "hackathon")
    keycloak_client_id: str = os.environ.get("KEYCLOAK_CLIENT_ID", "ips-backend")
    keycloak_client_secret: str = os.environ.get("KEYCLOAK_CLIENT_SECRET", "change-me")
    frontend_origin: str = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
    draft_retention_days: int = int(os.environ.get("DRAFT_RETENTION_DAYS", "30"))

    @property
    def jwks_uri(self) -> str:
        return (
            f"{self.keycloak_url}/realms/{self.keycloak_realm}"
            f"/protocol/openid-connect/certs"
        )

    @property
    def issuer(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

"""
main.py – FastAPI application entry point.

Security headers, CORS (restricted to frontend origin), router registration.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routers import approve, documents, drafts, history, patients, pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")

app = FastAPI(
    title="IPS Hackathon Backend",
    description="Backend for AI-assisted IPS/discharge summary generation. All outputs are drafts requiring clinical review.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS (restricted to configured frontend origin) ───────────────────────────
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    # Note: HSTS would be set by the nginx reverse proxy in production
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(patients.router)
app.include_router(documents.router)
app.include_router(pipeline.router)
app.include_router(drafts.router)
app.include_router(approve.router)
app.include_router(history.router)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


# ── Startup log ───────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event() -> None:
    logger.info(
        "IPS Backend started. FHIR=%s Keycloak=%s CORS=%s",
        settings.fhir_base_url,
        settings.keycloak_url,
        settings.frontend_origin,
    )

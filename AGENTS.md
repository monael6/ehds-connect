# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Structure

Full-stack EHDS (European Health Data Space) demo — Clinical AI Hackathon Vienna 2026, Track 3.
- `backend/` — FastAPI + DuckDB (Python 3.10+)
- `frontend/` — React 19 + TanStack Router + Vite (Bun as package manager)
- `patients/` — Synthetic patient data (P001–P006), used by the patientSummary pipeline
- `pipeline/` — LLM-based IPS discharge-summary pipeline (separate from `backend/app/engine/`)

## Commands

**Backend** (run from `backend/`):
```
uvicorn app.main:app --port 8000     # dev server
pytest                               # all tests
pytest tests/test_api.py::test_name  # single test
```
Most backend tests skip unless `backend/data/patients.csv` exists — the `@needs_data` marker and `store` fixture auto-skip when CSV files are absent.

**Frontend** (run from `frontend/`):
```
bun run dev           # vite dev server (port 5173)
bun run test          # vitest run (once)
bun run test:watch    # vitest watch
bun run lint          # eslint
bun run format        # prettier --write .
```
Single frontend test: `bun run test -- --reporter=verbose src/test/rules.test.ts`

## Critical Architecture

- **`backend/app/datastore.py`**: Loads 5 CSVs into DuckDB: `raw` (as-is), `kis` (primary-use canonical), `hdab` (opted-out patients removed). Column names fuzzy-mapped via `ALIASES` dict — never assume exact CSV column names.
- **`backend/app/state.py`**: In-memory SQLite for session/audit/decisions. `state.connect(":memory:")` in every test fixture — tests never share state. Modules can extend `state.SCHEMA` at import time (see `ips_pipeline.py`).
- **`frontend/src/api.ts`**: Every API call uses `live<DTO, T>(path, mapper, syntheticFallback, init?, as?)`. Backend unreachable → silent synthetic fallback. Non-GET failures throw. Never call `fetch` directly.
- **`frontend/src/lib/backend-mappers.ts`**: All DTO→UI conversions. Never inline in components or `api.ts`.
- **`frontend/src/lib/rules.ts`**: Access rules (`decideAccess`) and EHDS decision logic. UI never duplicates rule logic.

## Env Vars (Backend)

| Variable | Default |
|---|---|
| `EHDS_DATA_DIR` | `backend/data` |
| `EHDS_VAR_DIR` | `backend/var` |
| `EHDS_REQUESTS_DIR` | `backend/requests` |
| `EHDS_REFERENCE_DATE` | `2025-12-31` |
| `ANTHROPIC_API_KEY` | _(unset → `settings.llm_enabled = False`)_ |
| `EHDS_LLM` | `1` (set to `0` to force-disable LLM even with key set) |
| `VITE_API_BASE` (frontend) | `http://localhost:8000` |

**Pipeline-only LLM** (`pipeline/llm_client.py`): uses `LLM_PROVIDER` (openai/azure_openai/local_ollama) + `OPENAI_API_KEY` — distinct from the backend's `ANTHROPIC_API_KEY`.

## Code Style

**Frontend**: Prettier (printWidth 100, double quotes, trailing commas all). Path alias `@/` maps to `frontend/src/` (injected by `@lovable.dev/vite-tanstack-config` — never configure it manually in `vite.config.ts`).

**Backend**: `from __future__ import annotations` at top of every module. Pydantic v2 for all request/response models. Writes via `state.tx()`, reads via `state.query()` / `state.one()`.

## Gotchas

- **`vite.config.ts`**: Uses `@lovable.dev/vite-tanstack-config` which already bundles TanStack, React, Tailwind, Nitro, tsconfig paths, and the `@` alias. Adding any of these manually duplicates plugins and breaks the build.
- **`routeTree.gen.ts` is generated**: Never edit it. Add route files under `frontend/src/routes/`; the TanStack Router Vite plugin regenerates the tree on `bun run dev`.
- **Frontend tests live in `src/test/`**: Not co-located with source. The vitest `include` pattern is `src/**/*.{test,spec}.{ts,tsx}` — tests anywhere in `src/` are picked up.
- **`EHDS_VAR_DIR` in tests**: `conftest.py` sets it to a `tempfile.mkdtemp()` — tests must not write to `backend/var/`.
- **`DataStore` column access**: Use `store.sql()` or `store.scalar()` — never `store.con.execute()` from outside `datastore.py` (lock not acquired).
- **DuckDB schemas**: Business logic queries `kis.*` (primary) or `hdab.*` (secondary). Never query `raw.*`.
- **`patients/` ≠ `backend/data/`**: `patients/` is ground-truth JSON for the LLM pipeline; `backend/data/` is the Track-3 CSV dataset for the main API.

## Lovable Integration (Frontend)

The `frontend/` is connected to [Lovable](https://lovable.dev). **Never force-push, rebase, amend, or squash already-pushed commits** — this breaks Lovable's project history.

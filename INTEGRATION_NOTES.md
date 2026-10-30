# Integration Notes — `integration/ps-backend-into-connect`

Branch created from `feature/connect-frontend`, integrating the LLM pipeline
backend from `patientSummary` without taking Keycloak, HAPI FHIR, or the
patientSummary frontend.

---

## What was taken (unchanged)

| Source path | Destination | Notes |
|---|---|---|
| `pipeline/*.py` (all 9 modules) | `pipeline/` (repo root) | models, gate, pseudonymize, llm_client, extract, verify_quotes, terminology, fhir_mapping, validate, evaluate, summary, crypto |
| `terminology/*.json` | `terminology/` | icd10_lookup, atc_lookup, snomed_stub |
| `patients/P001–P006/` | `patients/P001–P006/` | Synthetic test dataset (patient.json, documents.json, ground_truth_ips.json, traps.md) |
| `output/P001/` | `output/P001/` | Sample run artefacts for reference |

---

## What was dropped

| Component | Reason |
|---|---|
| Keycloak OIDC auth | `connect-frontend` uses its own custom token + SQLite session system |
| HAPI FHIR server | `connect-frontend` uses DuckDB (analytics) + SQLite (state/sessions) |
| `patientSummary` React frontend | `connect-frontend` has its own frontend; no frontend changes in this branch |
| `patientSummary` FastAPI routers (`api/`, `routers/`) | Replaced by the new `ips_pipeline.py` adapter |
| `validator_cli.jar` / FHIR structural validation | Java dependency not present; step is skipped with a warning written to the draft |

---

## What was adapted / created

### `backend/app/primary/ips_pipeline.py` *(new)*

Adapter module that bridges `pipeline/` with the `connect-frontend` auth and
state system.

| Function | Purpose |
|---|---|
| `run_pipeline(pid, user)` | Runs all 9 pipeline steps for a patient document bundle; stores the result as a `draft` row in the `ips_drafts` SQLite table; writes an audit log entry |
| `approve_draft(draft_id, user)` | Sets `status=approved`, records clinician name and timestamp, writes audit log |
| `_load_patient_docs(pid)` | Reads `patients/{pid}/patient.json` + `documents.json` |
| `_patients_dir()` | Resolves the `patients/` directory relative to `settings.data_dir` |
| `_latest_draft(pid)` | Queries the most recent draft row for a patient |
| `_parse_draft(row)` | Deserialises JSON columns before returning to the API |

**Schema extension:** `_IPS_SCHEMA` is appended to `state.SCHEMA` at import time, so `state.connect()` automatically creates the `ips_drafts` table. No manual migration needed.

**Lazy imports:** All `pipeline.*` imports happen inside `run_pipeline()`. This keeps the `connect-frontend` backend bootable even when the optional pipeline deps (openai, cryptography, etc.) are not installed.

---

### `backend/app/main.py` — 3 new endpoints

```
POST /api/patients/{pid}/ips-pipeline
```
- Auth: `HOSPITAL` role required
- Runs (or re-runs) the LLM pipeline for the patient; pseudonymises before any LLM call
- Returns `201` with the draft JSON (`status`, `patient_id`, `summary_md`, `fhir_bundle`, `warnings`)
- Returns `503` when no LLM API key is configured
- Returns `404` when neither the KIS DB nor a document bundle exists for the patient

```
GET /api/patients/{pid}/ips-pipeline
```
- Auth: `HOSPITAL` role required
- Returns the latest draft; `404` with a helpful message if none exists yet

```
POST /api/patients/{pid}/ips-pipeline/approve
```
- Auth: `HOSPITAL` role required
- Approves the latest draft; sets `status=approved`, records `approved_by` and `approved_at`
- Returns `409` if already approved

**Authorization guard — `_own_patient_or_bundle`:**
The three new endpoints use a dedicated auth helper instead of `_own_patient`:

- If the patient exists in DuckDB (`kis.patients`) → enforces the `data_holder` treatment-relationship rule (same as all other patient endpoints).
- If the patient is **not** in DuckDB but `patients/{pid}/patient.json` exists → grants access to any authenticated `HOSPITAL` user. This allows the synthetic P001–P006 test bundles to work without needing DuckDB entries.

---

### `backend/requirements.txt`

Added pipeline dependencies:
```
pyyaml
requests
cryptography
python-dotenv
openai
```

---

### `backend/tests/test_ips_pipeline.py` *(new)*

7 tests, all mocked (no real LLM call):

| Test | Assertion |
|---|---|
| `test_404_when_no_draft` | GET before any POST → 404 |
| `test_201_creates_draft` | POST with mocked pipeline → 201, correct shape |
| `test_draft_retrievable_after_run` | POST then GET → 200, status=draft |
| `test_approve_sets_status` | Approve → status=approved, approved_by set |
| `test_double_approve_returns_409` | Second approve → 409 |
| `test_approve_unauthenticated_returns_401` | No token → 401 |
| `test_503_when_no_llm_key` | LLMClient raises EnvironmentError → 503 |

Pipeline steps mocked at `pipeline.<module>.<function>` level (lazy import path).
`sys.path` insert ensures `pipeline/` at repo root is importable from `backend/tests/`.

All 33 tests pass: `python -m pytest tests/ -v` from `backend/`.

---

## API compatibility

No existing `connect-frontend` endpoints were changed.  All new endpoints are
additive and follow the same auth, error, and response conventions as the rest
of `main.py`.

---

## How to run end-to-end (hackathon demo)

```bash
# From repo root — install pipeline deps in addition to backend deps
pip install -r backend/requirements.txt

# Set LLM provider (example: OpenAI)
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# Start backend
cd backend
uvicorn app.main:app --reload

# Run pipeline for synthetic patient P003
curl -X POST http://localhost:8000/api/patients/P003/ips-pipeline \
     -H "Authorization: Bearer <token>"

# Retrieve draft
curl http://localhost:8000/api/patients/P003/ips-pipeline \
     -H "Authorization: Bearer <token>"
```

Supported `LLM_PROVIDER` values: `openai`, `azure`, `ollama` (see `pipeline/llm_client.py`).
FHIR structural validation is skipped in this deployment (no `validator_cli.jar`);
a warning is added to the draft's `warnings` list.

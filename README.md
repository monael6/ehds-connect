# EHDS Connect

### One Health Data Space. Three Pathways.

**EHDS Connect** is a full-stack demo platform built for the **Clinical AI Hackathon Vienna 2026 — Track 3: European Health Data Space (EHDS)**.

It shows how health data can support individual patient care and medical research at the same time, while keeping privacy, transparency, and access control as first-class concerns.

---

## What it does

EHDS Connect covers two dimensions of the European Health Data Space.

**Primary use — patient care**
- Hospital patient list and structured KIS records for six synthetic patients (P001–P006)
- On-demand Patient Summary in DE / EN / IT, generated from coded data with source references
- Discharge letter workflow: write → sign with a FIDO2/WebAuthn key → release to ELGA and GP
- Cross-border access with consent, identity check, and emergency fallback — all logged and visible to the patient

**Secondary use — health data research**
- Guided request wizard for applicants (Art. 53, 54, 67, 69 EHDS)
- Deterministic decision engine: prohibited-purpose check → eligibility → rule-based approve/reject with article citations
- Statistics pipeline: SQL over the opted-out-removed `hdab` schema, small-cell suppression (< 10 → `<10`)
- Secure Processing Environment (SPE): per-application DuckDB file, downloads always 403, analysis returns aggregates only
- HDAB staff inbox: review, approve, reject, request more information

**AI Patient Summary (P001–P006 only)**  
Clinical documents are pseudonymised and sent to OpenAI (`gpt-4o` by default). The model lists key points with source references and draws no conclusions. Output is a draft until a doctor explicitly approves it. The 20,000-patient research dataset is never sent to an LLM.

---

## Project layout

```
backend/      FastAPI + DuckDB + SQLite (Python 3.10+)
frontend/     React 19 + TanStack Router + Vite (Bun)
patients/     Synthetic patient bundles P001–P006 (documents + ground truth IPS)
pipeline/     LLM-based IPS / discharge-summary pipeline (standalone)
terminology/  Code lists used by the parser (ICD-10, ATC, LOINC)
tests/        Root-level integration tests (jury-style requests)
```

---

## Quick start

### Backend

Requires Python 3.10+.

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

- Interactive API docs: http://localhost:8000/docs
- Run the 10 official metric requests: `python scripts/evaluate.py`
- Tests: `pytest -q`

### Frontend

Requires [Bun](https://bun.sh).

```bash
cd frontend
bun install
bun run dev        # http://localhost:8080
```

> **Note:** `npm install && npm run dev` also works if you don't have Bun.

---

## Demo accounts

All passwords are `demo1234`. Sign in at http://localhost:8080.

| User ID | Email | Role |
|---|---|---|
| `u-huber` | anna.huber@klinikum-west.at | Senior Doctor |
| `u-berger` | markus.berger@klinikum-west.at | Doctor |
| `u-gruber` | thomas.gruber@klinikum-west.at | Hospital IT Admin |
| `u-novak` | petra.novak@hdab.gv.at | HDAB Staff |
| `u-weiss` | lena.weiss@uni-graz.at | Researcher / Applicant |
| `u-muster` | — | Patient portal (Frau M., opted out of research) |
| `u-rossi` | — | Foreign doctor in Italy (cross-border, simulated) |

New hospital accounts stay pending until the IT Admin activates them.  
If the backend is not running, pages show synthetic fixtures labelled **"Synthetic fallback"**.

---

## Environment variables

### Backend

| Variable | Default | Description |
|---|---|---|
| `EHDS_DATA_DIR` | `backend/data` | Track-3 CSV dataset |
| `EHDS_VAR_DIR` | `backend/var` | SQLite state + SPE files |
| `EHDS_REQUESTS_DIR` | `backend/requests` | Request JSON files |
| `EHDS_REFERENCE_DATE` | `2025-12-31` | Used for age and active-medication calculations |
| `ANTHROPIC_API_KEY` | _(unset)_ | Enables the Anthropic LLM path in the backend engine |
| `EHDS_LLM` | `1` | Set to `0` to force-disable LLM even when the key is set |
| `OPENAI_API_KEY` | _(unset)_ | Used by the AI Patient Summary pipeline |
| `OPENAI_MODEL` | `gpt-4o` | Model for the pipeline (also supports Azure OpenAI and Ollama via `LLM_PROVIDER`) |

Create `backend/.env` or `.env` at the repo root (both are Git-ignored). Existing environment variables take precedence.

### Frontend

| Variable | Default |
|---|---|
| `VITE_API_BASE` | `http://localhost:8000` |

---

## Roles and access control

FastAPI enforces every rule below. The UI only shows or hides buttons.

| Category | Role | Permissions |
|---|---|---|
| Healthcare | Senior Doctor | Write, sign, and release discharge letters; authorise other doctors to release |
| Healthcare | Doctor | Write and edit letters; sign and release only when authorised by a senior doctor |
| Healthcare | IT Admin | Manage accounts, assign roles, revoke permissions, block lost keys, issue recovery codes — no patient data |
| Institute | HDAB Staff | Review applicant requests: approve, reject, or request more information |
| Researcher | Applicant | Submit requests via guided wizard; see results only after approval |
| Patient | Patient portal | View own records, set research opt-out, see cross-border access log |

---

## Discharge letter signing

The six-digit PIN is replaced by a digital signature. The backend issues a one-time challenge bound to the letter; the doctor signs it with a **FIDO2/WebAuthn** key (NFC hospital badge, USB/NFC security key, or Touch ID). Only public keys are stored server-side.

For the demo, a clearly-labelled **simulated P-256 key** (WebCrypto, lives only in the current browser tab) is available.

**Lost key procedure:**
1. Report the key lost — it is blocked immediately.
2. Sign with a previously registered backup key.
3. If no backup key exists, the IT Admin verifies the doctor's photo ID in person and issues a one-time recovery code (valid 24 h, registers exactly one new key).
4. Until recovery is complete, a senior doctor countersigns.

---

## Metric results (10 official Track-3 requests, 3 runs each)

| Metric | Result | Target |
|---|---|---|
| Correct decisions | 10 / 10 | 10 / 10 |
| Correct numbers | 6 / 6 | 6 / 6 |
| Privacy leaks | 0 | 0 |
| Consistency across 3 runs | 10 / 10 | 10 / 10 |
| Slowest response | 0.07 s | < 60 s |

Nine additional jury-style requests (`backend/tests/jury/`) cover `primary_icd10` filters, grouping by `data_holder` / sex / region, threshold on latest measurement, custom age bands, emergency visits, a marketing rejection, and a second SPE. Verified against hand-written SQL in `tests/test_jury.py`.

---

## Architecture

```
Request JSON ──► Decision engine ──► REJECT (Art. 54) ──────────────────────► answer + reasons
                 (rules, Art. 54/53/66/68/69/73)
                        │ approve
                        ▼
                 Request parser ──► Spec (criteria, groups, metrics)
                 (definitions → ICD-10/ATC/LOINC,
                  code lists in terminology/)
                        │
                        ▼
                 SQL generator ──► DuckDB "hdab" schema
                 (bound parameters)   (opted-out patients removed)
                        │
                        ├──► statistics (small-cell rule: < 10 → suppressed)
                        └──► SPE file (cohort + named record types, no download)

SQLite: users / roles / sessions, decisions, discharge letters + versions, audit log
```

### Key components

| Component | File | What it does |
|---|---|---|
| Data loader | `backend/app/datastore.py` | Loads 5 CSVs into DuckDB: `raw` (as-is), `kis` (primary-use canonical), `hdab` (opted-out removed). Column names fuzzy-mapped via `ALIASES`. |
| Decision engine | `backend/app/engine/decision.py` | Checks prohibited purposes (Art. 54 a–e) first, then eligibility, then approves or rejects with article citations and quoted sentences. |
| Request parser | `backend/app/engine/parser.py` | Reads per-request definitions (ICD-10, ATC, LOINC, sex, age bands, encounter type, active medication, latest measurement). Builds the subject and one metric per `Report per …:` line. |
| SQL generator | `backend/app/engine/query.py` | Template SQL with bound parameters on the `hdab` schema. Every group shown even if empty. |
| Small-cell rule | `backend/app/engine/smallcell.py` | Counts < 10 → `<10`; percentages / means with n < 10 → `suppressed`. One decimal, `ROUND_HALF_UP`. |
| SPE | `backend/app/engine/spe.py` | One DuckDB file per approved application in `var/spe/`. Downloads always 403. Analysis returns aggregates only. |
| Permit checklist | `backend/app/engine/permit.py` | Art. 68 criteria (allowed purpose, necessity, proportionality, qualification, safeguards, ethics, legal basis) for staff view. |
| App state | `backend/app/state.py` | SQLite transactions: users, sessions, decisions, provisions, consents, discharge letters + versions, audit log. |
| Auth | `backend/app/auth.py` | Bearer token, role enforced on every endpoint. |
| Primary use | `backend/app/primary/` | Patient Summary on demand, discharge letter workflow, cross-border access rules. |
| Evaluation | `backend/scripts/evaluate.py` | Runs 10 requests × 3, compares with `expected.json`, checks for leaks, measures time. |

### Technology choices

- **DuckDB** for analysis — reads CSVs directly, milliseconds for 20,000 patients, one file per SPE.
- **SQLite** for mutable state — transactions, no server needed.
- **No LLM for research data** — the decision engine, parser, SQL, and numbers are deterministic Python + SQL. Results are identical across runs. The 20,000-patient dataset never leaves the app.
- **Production would use:** PostgreSQL for state, a FHIR server for primary use, a dedicated analytical store for the HDAB.

---

## API reference (main endpoints)

| Area | Endpoints |
|---|---|
| Auth | `GET /api/auth/accounts`, `POST /api/auth/login`, `GET /api/me` |
| HDAB | `POST /api/requests/evaluate`, `GET /api/requests`, `GET /api/requests/{id}`, `POST /api/requests/{id}/confirm`, `POST /api/requests/{id}/ask-info`, `GET /api/metrics` |
| SPE | `GET /api/spe/{id}`, `GET /api/spe/{id}/analysis`, `POST /api/spe/{id}/download` (always 403) |
| Public | `GET /api/catalogue`, `GET /api/register`, `POST /api/eligibility` |
| Hospital | `GET /api/patients`, `GET /api/patients/{id}/summary?lang=`, `GET /api/patients/{id}/documents` |
| Discharge letter | `POST /api/discharge-letters`, `GET /api/discharge-letters/{id}`, `PUT …/sections/{key}`, `POST …/sign`, `POST …/correct`, `POST …/send` |
| Patient / cross-border | `GET /api/portal/me`, `PUT /api/portal/consent`, `POST /api/cross-border/check`, `POST /api/cross-border/patient-summary` |
| Audit | `GET /api/audit`, `GET /api/audit/mine` |

---

## Known limitations

- **Parser coverage:** understands the definition style of the 10 Track-3 requests. Requests written very differently are answered with the parts the parser recognises; unrecognised definitions appear in `spec.notes` in the staff view.
- **Research data gaps:** the Track-3 dataset has no allergy, dose, or progress-note fields — discharge letters for those 20,000 patients mark those sections as missing. P001–P006 have full document bundles.
- **Simulated integrations:** ELGA, MyHealth@EU / NCPeH, and ID Austria are simulated. WebAuthn signing works with software keys in the browser; no real NFC/USB hardware has been tested against this build.
- **AI summary is a draft:** the LLM output can vary between runs and must be approved by a clinician before it is treated as authoritative.

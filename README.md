# EHDS Connect

### One Health Data Space. Three Pathways.

**EHDS Connect** is a healthcare platform developed for the **Clinical AI Hackathon Vienna 2026**, focusing on Track 3: *European Health Data Space (EHDS)*.

Our project explores how health data can support both individual patient care and medical research while maintaining privacy, transparency, and responsible data access.

## Our Vision

Health data should be accessible when it is needed, protected when it matters, and useful beyond institutional and national borders.

EHDS Connect brings together two fundamental dimensions of the European Health Data Space:

- **Primary Use:** Supporting healthcare professionals with structured patient information for national and cross-border treatment.
- **Secondary Use:** Enabling responsible health research through controlled data access, transparent approval processes, and privacy-preserving analysis.

Our vision is to demonstrate how these two dimensions can coexist within one connected healthcare ecosystem.

## What We Are Building

EHDS Connect consists of three interconnected pathways.

### 1. Secondary Use – Research & Health Data Access

Our core hackathon challenge focuses on supporting Health Data Access Bodies (HDABs) in evaluating requests for the secondary use of health data.

The research portal is designed to:

- Accept and process research applications.
- Evaluate requests against defined EHDS rules.
- Provide transparent, explainable access decisions.
- Support privacy-preserving statistical analysis.
- Respect patient opt-outs and data protection requirements.
- Demonstrate controlled access through a simulated Secure Processing Environment (SPE).

### 2. Primary Use – National Patient Care

The national patient care portal demonstrates how structured health information can support healthcare professionals within Austria.

It focuses on patient summaries, relevant medical information, and clinical documentation.

### 3. Primary Use – Cross-Border Patient Care

The cross-border care portal explores how essential patient information can remain understandable and accessible when a patient receives medical treatment in another European country.

Through multilingual patient summaries and emergency-oriented views, the platform demonstrates the potential of interoperable healthcare across borders.

## Our Demonstration: One Patient, Three Pathways

To connect these scenarios, we follow a synthetic patient, **Frau M.**, through different healthcare situations.

In Vienna, her medical information supports clinical care. During an emergency in Italy, essential information can be presented to healthcare professionals in another language.

At the same time, her decision to opt out of secondary data use is respected, ensuring that her records are excluded from research processing.

**One patient. Three pathways. One connected European Health Data Space.**

---


## Run the backend

Requires Python 3.10+. The Track-3 data (`data/`, `requests/`) is in `backend/`.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

- API docs: http://localhost:8000/docs
- Metrics on the 10 requests: `python scripts/evaluate.py`
- Tests: `python -m pytest -q`

Quick check without signing in (works for new requests too):

```bash
curl -s -X POST localhost:8000/api/requests/evaluate -H 'Content-Type: application/json' -d '{"id":"R01"}'
curl -s -X POST localhost:8000/api/requests/evaluate -H 'Content-Type: application/json' -d @requests/R05.json
```

## Run the whole app

Start the backend as above, then in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:8080 and pick a demo account on the start page: Huber (hospital), Novak (HDAB staff), Weiss (researcher) or "Browse without account". Each account signs in to the backend as the same person, so every page reads and writes through FastAPI and the backend checks the role. If the backend is not running, the pages show synthetic fixtures and label them "Synthetic fallback". Another API address can be set with `VITE_API_BASE`.

The cross-border walkthrough (Primary use → Cross-border) acts as Frau M. in her portal (`u-muster`) and as the doctor in Italy (`u-rossi`).

## Roles, digital signatures and request review

| Category | Role | Can do |
|---|---|---|
| Healthcare | Senior Doctor | Write, sign and release discharge letters to ELGA and the GP; authorise doctors to release |
| Healthcare | Doctor | Write and edit letters; sign and release only when a senior doctor has authorised them |
| Healthcare | IT Admin | Activate accounts, assign roles, revoke permissions, block lost keys, issue recovery codes. No patient data |
| Institute | HDAB Staff | Review applicant requests: approve, reject or ask for more information |
| Researcher / Applicant | Applicant | Submit requests with the guided wizard (Art. 53, 54, 67, 69); see results only after approval |

FastAPI enforces every rule above. The UI only hides buttons.

Demo accounts (password `demo1234`): `anna.huber@klinikum-west.at` (Senior Doctor), `markus.berger@klinikum-west.at` (Doctor), `thomas.gruber@klinikum-west.at` (IT Admin), `petra.novak@hdab.gv.at` (HDAB Staff), `lena.weiss@uni-graz.at` (Applicant). New hospital accounts stay pending until the IT Admin activates them.

**Signing discharge letters.** The six-digit code is replaced by a digital signature. The backend issues a one-time challenge bound to the letter, and the doctor signs it with a FIDO2/WebAuthn key: an NFC hospital badge, a USB/NFC security key or Touch ID. Only public keys are stored. Without hardware, a clearly labelled simulated P-256 key (WebCrypto, kept in the browser tab's memory only) can be used for the demo.

**If the key is lost:**
1. Report it lost. The key is blocked immediately.
2. Sign with a backup key registered earlier.
3. With no backup key, the IT Admin checks the doctor's photo ID in person and issues a one-time recovery code. It is valid for 24 hours and registers exactly one new key.
4. Until then, a senior doctor signs.

## Metric results (10 official requests, 3 runs each)

| Metric | Result | Target |
|---|---|---|
| Correct decisions | 10 of 10 | 10 of 10 |
| Correct numbers | 6 of 6 | 6 of 6 |
| Privacy leaks | 0 | 0 |
| Consistency over 3 runs | 10 of 10 | 10 of 10 |
| Slowest answer | 0.07 s (R05, creates the SPE) | under 60 s |

Nine additional jury-style requests (`backend/tests/jury/`) filter inpatient stays by `primary_icd10`, group by `data_holder`, by sex and region, use thresholds on the latest measurement, custom age bands, emergency visits, a marketing rejection and a second SPE. Their numbers are checked against independently hand-written SQL in `tests/test_jury.py`.

## Technical architecture

```
request JSON ──► Decision engine ──► REJECT (Art. 54) ─────────────────────────────► answer + reasons (EN/DE/IT)
                 (rules, Art. 54/53/66/68/69/73)
                        │ approve
                        ▼
                 Request parser ──► Spec (criteria, groups, metrics) ──► SQL generator ──► DuckDB "hdab" schema
                 (definitions → ICD-10/ATC/LOINC,                                          (opted-out removed)
                  code lists in the data)                                                       │
                        │                                                        statistics ◄───┤───► SPE file
                        ▼                                                     (small-cell rule)     (cohort + requested
                 Art. 68 checklist, term mapping, SQL ──► staff view                                  record types, no download)

SQLite: users/roles, decisions, provisions, consents, discharge letters + versions, audit log
```

| Component | File | What it does |
|---|---|---|
| Data loader | `app/datastore.py` | Loads the 5 CSVs into DuckDB with three schemas like the real EHDS: `raw` (files), `kis` (clinical view for treatment), `hdab` (secondary-use copy without the 839 opted-out patients). Ages are 2025 minus birth year (data README). |
| Decision engine | `app/engine/decision.py` | The required order: prohibited purpose (Art. 54 letters a–e: insurance pricing, employment, marketing, re-identification, harmful products) → `health data request` → access application that explains why statistics are not enough → other access application. Cites articles and quotes the sentences it used as evidence. |
| Request parser | `app/engine/parser.py` | Reads each request's own definitions (`Name = ICD-10 code starting with …`, `ATC …`, `LOINC …`, `sex 'female'`, `encounter with type …`, `primary_icd10 …`, age bands, active-medication rule, `Use the latest …`, `A / B × 100`). Builds the subject from the question and one metric per item of the `Report per …:` line; "of them", "their" and "that share" refer to the previous item. Undefined terms are mapped through the code lists in the data and a small synonym list. Nothing is written per request. |
| SQL generator + small-cell rule | `app/engine/query.py`, `app/engine/smallcell.py` | Template SQL with bound parameters on the `hdab` schema. Every requested group is shown, even empty ones. Counts < 10 → `<10`; percentages with numerator or denominator < 10 and means of < 10 patients → `suppressed`; one decimal, halves up (`Decimal.ROUND_HALF_UP`). |
| Secure processing environment | `app/engine/spe.py` | One DuckDB file per approved application (`var/spe/SPE-R05.duckdb`) with only the cohort and the named record types (R05: conditions, medications, HbA1c only), patient IDs kept. Downloads always return 403 and are logged; analysis returns aggregates only. |
| Permit checklist | `app/engine/permit.py` | Art. 68 criteria per decision (allowed purpose, not prohibited, necessary and proportionate, why anonymised data is not enough, qualification, safeguards, ethics, legal basis) as yes / no / to be checked by staff. Also the eligibility wizard for interested parties. |
| App state | `app/state.py` | SQLite (transactions, one file): users and sessions, decisions, provisions by hospitals, consents, discharge letters with versions and edit history, audit log. |
| Roles | `app/auth.py` | Demo accounts, bearer token, role checked on every endpoint: hospital (primary use + data-provision inbox), HDAB staff (all requests, staff view, audit), interested party (own requests, public catalogue/register), patient (portal), foreign doctor (cross-border, simulated). |
| Primary use | `app/primary/` | Patient Summary on demand in DE/EN/IT from the codes (not free translation), emergency strip; discharge letter in the ELGA section order with a source per statement, "No data in the KIS" instead of invented content, versioned edits, signing with confirmation + second factor, blocked while required sections are empty, read-only after signing, corrections as new versions, sending only when signed; cross-border access rules with consent, identity check and emergency access, all logged and visible to the patient. |
| Evaluation | `scripts/evaluate.py` | Runs the 10 requests 3 times, compares with `expected.json` (layout-independent), checks for leaks (patient IDs, counts < 10, unsuppressed values, opted-out patients) and measures time. |

**Models and services:** none. Decisions, mapping, SQL and numbers are deterministic Python and SQL, so results are identical across runs and no data leaves the app. An LLM could be added later as a second opinion on the request text only (allowed by the rules); it is not used for any result above.

**Database choice:** DuckDB for analysis (reads the CSVs directly, milliseconds for 20,000 patients, one file per SPE). SQLite for state that changes (transactions, no server). In production: PostgreSQL for state, a FHIR server for primary use, a separate analytical store for the HDAB.

### Main endpoints

| Area | Endpoint |
|---|---|
| Sign in | `GET /api/auth/accounts`, `POST /api/auth/login {user_id}`, `GET /api/me` |
| HDAB | `POST /api/requests/evaluate`, `GET /api/requests`, `GET /api/requests/{id}`, `POST /api/requests/{id}/confirm`, `POST /api/requests/{id}/ask-info`, `GET /api/requests/samples`, `GET /api/metrics` |
| SPE | `GET /api/spe/{id}`, `GET /api/spe/{id}/analysis`, `POST /api/spe/{id}/download` (always 403) |
| Public | `GET /api/catalogue`, `GET /api/register`, `GET /api/facilities-not-in-catalogue`, `POST /api/eligibility` |
| Hospital | `GET /api/provisions`, `POST /api/provisions/{id}/provide`, `PUT /api/catalogue/{data_holder}`, `GET /api/patients`, `GET /api/patients/{id}/summary?lang=` |
| Discharge letter | `POST /api/discharge-letters`, `GET /api/discharge-letters/{id}`, `PUT …/sections/{key}`, `POST …/sign`, `POST …/correct`, `POST …/send` |
| Patient / abroad | `GET /api/portal/me`, `PUT /api/portal/consent`, `POST /api/cross-border/check` (decision only), `POST /api/cross-border/patient-summary` |
| Audit | `GET /api/audit` (HDAB, filters), `GET /api/audit/mine` |

Demo accounts: `u-novak` (HDAB staff), `u-weiss` (researcher), `u-public`, `u-huber` (Klinikum West), `u-muster` (Frau M., patient `p-4cfd3cf1`, opted out of research), `u-rossi` (doctor in Italy, simulated).

### What works and what does not

- Works: all five metrics on the 10 requests, the jury-style requests above, roles, audit log, SPE with blocked download, discharge-letter workflow, cross-border flow, and the frontend on top of all of it.
- Simulated: ELGA, MyHealth@EU / NCPeH, ID Austria and the second factor (any 6 digits).
- Limits: the parser understands the definition style of the Track-3 requests; a request written very differently is answered with the parts it recognises and lists unrecognised definitions in the staff view (`spec.notes`). The data has no allergies, doses or progress notes, so the letter marks those sections as missing.

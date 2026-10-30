"""EHDS Connect API.

Run:  uvicorn app.main:app --port 8000   (from backend/)
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import auth, catalogue, state
from .auth import FOREIGN_DOCTOR, HDAB, HOSPITAL, HOSPITAL_IT, INTERESTED, PATIENT
from .config import settings
from .datastore import get_store
from .engine import permit, spe
from .engine.pipeline import applicant_status_view, applicant_view, evaluate
from .primary import crossborder, letters, signature, summary

DEMO_HOSPITAL = "Klinikum West"


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.connect()
    store = get_store()
    holders = store.data_holders()
    auth.seed_users(DEMO_HOSPITAL if DEMO_HOSPITAL in holders else (holders[0] if holders else None))
    yield


app = FastAPI(title="EHDS Connect API", version="1.0",
              description="Health Data Access Body (secondary use) and primary use for the Clinical AI Hackathon Vienna 2026, "
                          "Track 3. Synthetic data only.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins + ["*"], allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ meta & auth
@app.get("/api/health")
def health():
    return {"status": "ok", "data": get_store().summary()}


@app.get("/api/auth/accounts")
def accounts():
    """Demo accounts for the sign-in screen (no passwords)."""
    rows = state.query("SELECT * FROM users WHERE status = 'active' AND id LIKE 'u-%' ORDER BY role, id")
    demo = {u["id"] for u in auth.DEMO_USERS}
    return [auth.public(r) for r in rows if r["id"] in demo]


class LoginIn(BaseModel):
    user_id: str | None = Field(None, examples=["u-novak"],
                                description="Demo shortcut: u-novak (HDAB), u-weiss (applicant), u-huber (senior doctor), "
                                            "u-berger (doctor), u-gruber (hospital IT admin), u-muster (patient), "
                                            "u-rossi (doctor in Italy), u-public")
    email: str | None = None
    password: str | None = None


@app.post("/api/auth/login")
def login(body: LoginIn):
    if body.email:
        return auth.login_password(body.email, body.password or "")
    if not body.user_id:
        raise HTTPException(422, "Enter email and password")
    return auth.login(body.user_id)


@app.get("/api/auth/registration-options")
def registration_options():
    """Categories and roles for the registration form."""
    return [
        {"category": "healthcare", "label": "Healthcare", "description": "Hospital staff",
         "roles": [{"id": auth.SENIOR, "label": "Senior Doctor"}, {"id": auth.DOCTOR, "label": "Doctor"},
                   {"id": auth.IT_ADMIN, "label": "IT Admin"}], "needs_activation": True,
         "hospitals": get_store().data_holders()},
        {"category": "institute", "label": "Institute", "description": "Health Data Access Body",
         "roles": [{"id": "hdab_staff", "label": "HDAB Staff"}], "needs_activation": False},
        {"category": "applicant", "label": "Researcher / Applicant",
         "description": "You submit data requests and receive results",
         "roles": [{"id": "applicant", "label": "Applicant"}], "needs_activation": False},
    ]


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str
    category: str = Field(examples=["applicant"])
    role: str = Field(examples=["applicant"])
    organisation: str = ""
    hospital: str | None = None


@app.post("/api/auth/register")
def register(body: RegisterIn):
    hospital = None
    if body.category == "healthcare":
        holders = get_store().data_holders()
        hospital = body.hospital if body.hospital in holders else (DEMO_HOSPITAL if DEMO_HOSPITAL in holders else None)
        if not hospital:
            raise HTTPException(422, "Choose your hospital")
    return auth.register(body.name, body.email, body.password, body.category, body.role, body.organisation, hospital)


@app.post("/api/auth/logout")
def logout(user: dict = Depends(auth.current_user)):
    auth.logout(user["token"])
    state.audit(user, "auth", "sign_out", outcome="ok")
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(auth.current_user)):
    return {"user": auth.public(user), "areas": sorted(auth.ROLE_AREAS[user["role"]])}


# ------------------------------------------------------------------ secondary use
def _requests_dir() -> Path:
    return settings.requests_dir


@app.get("/api/requests/samples")
def samples():
    out = []
    for p in sorted(_requests_dir().glob("R*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out.append({"id": r.get("id", p.stem), "applicant": r.get("applicant"), "purpose": r.get("purpose"),
                    "requested_as": r.get("requested_as"), "request": r})
    return out


@app.post("/api/requests/evaluate")
def evaluate_request(request: dict = Body(..., examples=[{"id": "R01"}]), view: str = Query("auto"),
                     user: dict | None = Depends(auth.optional_user)):
    """Decide a request and compute statistics or create the SPE.

    Works without sign-in (as an anonymous applicant) so the jury can post requests directly.
    HDAB staff get the full staff view (spec, code mapping, SQL, checklist)."""
    if user and user["role"] not in (HDAB, INTERESTED):
        raise HTTPException(403, f"You don't have access to this area with the role {user['role']}.")
    if set(request) == {"id"} and (_requests_dir() / f"{request['id']}.json").exists():
        request = json.loads((_requests_dir() / f"{request['id']}.json").read_text(encoding="utf-8"))
    if not request.get("definitions") and not request.get("purpose"):
        raise HTTPException(422, "A request needs at least a purpose and definitions")
    result = evaluate(request, get_store(), user)
    if user and user["role"] == INTERESTED:
        return applicant_status_view(result, "submitted", None)
    staff = (user and user["role"] == HDAB and view != "applicant") or (user is None and view == "staff")
    return result if staff else applicant_view(result)


@app.get("/api/requests")
def list_requests(user: dict = Depends(auth.require(HDAB, INTERESTED))):
    rows = state.query("SELECT request_id, submitted_by, applicant, purpose, requested_as, decision, articles, status, "
                       "staff_note, created_at, updated_at FROM decisions ORDER BY created_at DESC")
    if user["role"] == INTERESTED:
        rows = [r for r in rows if r["submitted_by"] == user["id"]]
    for r in rows:
        r["applicant"] = json.loads(r["applicant"] or "null")
        r["articles"] = json.loads(r["articles"])
    return rows


def _decision(rid: str) -> dict:
    row = state.one("SELECT * FROM decisions WHERE request_id = ?", (rid,))
    if not row:
        raise HTTPException(404, "Request not evaluated yet")
    row["result"] = json.loads(row["result"])
    return row


@app.get("/api/requests/{rid}")
def get_request(rid: str, user: dict = Depends(auth.require(HDAB, INTERESTED))):
    row = _decision(rid)
    if user["role"] == INTERESTED:
        if row["submitted_by"] != user["id"]:
            raise HTTPException(403, "You can only see your own requests.")
        return applicant_status_view(row["result"], row["status"], row["staff_note"])
    return {**row["result"], "status": row["status"], "staff_note": row["staff_note"]}


class StaffAction(BaseModel):
    note: str | None = None


@app.post("/api/requests/{rid}/confirm")
def confirm_decision(rid: str, body: StaffAction, user: dict = Depends(auth.require(HDAB))):
    _decision(rid)
    with state.tx() as c:
        c.execute("UPDATE decisions SET status='confirmed', staff_note=?, updated_at=? WHERE request_id=?",
                  (body.note, state.now(), rid))
        state.audit(user, "secondary", "decision_confirmed", request_id=rid, outcome="confirmed", details={"note": body.note}, conn=c)
    return {"request_id": rid, "status": "confirmed"}


@app.post("/api/requests/{rid}/reject")
def reject_request(rid: str, body: StaffAction, user: dict = Depends(auth.require(HDAB))):
    _decision(rid)
    if not (body.note or "").strip():
        raise HTTPException(422, "Give the applicant a reason for the rejection")
    with state.tx() as c:
        c.execute("UPDATE decisions SET status='rejected', staff_note=?, updated_at=? WHERE request_id=?",
                  (body.note, state.now(), rid))
        state.audit(user, "secondary", "request_rejected", request_id=rid, outcome="rejected", details={"note": body.note}, conn=c)
    return {"request_id": rid, "status": "rejected"}


@app.post("/api/requests/{rid}/ask-info")
def ask_info(rid: str, body: StaffAction, user: dict = Depends(auth.require(HDAB))):
    _decision(rid)
    with state.tx() as c:
        c.execute("UPDATE decisions SET status='more_information_requested', staff_note=?, updated_at=? WHERE request_id=?",
                  (body.note, state.now(), rid))
        state.audit(user, "secondary", "more_information_requested", request_id=rid, outcome="pending",
                    details={"note": body.note}, conn=c)
    return {"request_id": rid, "status": "more_information_requested"}


@app.get("/api/spe/{rid}")
def spe_info(rid: str, user: dict = Depends(auth.require(HDAB, INTERESTED))):
    info = spe.describe(rid)
    if not info:
        raise HTTPException(404, "No secure processing environment for this request")
    state.audit(user, "secondary", "spe_viewed", request_id=rid, outcome="ok")
    return info


@app.get("/api/spe/{rid}/analysis")
def spe_analysis(rid: str, user: dict = Depends(auth.require(HDAB, INTERESTED))):
    out = spe.aggregate(rid)
    if out is None:
        raise HTTPException(404, "No secure processing environment for this request")
    state.audit(user, "secondary", "spe_analysis", request_id=rid, outcome="aggregate_only")
    return {"note": "Analysis runs inside the SPE. Only aggregate output leaves it.", **out}


@app.post("/api/spe/{rid}/download", operation_id="spe_download")
@app.get("/api/spe/{rid}/download", operation_id="spe_download_get")
def spe_download(rid: str, user: dict | None = Depends(auth.optional_user)):
    """Always blocked (Art. 73): data never leaves the secure processing environment."""
    state.audit(user, "secondary", "spe_download_attempt", request_id=rid, outcome="blocked")
    raise HTTPException(403, {"blocked": True, "message": "Download blocked – data never leaves the secure processing "
                                                          "environment. This attempt has been logged."})


@app.get("/api/metrics")
def metrics(refresh: bool = False):
    path = settings.var_dir / "metrics.json"
    if refresh or not path.exists():
        import importlib.util
        spec_ = importlib.util.spec_from_file_location("evaluate", Path(__file__).resolve().parent.parent / "scripts" / "evaluate.py")
        mod = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(mod)
        conn = state.connect()
        try:
            report = mod.run(settings.requests_dir, store=get_store())
        finally:
            state._conn = conn  # evaluation used its own in-memory state
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report
    return json.loads(path.read_text(encoding="utf-8"))


# public
@app.get("/api/catalogue")
def get_catalogue():
    return catalogue.catalogue(get_store())


class CatalogueIn(BaseModel):
    title: str | None = None
    description: str | None = None


@app.put("/api/catalogue/{data_holder}")
def put_catalogue(data_holder: str, body: CatalogueIn, user: dict = Depends(auth.require(HOSPITAL))):
    if user["data_holder"] != data_holder:
        raise HTTPException(403, "You can only describe your own hospital's datasets.")
    catalogue.update_entry(data_holder, body.title, body.description, user)
    return [c for c in catalogue.catalogue(get_store()) if c["data_holder"] == data_holder][0]


@app.get("/api/register")
def get_register():
    return catalogue.register()


@app.get("/api/facilities-not-in-catalogue")
def facilities():
    return catalogue.FACILITIES_NOT_REGISTERED


@app.post("/api/eligibility")
def eligibility(answers: dict = Body(...)):
    return permit.eligibility(answers)


# hospital as data holder
@app.get("/api/provisions")
def provisions(user: dict = Depends(auth.require(HOSPITAL))):
    rows = state.query("""SELECT p.request_id, p.status, p.provided_at, p.provided_by, d.applicant, d.purpose, d.decision,
                          d.created_at AS decided_at, d.result FROM provisions p JOIN decisions d USING (request_id)
                          WHERE p.data_holder = ? AND d.decision != 'REJECT' ORDER BY d.created_at DESC""",
                       (user["data_holder"],))
    store = get_store()
    out = []
    for r in rows:
        res = json.loads(r.pop("result"))
        applicant = json.loads(r["applicant"] or "null")
        if r["decision"] == "APPROVE_SPE":
            what = {"type": "pseudonymised records for the SPE", "record_types": res.get("spe", {}).get("record_types"),
                    "patients_from_this_hospital": _spe_patients_from(store, r["request_id"], user["data_holder"])}
        else:
            what = {"type": "data for anonymised statistics (computed by the HDAB)",
                    "record_types": ["conditions", "medications", "observations", "encounters"]}
        out.append({**r, "applicant": applicant, "what": {**what, "pseudonymised": True, "opted_out_excluded": True}})
    return out


def _spe_patients_from(store, rid: str, dh: str):
    path = spe.spe_path(rid)
    if not path.exists():
        return None
    import duckdb
    con = duckdb.connect(str(path), read_only=True)
    try:
        ids = [r[0] for r in con.execute("SELECT patient_id FROM cohort").fetchall()]
    finally:
        con.close()
    if not ids:
        return 0
    return store.scalar(f"SELECT count(*) FROM kis.patients WHERE data_holder = ? AND patient_id IN ({','.join('?' * len(ids))})",
                        [dh, *ids])


@app.post("/api/provisions/{rid}/provide")
def provide(rid: str, user: dict = Depends(auth.require(HOSPITAL))):
    row = state.one("SELECT * FROM provisions WHERE request_id = ? AND data_holder = ?", (rid, user["data_holder"]))
    if not row:
        raise HTTPException(404, "No data request for your hospital")
    with state.tx() as c:
        c.execute("UPDATE provisions SET status='provided', provided_by=?, provided_at=? WHERE request_id=? AND data_holder=?",
                  (user["name"], state.now(), rid, user["data_holder"]))
        state.audit(user, "provision", "data_provided_to_hdab", request_id=rid, outcome="provided",
                    details={"data_holder": user["data_holder"]}, conn=c)
    return state.one("SELECT * FROM provisions WHERE request_id = ? AND data_holder = ?", (rid, user["data_holder"]))


# audit
@app.get("/api/audit")
def audit(user: dict = Depends(auth.require(HDAB)), user_id: str | None = None, role: str | None = None,
          area: str | None = None, patient_id: str | None = None, request_id: str | None = None,
          since: str | None = None, until: str | None = None, limit: int = 500):
    return state.audit_rows(user_id=user_id, role=role, area=area, patient_id=patient_id, request_id=request_id,
                            since=since, until=until, limit=limit)


@app.get("/api/audit/mine")
def my_audit(user: dict = Depends(auth.current_user)):
    return state.audit_rows(user_id=user["id"], limit=200)


# ------------------------------------------------------------------ primary use
@app.get("/api/patients")
def patients(search: str = "", user: dict = Depends(auth.require(HOSPITAL))):
    rows = summary.search(get_store(), search, user["data_holder"])
    state.audit(user, "primary", "patient_search", outcome=str(len(rows)), details={"search": search})
    return rows


def _own_patient(pid: str, user: dict) -> dict:
    p = summary.patient(get_store(), pid)
    if not p:
        raise HTTPException(404, "Patient not found")
    if user["role"] == HOSPITAL and p["data_holder"] != user["data_holder"]:
        state.audit(user, "primary", "patient_access_denied", patient_id=pid, outcome="no_treatment_relationship")
        raise HTTPException(403, "No treatment relationship: patient belongs to another hospital.")
    return p


@app.get("/api/patients/{pid}/summary")
def patient_summary(pid: str, lang: str = "de", user: dict = Depends(auth.require(HOSPITAL))):
    _own_patient(pid, user)
    out = summary.build(get_store(), pid, lang)
    state.audit(user, "primary", "patient_summary_viewed", patient_id=pid, outcome="ALLOW", details={"rule": 2, "lang": lang})
    return out


@app.get("/api/patients/{pid}/ips")
def patient_ips(pid: str, lang: str = "de", user: dict = Depends(auth.require(HOSPITAL))):
    return patient_summary(pid, lang, user)


class LetterIn(BaseModel):
    patient_id: str
    encounter_id: str | None = None


@app.post("/api/discharge-letters")
def create_letter(body: LetterIn, user: dict = Depends(auth.require(HOSPITAL))):
    _own_patient(body.patient_id, user)
    return letters.create(get_store(), body.patient_id, user, body.encounter_id)


@app.get("/api/discharge-letters")
def list_letters(patient_id: str, user: dict = Depends(auth.require(HOSPITAL))):
    _own_patient(patient_id, user)
    return state.query("SELECT id, version, status, encounter_id, signed_by, signed_at, created_at, updated_at, supersedes "
                       "FROM letters WHERE patient_id = ? ORDER BY version DESC", (patient_id,))


@app.get("/api/discharge-letters/{lid}")
def get_letter(lid: str, user: dict = Depends(auth.require(HOSPITAL))):
    row = letters.get(lid)
    _own_patient(row["patient_id"], user)
    state.audit(user, "primary", "letter_viewed", patient_id=row["patient_id"], outcome="ok", details={"letter_id": lid})
    return row


class SectionIn(BaseModel):
    text: str | None = None
    texts: list[str] | None = None
    items: list[dict] | None = None
    reason: str | None = None
    editor: str | None = None  # ignored: the editor is the signed-in user


@app.put("/api/discharge-letters/{lid}/sections/{key}")
def edit_section(lid: str, key: str, body: SectionIn, user: dict = Depends(auth.require(HOSPITAL))):
    _own_patient(letters.get(lid)["patient_id"], user)
    text = body.text if body.text is not None else ("\n".join(body.texts) if body.texts is not None else None)
    return letters.edit_section(lid, key, text, body.items, body.reason, user)


class SignIn(BaseModel):
    confirmed: bool
    key_id: str
    challenge: str
    assertion: dict | None = Field(None, description="WebAuthn assertion (PublicKeyCredential JSON) for a hardware key")
    signature: str | None = Field(None, description="base64url P-256 signature (r||s) over the challenge, simulated key")


@app.post("/api/discharge-letters/{lid}/sign/challenge")
def sign_challenge(lid: str, user: dict = Depends(auth.require_release)):
    letter = letters.get(lid)
    _own_patient(letter["patient_id"], user)
    if letter["status"] != "draft":
        raise HTTPException(409, f"Letter is already {letter['status']}")
    return signature.sign_challenge(user, lid)


@app.post("/api/discharge-letters/{lid}/sign")
def sign_letter(lid: str, body: SignIn, user: dict = Depends(auth.require_release)):
    _own_patient(letters.get(lid)["patient_id"], user)
    return letters.sign(lid, body.confirmed, user, lambda: signature.verify(
        user, lid, body.key_id, body.challenge, assertion=body.assertion, signature=body.signature))


@app.post("/api/discharge-letters/{lid}/correct")
def correct_letter(lid: str, user: dict = Depends(auth.require_release)):
    _own_patient(letters.get(lid)["patient_id"], user)
    return letters.correct(lid, user)


@app.post("/api/discharge-letters/{lid}/send")
def send_letter(lid: str, user: dict = Depends(auth.require_release)):
    _own_patient(letters.get(lid)["patient_id"], user)
    return letters.send(lid, user)


# patient portal
class ConsentIn(BaseModel):
    allow_cross_border: bool
    hidden_sections: list[str] = []


@app.get("/api/portal/me")
def portal_me(user: dict = Depends(auth.require(PATIENT))):
    pid = user["patient_id"]
    p = summary.patient(get_store(), pid)
    return {"patient_id": pid, "opted_out_of_secondary_use": p["opted_out"] if p else None,
            "consent": crossborder.get_consent(pid), "accesses": crossborder.accesses(pid),
            "approved_research": catalogue.register()}


@app.put("/api/portal/consent")
def portal_consent(body: ConsentIn, user: dict = Depends(auth.require(PATIENT))):
    return crossborder.set_consent(user["patient_id"], body.allow_cross_border, body.hidden_sections, user)


@app.get("/api/portal/accesses")
def portal_accesses(user: dict = Depends(auth.require(PATIENT))):
    return crossborder.accesses(user["patient_id"])


# cross-border (simulated foreign hospital system)
class CrossBorderIn(BaseModel):
    patient_id: str
    document_type: str | None = None   # passport | id_card | id_austria_code
    document_number: str | None = None
    name: str | None = None
    birth_date: str | None = None
    identity_checked: bool = False
    patient_agrees: bool = False
    emergency: bool = False
    reason: str | None = None
    lang: str = "it"


@app.post("/api/cross-border/check")
def cross_border_check(body: CrossBorderIn, user: dict = Depends(auth.require(FOREIGN_DOCTOR, HOSPITAL))):
    """Access decision (rules 1–5) without releasing any data."""
    return crossborder.check_access(get_store(), user, body.patient_id, identity_checked=body.identity_checked,
                                    patient_agrees=body.patient_agrees, emergency=body.emergency, reason=body.reason)


@app.post("/api/cross-border/patient-summary")
def cross_border(body: CrossBorderIn, user: dict = Depends(auth.require(FOREIGN_DOCTOR, HOSPITAL))):
    return crossborder.request_summary(get_store(), user, body.patient_id,
                                       identity={"document_type": body.document_type},
                                       identity_checked=body.identity_checked, patient_agrees=body.patient_agrees,
                                       emergency=body.emergency, reason=body.reason, lang=body.lang)


# ------------------------------------------------------------------ security keys (digital signature)
@app.get("/api/security-keys")
def my_keys(user: dict = Depends(auth.require(HOSPITAL))):
    return signature.keys(user["id"])


class KeyOptionsIn(BaseModel):
    recovery_code: str | None = None


@app.post("/api/security-keys/register/options")
def key_options(body: KeyOptionsIn, user: dict = Depends(auth.require(HOSPITAL))):
    return signature.registration_options(user, body.recovery_code)


class KeyIn(BaseModel):
    kind: str = Field(examples=["webauthn", "software"])
    label: str | None = None
    challenge: str
    credential: dict | None = None
    public_key: str | None = Field(None, description="software key: base64url SPKI (DER) P-256 public key")
    signature: str | None = Field(None, description="software key: signature over the challenge (proof of possession)")
    recovery_code: str | None = None


@app.post("/api/security-keys")
def add_key(body: KeyIn, user: dict = Depends(auth.require(HOSPITAL))):
    return signature.register(user, body.kind, body.label, body.challenge, credential=body.credential,
                              public_key=body.public_key, signature=body.signature, recovery_code=body.recovery_code)


@app.post("/api/security-keys/{kid}/lost")
def key_lost(kid: str, user: dict = Depends(auth.require(HOSPITAL))):
    return signature.report_lost(user, kid)


# ------------------------------------------------------------------ hospital staff & permissions
def _staff_row(u: dict) -> dict:
    return {**auth.public(u), "keys": signature.keys(u["id"]) if u["role"] == HOSPITAL else []}


def _colleague(uid: str, user: dict) -> dict:
    target = state.one("SELECT * FROM users WHERE id = ? AND role IN (?, ?)", (uid, HOSPITAL, HOSPITAL_IT))
    if not target or target["organisation"] != user["organisation"]:
        raise HTTPException(404, "No such staff member in your hospital")
    return target


@app.get("/api/hospital/staff")
def hospital_staff(user: dict = Depends(auth.require(HOSPITAL_IT, HOSPITAL))):
    """IT admins see everyone in their hospital; senior doctors see their colleagues to grant permissions."""
    if user["role"] == HOSPITAL and user.get("hospital_role") != auth.SENIOR:
        raise HTTPException(403, "Only senior doctors and IT admins can see the staff list.")
    rows = state.query("SELECT * FROM users WHERE role IN (?, ?) AND organisation = ? ORDER BY status DESC, name",
                       (HOSPITAL, HOSPITAL_IT, user["organisation"]))
    if user["role"] == HOSPITAL:
        rows = [r for r in rows if r["role"] == HOSPITAL and r["status"] == "active"]
    return [_staff_row(r) for r in rows]


@app.post("/api/admin/users/{uid}/activate")
def activate_user(uid: str, user: dict = Depends(auth.require(HOSPITAL_IT))):
    target = _colleague(uid, user)
    with state.tx() as c:
        c.execute("UPDATE users SET status='active' WHERE id=?", (uid,))
        state.audit(user, "admin", "account_activated", outcome="active", details={"user": uid}, conn=c)
    return _staff_row({**target, "status": "active"})


class RoleIn(BaseModel):
    hospital_role: str = Field(examples=["doctor"])


@app.put("/api/admin/users/{uid}/role")
def set_role(uid: str, body: RoleIn, user: dict = Depends(auth.require(HOSPITAL_IT))):
    if body.hospital_role not in auth.HOSPITAL_ROLES:
        raise HTTPException(422, "Unknown hospital role")
    if uid == user["id"]:
        raise HTTPException(409, "You cannot change your own role.")
    target = _colleague(uid, user)
    system_role = HOSPITAL_IT if body.hospital_role == auth.IT_ADMIN else HOSPITAL
    with state.tx() as c:
        c.execute("UPDATE users SET role=?, hospital_role=? WHERE id=?", (system_role, body.hospital_role, uid))
        if body.hospital_role != auth.DOCTOR:
            c.execute("DELETE FROM permissions WHERE user_id=? AND permission=?", (uid, auth.RELEASE_LETTERS))
        state.audit(user, "admin", "role_changed", outcome=body.hospital_role,
                    details={"user": uid, "from": target.get("hospital_role")}, conn=c)
    return _staff_row(state.one("SELECT * FROM users WHERE id = ?", (uid,)))


@app.post("/api/hospital/staff/{uid}/release-permission")
def grant_release(uid: str, user: dict = Depends(auth.require_senior)):
    target = _colleague(uid, user)
    if target["role"] != HOSPITAL or target.get("hospital_role") != auth.DOCTOR or target["status"] != "active":
        raise HTTPException(409, "Release permission can only be granted to active doctors.")
    with state.tx() as c:
        c.execute("INSERT OR REPLACE INTO permissions (user_id,permission,granted_by,granted_by_name,granted_at) "
                  "VALUES (?,?,?,?,?)", (uid, auth.RELEASE_LETTERS, user["id"], user["name"], state.now()))
        state.audit(user, "admin", "release_permission_granted", outcome="granted", details={"user": uid}, conn=c)
    return _staff_row(target)


@app.delete("/api/hospital/staff/{uid}/release-permission")
def revoke_release(uid: str, user: dict = Depends(auth.require(HOSPITAL_IT, HOSPITAL))):
    if user["role"] == HOSPITAL and user.get("hospital_role") != auth.SENIOR:
        raise HTTPException(403, "Only senior doctors and IT admins can revoke release permissions.")
    target = _colleague(uid, user)
    with state.tx() as c:
        c.execute("DELETE FROM permissions WHERE user_id=? AND permission=?", (uid, auth.RELEASE_LETTERS))
        state.audit(user, "admin", "release_permission_revoked", outcome="revoked", details={"user": uid}, conn=c)
    return _staff_row(target)


@app.get("/api/hospital/staff/{uid}/permission-history")
def permission_history(uid: str, user: dict = Depends(auth.require(HOSPITAL_IT))):
    _colleague(uid, user)
    rows = state.audit_rows(area="admin", limit=500) + state.audit_rows(area="auth", limit=500)
    return sorted([r for r in rows if r["details"].get("user") == uid or r["details"].get("for_user") == uid
                   or r["details"].get("owner") == uid], key=lambda r: r["id"], reverse=True)


@app.post("/api/admin/users/{uid}/keys/{kid}/lost")
def admin_key_lost(uid: str, kid: str, user: dict = Depends(auth.require(HOSPITAL_IT))):
    _colleague(uid, user)
    return signature.report_lost(user, kid, owner_id=uid)


class RecoveryIn(BaseModel):
    identity_checked: bool = Field(description="IT admin confirms the doctor's photo ID was checked in person")


@app.post("/api/admin/users/{uid}/recovery-code")
def recovery_code(uid: str, body: RecoveryIn, user: dict = Depends(auth.require(HOSPITAL_IT))):
    target = _colleague(uid, user)
    if not body.identity_checked:
        raise HTTPException(422, "Check the doctor's photo ID in person before issuing a recovery code.")
    if target["role"] != HOSPITAL:
        raise HTTPException(409, "Only doctors sign with a security key.")
    return signature.issue_recovery_code(user, uid)

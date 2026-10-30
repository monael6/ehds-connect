"""Authentication, registration and role-based authorisation.

Real deployment: hospital SSO, ID Austria for citizens and authority accounts,
NCPeH trust for foreign doctors. Here: email + password (or preset demo accounts)
and a bearer token, but every endpoint checks the role server-side.

Hospital staff have one of three hospital roles. Only senior doctors, and
doctors a senior doctor has authorised, may sign discharge letters and
release them to ELGA / the GP. IT admins manage accounts and see no patient data.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import state

HOSPITAL = "hospital"
HOSPITAL_IT = "hospital_it"
HDAB = "hdab_staff"
INTERESTED = "interested_party"
PATIENT = "patient"
FOREIGN_DOCTOR = "foreign_doctor"

SENIOR = "senior_doctor"
DOCTOR = "doctor"
IT_ADMIN = "it_admin"
HOSPITAL_ROLES = {SENIOR: "Senior Doctor", DOCTOR: "Doctor", IT_ADMIN: "IT Admin"}

RELEASE_LETTERS = "release_letters"

ROLE_AREAS = {
    HOSPITAL: {"primary", "provision", "catalogue"},
    HOSPITAL_IT: {"admin"},
    HDAB: {"secondary", "audit", "catalogue"},
    INTERESTED: {"public", "catalogue", "apply"},
    PATIENT: {"portal"},
    FOREIGN_DOCTOR: {"cross_border"},
}

DEMO_PASSWORD = "demo1234"

DEMO_USERS = [
    {"id": "u-huber", "name": "Dr. Anna Huber", "role": HOSPITAL, "hospital_role": SENIOR,
     "email": "anna.huber@klinikum-west.at", "organisation": "Klinikum West", "data_holder": None,
     "sign_in_method": "Hospital account + security key"},
    {"id": "u-berger", "name": "Dr. Markus Berger", "role": HOSPITAL, "hospital_role": DOCTOR,
     "email": "markus.berger@klinikum-west.at", "organisation": "Klinikum West", "data_holder": None,
     "sign_in_method": "Hospital account + security key"},
    {"id": "u-gruber", "name": "Thomas Gruber", "role": HOSPITAL_IT, "hospital_role": IT_ADMIN,
     "email": "thomas.gruber@klinikum-west.at", "organisation": "Klinikum West", "data_holder": None,
     "sign_in_method": "Hospital account"},
    {"id": "u-novak", "name": "Mag. Petra Novak", "role": HDAB,
     "email": "petra.novak@hdab.gv.at", "organisation": "Health Data Access Body Austria", "data_holder": None,
     "sign_in_method": "ID Austria / authority account"},
    {"id": "u-weiss", "name": "Dr. Lena Weiss", "role": INTERESTED,
     "email": "lena.weiss@uni-graz.at", "organisation": "University of Graz", "data_holder": None,
     "sign_in_method": "ID Austria"},
    {"id": "u-public", "name": "Public visitor", "role": INTERESTED,
     "organisation": "-", "data_holder": None, "sign_in_method": "browse without account"},
    {"id": "u-muster", "name": "Frau M. (patient)", "role": PATIENT, "organisation": "-", "data_holder": None,
     "sign_in_method": "ID Austria", "patient_id": "p-4cfd3cf1"},
    {"id": "u-rossi", "name": "Dr. Giulia Rossi", "role": FOREIGN_DOCTOR,
     "organisation": "Ospedale di Firenze (IT)", "data_holder": None,
     "sign_in_method": "Italian hospital system, vouched by NCPeH Italy"},
]

PUBLIC_FIELDS = ("id", "name", "email", "role", "hospital_role", "organisation", "data_holder",
                 "sign_in_method", "patient_id", "status")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000).hex()
    return f"pbkdf2_sha256$120000${salt}${digest}"


def check_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, rounds, salt, digest = stored.split("$")
    except ValueError:
        return False
    got = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
    return hmac.compare_digest(got, digest)


def seed_users(hospital_data_holder: str | None = None) -> None:
    """Insert demo users. Hospital accounts are tied to one data holder from the data."""
    demo_hash = hash_password(DEMO_PASSWORD)
    with state.tx() as c:
        for u in DEMO_USERS:
            dh = hospital_data_holder if u["role"] in (HOSPITAL, HOSPITAL_IT) else u["data_holder"]
            org = hospital_data_holder if u["role"] in (HOSPITAL, HOSPITAL_IT) and hospital_data_holder else u["organisation"]
            c.execute("INSERT INTO users (id,name,role,organisation,data_holder,sign_in_method,patient_id,email,"
                      "password_hash,hospital_role,status) VALUES (?,?,?,?,?,?,?,?,?,?,'active') "
                      "ON CONFLICT(id) DO UPDATE SET data_holder=excluded.data_holder, organisation=excluded.organisation, "
                      "email=COALESCE(users.email, excluded.email), "
                      "password_hash=COALESCE(users.password_hash, excluded.password_hash), "
                      "hospital_role=COALESCE(users.hospital_role, excluded.hospital_role)",
                      (u["id"], u["name"], u["role"], org, dh, u["sign_in_method"], u.get("patient_id"),
                       u.get("email"), demo_hash if u.get("email") else None, u.get("hospital_role")))


def permissions(user: dict) -> list[str]:
    rows = state.query("SELECT permission FROM permissions WHERE user_id = ?", (user["id"],))
    granted = {r["permission"] for r in rows}
    if user.get("role") == HOSPITAL and user.get("hospital_role") == SENIOR:
        granted.add(RELEASE_LETTERS)
    if user.get("role") != HOSPITAL:
        granted.discard(RELEASE_LETTERS)
    return sorted(granted)


def can_release(user: dict) -> bool:
    return RELEASE_LETTERS in permissions(user)


def public(user: dict) -> dict:
    out = {k: user.get(k) for k in PUBLIC_FIELDS}
    out["hospital_role_label"] = HOSPITAL_ROLES.get(user.get("hospital_role") or "")
    out["permissions"] = permissions(user)
    return out


def _session(user: dict, method: str) -> dict:
    if user.get("status") != "active":
        raise HTTPException(403, "Your account is waiting for activation by your hospital IT admin.")
    token = secrets.token_urlsafe(24)
    with state.tx() as c:
        c.execute("INSERT INTO sessions (token,user_id,created_at) VALUES (?,?,?)", (token, user["id"], state.now()))
        state.audit(user, "auth", "sign_in", outcome="ok", details={"method": method}, conn=c)
    return {"token": token, "user": public(user), "areas": sorted(ROLE_AREAS[user["role"]])}


def login(user_id: str) -> dict:
    """Demo shortcut: sign in to a preset account without a password."""
    user = state.one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        raise HTTPException(404, "Unknown demo account")
    return _session(user, user["sign_in_method"] or "demo account")


def login_password(email: str, password: str) -> dict:
    user = state.one("SELECT * FROM users WHERE lower(email) = lower(?)", (email.strip(),))
    if not user or not check_password(password, user.get("password_hash")):
        state.audit(None, "auth", "sign_in_failed", outcome="bad_credentials", details={"email": email.strip().lower()})
        raise HTTPException(401, "Email or password is wrong.")
    return _session(user, "email + password")


# category -> allowed roles -> (system role, hospital role, needs IT admin activation)
REGISTRATION = {
    "healthcare": {SENIOR: (HOSPITAL, SENIOR, True), DOCTOR: (HOSPITAL, DOCTOR, True),
                   IT_ADMIN: (HOSPITAL_IT, IT_ADMIN, True)},
    "institute": {"hdab_staff": (HDAB, None, False)},
    "applicant": {"applicant": (INTERESTED, None, False)},
}


def register(name: str, email: str, password: str, category: str, role: str, organisation: str,
             hospital: str | None) -> dict:
    roles = REGISTRATION.get(category)
    if not roles or role not in roles:
        raise HTTPException(422, "Choose a category and a role that belongs to it.")
    if len(password) < 8:
        raise HTTPException(422, "The password needs at least 8 characters.")
    if "@" not in email:
        raise HTTPException(422, "Enter a valid email address.")
    if state.one("SELECT id FROM users WHERE lower(email) = lower(?)", (email.strip(),)):
        raise HTTPException(409, "An account with this email already exists.")
    system_role, hospital_role, needs_activation = roles[role]
    is_hospital = category == "healthcare"
    user = {"id": f"u-{secrets.token_hex(4)}", "name": name.strip(), "role": system_role,
            "hospital_role": hospital_role, "email": email.strip().lower(),
            "organisation": (hospital or organisation) if is_hospital else organisation.strip(),
            "data_holder": hospital if is_hospital else None,
            "sign_in_method": "Hospital account + security key" if is_hospital else "email + password",
            "status": "pending" if needs_activation else "active"}
    if not user["name"] or not user["organisation"]:
        raise HTTPException(422, "Name and organisation are required.")
    with state.tx() as c:
        c.execute("INSERT INTO users (id,name,role,organisation,data_holder,sign_in_method,email,password_hash,"
                  "hospital_role,status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (user["id"], user["name"], user["role"], user["organisation"], user["data_holder"],
                   user["sign_in_method"], user["email"], hash_password(password), hospital_role, user["status"]))
        state.audit(user, "auth", "registered", outcome=user["status"], details={"category": category, "role": role}, conn=c)
    if needs_activation:
        return {"status": "pending", "user": public(user),
                "message": "Account created. Your hospital IT admin must activate it before you can sign in."}
    return {"status": "active", **_session(user, "registration")}


def logout(token: str) -> None:
    with state.tx() as c:
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))


# A security scheme (not a plain header parameter) so the "Authorize" button in /docs works
bearer = HTTPBearer(auto_error=False, description="Token from POST /api/auth/login")


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(401, "Sign in first")
    token = creds.credentials.strip()
    row = state.one("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?", (token,))
    if not row or row.get("status") != "active":
        raise HTTPException(401, "Session expired, sign in again")
    row.pop("password_hash", None)
    row["token"] = token
    return row


def optional_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict | None:
    try:
        return current_user(creds)
    except HTTPException:
        return None


def require(*roles: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            state.audit(user, "auth", "access_denied", outcome="denied", details={"needed": list(roles)})
            raise HTTPException(403, f"You don't have access to this area with the role {user['role']}.")
        return user
    return dep


def require_release(user: dict = Depends(require(HOSPITAL))) -> dict:
    """Signing and releasing letters (ELGA, GP): senior doctors or doctors they authorised."""
    if not can_release(user):
        state.audit(user, "primary", "release_denied", outcome="no_release_permission")
        raise HTTPException(403, "Only a senior doctor, or a doctor a senior doctor has authorised, "
                                 "may sign and release discharge letters.")
    return user


def require_senior(user: dict = Depends(require(HOSPITAL))) -> dict:
    if user.get("hospital_role") != SENIOR:
        raise HTTPException(403, "Only senior doctors can grant release permissions.")
    return user

"""Demo authentication and role-based authorisation.

Real deployment: hospital SSO + second factor, ID Austria for citizens and
authority accounts, NCPeH trust for foreign doctors. Here: preset demo accounts
and a bearer token, but every endpoint checks the role server-side.
"""
from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException

from . import state

HOSPITAL = "hospital"
HDAB = "hdab_staff"
INTERESTED = "interested_party"
PATIENT = "patient"
FOREIGN_DOCTOR = "foreign_doctor"

ROLE_AREAS = {
    HOSPITAL: {"primary", "provision", "catalogue"},
    HDAB: {"secondary", "audit", "catalogue"},
    INTERESTED: {"public", "catalogue", "apply"},
    PATIENT: {"portal"},
    FOREIGN_DOCTOR: {"cross_border"},
}

DEMO_USERS = [
    {"id": "u-huber", "name": "Dr. Anna Huber", "role": HOSPITAL,
     "organisation": "Klinikum West", "data_holder": None,
     "sign_in_method": "Hospital single sign-on + second factor"},
    {"id": "u-novak", "name": "Mag. Petra Novak", "role": HDAB,
     "organisation": "Health Data Access Body Austria", "data_holder": None,
     "sign_in_method": "ID Austria / authority account"},
    {"id": "u-weiss", "name": "Dr. Lena Weiss", "role": INTERESTED,
     "organisation": "University of Graz", "data_holder": None, "sign_in_method": "ID Austria"},
    {"id": "u-public", "name": "Public visitor", "role": INTERESTED,
     "organisation": "-", "data_holder": None, "sign_in_method": "browse without account"},
    {"id": "u-muster", "name": "Frau M. (patient)", "role": PATIENT, "organisation": "-", "data_holder": None,
     "sign_in_method": "ID Austria", "patient_id": "p-4cfd3cf1"},
    {"id": "u-rossi", "name": "Dr. Giulia Rossi", "role": FOREIGN_DOCTOR,
     "organisation": "Ospedale di Firenze (IT)", "data_holder": None,
     "sign_in_method": "Italian hospital system, vouched by NCPeH Italy"},
]


def seed_users(hospital_data_holder: str | None = None) -> None:
    """Insert demo users. The hospital account is tied to one data holder from the data."""
    with state.tx() as c:
        for u in DEMO_USERS:
            dh = hospital_data_holder if u["role"] == HOSPITAL else u["data_holder"]
            c.execute("INSERT INTO users (id,name,role,organisation,data_holder,sign_in_method,patient_id) VALUES (?,?,?,?,?,?,?) "
                      "ON CONFLICT(id) DO UPDATE SET data_holder=excluded.data_holder, organisation=excluded.organisation",
                      (u["id"], u["name"], u["role"], u["organisation"], dh, u["sign_in_method"], u.get("patient_id")))


def login(user_id: str) -> dict:
    user = state.one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        raise HTTPException(404, "Unknown demo account")
    token = secrets.token_urlsafe(24)
    with state.tx() as c:
        c.execute("INSERT INTO sessions (token,user_id,created_at) VALUES (?,?,?)", (token, user_id, state.now()))
        state.audit(user, "auth", "sign_in", outcome="ok", details={"method": user["sign_in_method"]}, conn=c)
    return {"token": token, "user": user, "areas": sorted(ROLE_AREAS[user["role"]])}


def logout(token: str) -> None:
    with state.tx() as c:
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in first")
    token = authorization.split(" ", 1)[1].strip()
    row = state.one("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?", (token,))
    if not row:
        raise HTTPException(401, "Session expired, sign in again")
    row["token"] = token
    return row


def optional_user(authorization: str | None = Header(default=None)) -> dict | None:
    try:
        return current_user(authorization)
    except HTTPException:
        return None


def require(*roles: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            state.audit(user, "auth", "access_denied", outcome="denied", details={"needed": list(roles)})
            raise HTTPException(403, f"You don't have access to this area with the role {user['role']}.")
        return user
    return dep

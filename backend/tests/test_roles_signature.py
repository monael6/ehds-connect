"""Hospital roles, release permission, security-key signing and recovery, registration, HDAB review."""
import pytest
from fastapi.testclient import TestClient

from app import datastore
from tests.test_api import enrol_key, login, sign_body


@pytest.fixture()
def client(store):
    datastore.set_store(store)
    from app.main import app
    with TestClient(app) as c:
        yield c


def _ready_letter(c, h):
    lid = c.post("/api/discharge-letters", json={"patient_id": "p-4cfd3cf1"}, headers=h).json()["id"]
    c.put(f"/api/discharge-letters/{lid}/sections/empfehlungen", json={"text": "Kontrolle in 6 Wochen."}, headers=h)
    return lid


def test_doctor_needs_permission_from_senior_doctor(client):
    doc, senior, it = login(client, "u-berger"), login(client, "u-huber"), login(client, "u-gruber")
    me = client.get("/api/me", headers=doc).json()["user"]
    assert me["hospital_role_label"] == "Doctor" and me["permissions"] == [] and "password_hash" not in me
    lid = _ready_letter(client, doc)  # doctors may draft and edit
    assert client.post(f"/api/discharge-letters/{lid}/sign/challenge", headers=doc).status_code == 403
    assert client.post(f"/api/discharge-letters/{lid}/send", headers=doc).status_code == 403
    # IT admin cannot grant, and sees no patients
    assert client.post("/api/hospital/staff/u-berger/release-permission", headers=it).status_code == 403
    assert client.get("/api/patients", headers=it).status_code == 403
    # doctors cannot grant themselves
    assert client.post("/api/hospital/staff/u-berger/release-permission", headers=doc).status_code == 403
    granted = client.post("/api/hospital/staff/u-berger/release-permission", headers=senior).json()
    assert granted["permissions"] == ["release_letters"]
    staff = {s["id"]: s for s in client.get("/api/hospital/staff", headers=it).json()}
    assert staff["u-berger"]["permissions"] == ["release_letters"] and "u-gruber" in staff
    priv, key = enrol_key(client, doc)
    signed = client.post(f"/api/discharge-letters/{lid}/sign", json=sign_body(client, doc, lid, priv, key.json()["id"]),
                         headers=doc)
    assert signed.status_code == 200 and signed.json()["signed_by"] == "Dr. Markus Berger"
    assert client.post(f"/api/discharge-letters/{lid}/send", headers=doc).status_code == 200
    # IT admin revokes; release blocked again
    assert client.delete("/api/hospital/staff/u-berger/release-permission", headers=it).json()["permissions"] == []
    assert client.post(f"/api/discharge-letters/{lid}/send", headers=doc).status_code == 403
    history = client.get("/api/hospital/staff/u-berger/permission-history", headers=it).json()
    assert {"release_permission_granted", "release_permission_revoked"} <= {h["action"] for h in history}


def test_it_admin_changes_roles(client):
    it, doc = login(client, "u-gruber"), login(client, "u-berger")
    assert client.put("/api/admin/users/u-berger/role", json={"hospital_role": "senior_doctor"}, headers=doc).status_code == 403
    assert client.put("/api/admin/users/u-gruber/role", json={"hospital_role": "doctor"}, headers=it).status_code == 409
    up = client.put("/api/admin/users/u-berger/role", json={"hospital_role": "senior_doctor"}, headers=it).json()
    assert up["hospital_role"] == "senior_doctor" and up["permissions"] == ["release_letters"]


def test_lost_key_backup_and_recovery(client):
    h, it = login(client, "u-huber"), login(client, "u-gruber")
    assert client.post("/api/discharge-letters/x/sign/challenge", headers=h).status_code == 404
    lid = _ready_letter(client, h)
    r = client.post(f"/api/discharge-letters/{lid}/sign/challenge", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["needs_key"]
    priv1, k1 = enrol_key(client, h)
    priv2, k2 = enrol_key(client, h)  # backup key, allowed while the first one is active
    client.post(f"/api/security-keys/{k1.json()['id']}/lost", headers=h)
    # the lost key no longer signs, the backup does
    assert client.post(f"/api/discharge-letters/{lid}/sign", json=sign_body(client, h, lid, priv1, k1.json()["id"]),
                       headers=h).status_code == 401
    client.post(f"/api/admin/users/u-huber/keys/{k2.json()['id']}/lost", headers=it)
    # all keys lost: a new key needs a recovery code from IT after an identity check
    _, denied = enrol_key(client, h)
    assert denied.status_code == 403 and denied.json()["detail"]["needs_recovery_code"]
    assert client.post("/api/admin/users/u-huber/recovery-code", json={"identity_checked": False}, headers=it).status_code == 422
    code = client.post("/api/admin/users/u-huber/recovery-code", json={"identity_checked": True}, headers=it).json()["code"]
    priv3, k3 = enrol_key(client, h, recovery_code=code)
    assert k3.status_code == 200
    assert client.post(f"/api/discharge-letters/{lid}/sign", json=sign_body(client, h, lid, priv3, k3.json()["id"]),
                       headers=h).json()["status"] == "signed"
    client.post(f"/api/security-keys/{k3.json()['id']}/lost", headers=h)
    _, reused = enrol_key(client, h, recovery_code=code)  # one-time code
    assert reused.status_code == 403


def test_registration_and_password_login(client):
    opts = {o["category"]: o for o in client.get("/api/auth/registration-options").json()}
    assert [r["label"] for r in opts["healthcare"]["roles"]] == ["Senior Doctor", "Doctor", "IT Admin"]
    app_ = client.post("/api/auth/register", json={"name": "Dr. Max Roth", "email": "max@uni-wien.at", "password": "secret123",
                                                   "category": "applicant", "role": "applicant", "organisation": "Uni Wien"})
    assert app_.json()["status"] == "active" and app_.json()["token"]
    assert client.post("/api/auth/register", json={"name": "X", "email": "MAX@uni-wien.at", "password": "secret123",
                                                   "category": "applicant", "role": "applicant", "organisation": "Y"}).status_code == 409
    assert client.post("/api/auth/register", json={"name": "X", "email": "x@y.at", "password": "secret123",
                                                   "category": "applicant", "role": "senior_doctor", "organisation": "Y"}).status_code == 422
    doc = client.post("/api/auth/register", json={"name": "Dr. Eva Lang", "email": "eva@klinik.at", "password": "secret123",
                                                  "category": "healthcare", "role": "doctor"}).json()
    assert doc["status"] == "pending"
    assert client.post("/api/auth/login", json={"email": "eva@klinik.at", "password": "secret123"}).status_code == 403
    it = login(client, "u-gruber")
    client.post(f"/api/admin/users/{doc['user']['id']}/activate", headers=it)
    ok = client.post("/api/auth/login", json={"email": "eva@klinik.at", "password": "secret123"})
    assert ok.status_code == 200 and ok.json()["user"]["hospital_role"] == "doctor"
    assert client.post("/api/auth/login", json={"email": "eva@klinik.at", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "anna.huber@klinikum-west.at", "password": "demo1234"}).status_code == 200


def test_applicant_results_wait_for_hdab_approval(client):
    hdab, weiss = login(client, "u-novak"), login(client, "u-weiss")
    own = client.post("/api/requests/evaluate", json={"id": "R01"}, headers=weiss).json()
    assert own["status"] == "submitted" and not own["results_released"] and "answer" not in own
    inbox = client.get("/api/requests", headers=hdab).json()
    assert inbox[0]["request_id"] == "R01" and inbox[0]["status"] == "submitted"
    assert client.post("/api/requests/R01/reject", json={"note": ""}, headers=hdab).status_code == 422
    client.post("/api/requests/R01/confirm", json={"note": "Approved"}, headers=hdab)
    got = client.get("/api/requests/R01", headers=weiss).json()
    assert got["status"] == "confirmed" and got["results_released"] and got["answer"]
    client.post("/api/requests/evaluate", json={"id": "R03"}, headers=weiss)
    client.post("/api/requests/R03/reject", json={"note": "Not in the public interest"}, headers=hdab)
    got = client.get("/api/requests/R03", headers=weiss).json()
    assert got["status"] == "rejected" and got["staff_note"] == "Not in the public interest" and "answer" not in got

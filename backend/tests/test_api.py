"""API: roles, SPE download block, discharge letter workflow, cross-border rules, audit."""
import base64

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from app import datastore


@pytest.fixture()
def client(store):
    datastore.set_store(store)
    from app.main import app
    with TestClient(app) as c:
        yield c


def login(c, uid):
    return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"user_id": uid}).json()["token"]}


def enrol_key(c, h, recovery_code=None):
    """Register a simulated P-256 security key, like the browser does with WebCrypto."""
    priv = ec.generate_private_key(ec.SECP256R1())
    spki = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    opts = c.post("/api/security-keys/register/options", json={"recovery_code": recovery_code}, headers=h)
    if opts.status_code != 200:
        return None, opts
    ch = opts.json()["challenge"]
    r = c.post("/api/security-keys", headers=h, json={"kind": "software", "label": "Demo key", "challenge": ch,
                                                       "public_key": b64(spki), "signature": raw_sign(priv, ch),
                                                       "recovery_code": recovery_code})
    return priv, r


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def raw_sign(priv, challenge: str) -> str:
    r, s = decode_dss_signature(priv.sign(challenge.encode(), ec.ECDSA(hashes.SHA256())))
    return b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def sign_body(c, h, lid, priv, kid, tamper=False):
    ch = c.post(f"/api/discharge-letters/{lid}/sign/challenge", headers=h).json()["challenge"]
    sig = raw_sign(priv, ch + ("x" if tamper else ""))
    return {"confirmed": True, "key_id": kid, "challenge": ch, "signature": sig}


def test_roles_are_enforced(client):
    hosp, hdab, weiss = login(client, "u-huber"), login(client, "u-novak"), login(client, "u-weiss")
    assert client.get("/api/requests", headers=hosp).status_code == 403
    assert client.get("/api/patients", headers=hdab).status_code == 403
    assert client.get("/api/audit", headers=weiss).status_code == 403
    assert client.get("/api/patients", headers=weiss).status_code == 403
    assert client.get("/api/requests").status_code == 401


def test_applicant_sees_only_own_requests_and_no_sql(client):
    hdab, weiss = login(client, "u-novak"), login(client, "u-weiss")
    staff = client.post("/api/requests/evaluate", json={"id": "R01"}, headers=hdab).json()
    assert "staff" in staff and staff["permit_checklist"]
    own = client.post("/api/requests/evaluate", json={"id": "R03"}, headers=weiss).json()
    assert "staff" not in own and "permit_checklist" not in own
    assert client.get("/api/requests/R01", headers=weiss).status_code == 403
    assert [r["request_id"] for r in client.get("/api/requests", headers=weiss).json()] == ["R03"]


def test_spe_download_always_blocked_and_logged(client):
    hdab = login(client, "u-novak")
    res = client.post("/api/requests/evaluate", json={"id": "R05"}, headers=hdab).json()
    assert res["decision"] == "APPROVE_SPE" and res["spe"]["patient_count"] == 1152
    r = client.get("/api/spe/R05/download", headers=hdab)
    assert r.status_code == 403 and r.json()["detail"]["blocked"]
    audit = client.get("/api/audit?request_id=R05", headers=hdab).json()
    assert any(a["action"] == "spe_download_attempt" and a["outcome"] == "blocked" for a in audit)


def test_reject_has_no_answer(client):
    res = client.post("/api/requests/evaluate", json={"id": "R02"}).json()
    assert res["decision"] == "REJECT" and res["answer"] is None and res["explanation"]["de"]


def test_discharge_letter_workflow(client):
    h = login(client, "u-huber")
    priv, key = enrol_key(client, h)
    kid = key.json()["id"]
    letter = client.post("/api/discharge-letters", json={"patient_id": "p-4cfd3cf1"}, headers=h).json()
    lid = letter["id"]
    assert "Weitere empfohlene Maßnahmen" in letter["missing_required"]
    assert client.post(f"/api/discharge-letters/{lid}/send", headers=h).status_code == 409
    assert client.post(f"/api/discharge-letters/{lid}/sign", json=sign_body(client, h, lid, priv, kid),
                       headers=h).status_code == 422
    client.put(f"/api/discharge-letters/{lid}/sections/empfehlungen",
               json={"text": "Kardiologische Kontrolle in 6 Wochen.", "reason": "ergänzt"}, headers=h)
    letter = client.get(f"/api/discharge-letters/{lid}", headers=h).json()
    assert letter["missing_required"] == [] and letter["edit_history"][0]["reason"] == "ergänzt"
    assert client.post(f"/api/discharge-letters/{lid}/sign", json=sign_body(client, h, lid, priv, kid, tamper=True),
                       headers=h).status_code == 401
    body = sign_body(client, h, lid, priv, kid)
    signed = client.post(f"/api/discharge-letters/{lid}/sign", json=body, headers=h).json()
    assert signed["status"] == "signed" and signed["signed_by"] == "Dr. Anna Huber"
    assert signed["signature"]["method"].startswith("simulated security key")
    # a challenge works once only
    assert client.post(f"/api/discharge-letters/{lid}/sign", json=body, headers=h).status_code == 409
    assert client.put(f"/api/discharge-letters/{lid}/sections/brieftext", json={"text": "x"}, headers=h).status_code == 409
    assert client.post(f"/api/discharge-letters/{lid}/send", headers=h).status_code == 200
    v2 = client.post(f"/api/discharge-letters/{lid}/correct", headers=h).json()
    assert v2["version"] == 2 and v2["supersedes"] == lid
    assert client.get(f"/api/discharge-letters/{lid}", headers=h).json()["status"] == "superseded"


def test_letter_never_invents_missing_data(client):
    h = login(client, "u-huber")
    letter = client.post("/api/discharge-letters", json={"patient_id": "p-4cfd3cf1"}, headers=h).json()
    allergies = next(s for s in letter["content"]["sections"] if s["key"] == "allergien")
    assert allergies["empty"] and "No data in the KIS" in allergies["text"]
    for s in letter["content"]["sections"]:
        for item in s["items"]:
            assert item.get("source"), f"statement without source in {s['key']}"


def test_cross_border_rules(client):
    rossi, patient = login(client, "u-rossi"), login(client, "u-muster")
    body = {"patient_id": "p-4cfd3cf1", "identity_checked": True, "patient_agrees": True, "lang": "it"}
    assert client.post("/api/cross-border/patient-summary", json=body, headers=rossi).json()["decision"] == "DENY"
    client.put("/api/portal/consent", json={"allow_cross_border": True, "hidden_sections": ["results"]}, headers=patient)
    ok = client.post("/api/cross-border/patient-summary", json=body, headers=rossi).json()
    assert ok["decision"] == "ALLOW_CROSS_BORDER" and "results" not in ok["summary"]
    assert ok["summary"]["problems"][0]["label"] == "Fibrillazione atriale cronica"
    no_id = client.post("/api/cross-border/patient-summary", json={**body, "identity_checked": False}, headers=rossi).json()
    assert no_id["decision"] == "DENY"
    em = client.post("/api/cross-border/patient-summary",
                     json={"patient_id": "p-4cfd3cf1", "emergency": True, "reason": "unconscious"}, headers=rossi).json()
    assert em["decision"] == "ALLOW_EMERGENCY" and "problems" not in em["summary"] and em["summary"]["emergency"]
    accesses = client.get("/api/portal/accesses", headers=patient).json()
    assert {a["outcome"] for a in accesses} >= {"ALLOW_CROSS_BORDER", "ALLOW_EMERGENCY"}
    check = client.post("/api/cross-border/check", json=body, headers=rossi).json()
    assert check["decision"] == "ALLOW_CROSS_BORDER" and check["rule"] == 3 and "summary" not in check
    assert client.post("/api/cross-border/check", json=body, headers=patient).status_code == 403


def test_opted_out_patient_visible_for_treatment_not_research(client, store):
    h = login(client, "u-huber")
    assert client.get("/api/patients/p-4cfd3cf1/summary", headers=h).status_code == 200
    assert store.scalar("SELECT count(*) FROM hdab.patients WHERE patient_id = 'p-4cfd3cf1'") == 0


def test_hospital_inbox_and_provision(client):
    hdab, hosp = login(client, "u-novak"), login(client, "u-huber")
    client.post("/api/requests/evaluate", json={"id": "R05"}, headers=hdab)
    inbox = client.get("/api/provisions", headers=hosp).json()
    assert inbox and all(i["decision"] != "REJECT" and i["decided_at"] for i in inbox)
    done = client.post("/api/provisions/R05/provide", headers=hosp).json()
    assert done["status"] == "provided"


def test_public_pages_have_no_numbers(client):
    client.post("/api/requests/evaluate", json={"id": "R01"})
    reg = client.get("/api/register").json()
    assert reg and "answer" not in reg[0]
    assert client.get("/api/facilities-not-in-catalogue").json()
    assert client.post("/api/eligibility", json={"purpose": "set insurance premiums for customers"}).json()["result"] == "not_eligible"


def test_eligibility_wizard_matches_the_decision(client):
    """The wizard accepts a reason for records only if the decision on the real application would accept it too."""
    base = {"purpose": "Scientific health research", "purpose_code": "research", "need": "records",
            "qualified": True, "safeguards": True, "ethics": True}
    vague = client.post("/api/eligibility", json={**base, "why_not_statistics": "We need treatment sequences."}).json()
    assert vague["result"] == "statistics"
    clear = client.post("/api/eligibility", json={**base, "why_not_statistics": "We train a model on record-level histories."}).json()
    assert clear["result"] == "spe"
    assert client.post("/api/eligibility", json={**base, "why_not_statistics": "We train a model.", "ethics": False}).json()["result"] == "not_eligible"


def test_docs_page_can_sign_in(client):
    """The /docs "Authorize" button needs a security scheme; a plain Authorization header param is ignored by Swagger."""
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    assert schema["paths"]["/api/requests"]["get"]["security"] == [{"HTTPBearer": []}]

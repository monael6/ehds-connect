import pytest
from fastapi.testclient import TestClient

from tests.test_api import login


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def h(c, uid):
    return login(c, uid)


def test_bundle_patients_listed_with_names_for_their_hospital(client):
    rows = client.get("/api/patients", headers=h(client, "u-huber")).json()
    named = {r["patient_id"]: r["name"] for r in rows if r["name"]}
    assert named["P001"] == "Hermine Bruckner" and len(named) == 6
    assert client.get("/api/patients?search=bruckner", headers=h(client, "u-huber")).json()[0]["patient_id"] == "P001"


def test_documents_for_clinicians_only(client):
    docs = client.get("/api/patients/P001/documents", headers=h(client, "u-berger")).json()["documents"]
    assert len(docs) == 28 and docs[0]["date"] >= docs[-1]["date"]
    assert client.get("/api/patients/P001/documents", headers=h(client, "u-gruber")).status_code == 403


def test_summary_from_documents_keeps_traps(client):
    s = client.get("/api/patients/P001/summary?lang=en", headers=h(client, "u-huber")).json()
    assert [a["verification"] for a in s["allergies"]["items"]] == ["unconfirmed"]
    labels = " ".join(p["label"] for p in s["problems"])
    assert "Lungenembolie" not in labels
    assert "B01AB01" not in {m["code"] for m in s["medications"]}  # heparin was stopped
    assert all(p["source"].startswith("P001-D") for p in s["problems"])


def test_letter_draft_from_documents(client):
    letter = client.post("/api/discharge-letters", json={"patient_id": "P001"}, headers=h(client, "u-berger")).json()
    sec = {s["key"]: s for s in letter["content"]["sections"]}
    assert letter["content"]["header"]["stay"]["from"] == "2024-09-02"
    assert any("Ramipril 5mg" in i["text"] for i in sec["medikation"]["items"])
    assert any("abgesetzt" in i["text"] for i in sec["medikation"]["items"])
    assert sec["allergien"]["items"] and sec["empfehlungen"]["empty"]


def test_bundle_patients_not_in_secondary_use(client):
    from app.datastore import get_store
    assert get_store().scalar("SELECT count(*) FROM hdab.patients WHERE patient_id LIKE 'P00%'") == 0

import pytest
from fastapi.testclient import TestClient

from app.primary import records
from tests.test_api import login


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def h(c, uid):
    return login(c, uid)


def test_ai_checks_trim_trailing_periods_before_joining():
    rec = {
        "record": {
            "unverified": [],
            "must_not_include": [{
                "text": "The CT report mentions no embolism..  ",
                "detail": "Radiology report D005..  ",
                "sources": ["P001-D005"],
            }],
        },
        "documents": [{"id": "P001-D005", "typ": "Radiologiebefund"}],
    }

    checks = records.checks(rec)

    assert checks[0]["text"] == (
        "The CT report mentions no embolism – Radiology report D005. Please review the sources."
    )


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
    assert "embolism" not in labels.lower() and "Lungenembolie" not in labels
    assert any("P001-D015" in c["source"] for c in s["checks"])
    assert not any("ruled out" in c["text"] for c in s["checks"])
    assert any(": mentioned in the source documents, not included in this summary." in c["text"] for c in s["checks"])
    assert "B01AB01" not in {m["code"] for m in s["medications"]}  # heparin was stopped
    assert all(p["source"].startswith("P001-D") for p in s["problems"])


def test_letter_draft_from_documents(client):
    letter = client.post("/api/discharge-letters", json={"patient_id": "P001"}, headers=h(client, "u-berger")).json()
    sec = {s["key"]: s for s in letter["content"]["sections"]}
    assert letter["content"]["header"]["stay"]["from"] == "2024-09-02"
    assert any("Ramipril 5 mg" in i["text"] for i in sec["medikation"]["items"])
    assert any("stopped during the stay" in i["text"] for i in sec["medikation"]["items"])
    assert sec["allergien"]["items"] and sec["empfehlungen"]["empty"]


def test_bundle_patients_not_in_secondary_use(client):
    from app.datastore import get_store
    assert get_store().scalar("SELECT count(*) FROM hdab.patients WHERE patient_id LIKE 'P00%'") == 0


def test_all_bundles_english_and_no_system_diagnosis(client):
    import re
    hd = h(client, "u-huber")
    for pid in ["P001", "P002", "P003", "P004", "P005", "P006"]:
        docs = client.get(f"/api/patients/{pid}/documents", headers=hd).json()["documents"]
        assert not any(re.search(r"\b(und|mit|nach|der|die)\b", d["text"]) for d in docs), pid
        s = client.get(f"/api/patients/{pid}/summary", headers=hd).json()
        assert s["checks"] and all("Please review the sources" in c["text"] for c in s["checks"])
        assert "ruled out" not in str(s["checks"]).lower()

"""
seed.py – Load synthetic patients and their source documents into HAPI FHIR.

Runs once at startup (docker-compose restart: "no").
Creates:
  - Patient resource for each patient
  - Organization resource for Landesklinikum Musterstadt
  - DocumentReference for each document (content as base64 text/plain)
  - Practitioner resources for the 3 demo clinicians
  - CareTeam resources linking practitioners to patients

Environment:
  FHIR_BASE_URL  e.g. http://hapi-fhir:8080/fhir
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

FHIR_BASE = os.environ.get("FHIR_BASE_URL", "http://hapi-fhir:8080/fhir")
PATIENTS_DIR = Path("/app/patients")

# ── Practitioner definitions (mirror Keycloak users) ──────────────────────────
PRACTITIONERS = [
    {
        "id": "practitioner-mueller",
        "family": "Müller",
        "given": "Elisabeth",
        "identifier": "mueller@demo.klinik.at",
    },
    {
        "id": "practitioner-wagner",
        "family": "Wagner",
        "given": "Thomas",
        "identifier": "wagner@demo.klinik.at",
    },
    {
        "id": "practitioner-bauer",
        "family": "Bauer",
        "given": "Lukas",
        "identifier": "bauer@demo.klinik.at",
    },
]

# Assignment: patient → list of practitioner IDs
PATIENT_ASSIGNMENTS = {
    "P001": ["practitioner-mueller", "practitioner-bauer"],
    "P002": ["practitioner-mueller"],
    "P003": ["practitioner-wagner"],
    "P004": ["practitioner-bauer"],
    "P005": ["practitioner-mueller", "practitioner-wagner"],
    "P006": ["practitioner-wagner"],
}

HEADERS = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"}


def wait_for_fhir(retries: int = 20, delay: int = 5) -> None:
    print(f"Waiting for FHIR server at {FHIR_BASE} …", flush=True)
    for attempt in range(retries):
        try:
            r = requests.get(f"{FHIR_BASE}/metadata", timeout=10)
            if r.status_code == 200:
                print("FHIR server is ready.", flush=True)
                return
        except requests.RequestException:
            pass
        print(f"  attempt {attempt+1}/{retries} – not ready, retrying in {delay}s …", flush=True)
        time.sleep(delay)
    print("ERROR: FHIR server did not become ready. Exiting.", flush=True)
    sys.exit(1)


def put_resource(resource_type: str, resource_id: str, body: dict) -> dict:
    url = f"{FHIR_BASE}/{resource_type}/{resource_id}"
    r = requests.put(url, json=body, headers=HEADERS, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ERROR {r.status_code} PUT {url}: {r.text[:300]}", flush=True)
        r.raise_for_status()
    return r.json()


def seed_organization() -> str:
    """Create the main fictional hospital as an Organization."""
    org_id = "org-landesklinikum-musterstadt"
    put_resource("Organization", org_id, {
        "resourceType": "Organization",
        "id": org_id,
        "meta": {"tag": [{"system": "http://ips-hackathon/tags", "code": "mock-kis"}]},
        "active": True,
        "name": "Landesklinikum Musterstadt",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type",
                               "code": "prov", "display": "Healthcare Provider"}]}],
        "address": [{"city": "Musterstadt", "country": "AT"}],
    })
    print(f"  Seeded Organization/{org_id}", flush=True)
    return org_id


def seed_practitioners() -> None:
    for p in PRACTITIONERS:
        put_resource("Practitioner", p["id"], {
            "resourceType": "Practitioner",
            "id": p["id"],
            "meta": {"tag": [{"system": "http://ips-hackathon/tags", "code": "mock-kis"}]},
            "active": True,
            "identifier": [{"system": "http://ips-hackathon/practitioners", "value": p["identifier"]}],
            "name": [{"family": p["family"], "given": [p["given"]]}],
        })
        print(f"  Seeded Practitioner/{p['id']}", flush=True)


def gender_fhir(geschlecht: str) -> str:
    mapping = {"weiblich": "female", "maennlich": "male", "divers": "other"}
    return mapping.get(geschlecht, "unknown")


def seed_patient(demo: dict, org_id: str) -> str:
    pid = demo["patient_id"]
    fhir_id = f"patient-{pid.lower()}"
    put_resource("Patient", fhir_id, {
        "resourceType": "Patient",
        "id": fhir_id,
        "meta": {"tag": [{"system": "http://ips-hackathon/tags", "code": "mock-kis"}]},
        "identifier": [
            {"system": "http://ips-hackathon/patients", "value": pid},
            {"system": "http://ips-hackathon/versicherung",
             "value": demo["fiktive_versicherungsnummer"]},
        ],
        "active": True,
        "name": [{"family": demo["nachname"], "given": [demo["vorname"]]}],
        "gender": gender_fhir(demo["geschlecht"]),
        "birthDate": demo["geburtsdatum"],
        "address": [{"state": demo.get("wohnort_bundesland", ""), "country": "AT"}],
        "managingOrganization": {"reference": f"Organization/{org_id}"},
    })
    print(f"  Seeded Patient/{fhir_id} ({pid})", flush=True)
    return fhir_id


def seed_documents(docs: list, patient_fhir_id: str, pid: str, org_id: str) -> None:
    for doc in docs:
        doc_id = doc["id"].lower().replace("-", "")
        content_b64 = base64.b64encode(doc["text"].encode("utf-8")).decode("ascii")
        # Map doc type to LOINC (best-effort; unknown types get a fallback)
        loinc = _doc_type_loinc(doc.get("typ", ""))
        put_resource("DocumentReference", f"docref-{doc_id}", {
            "resourceType": "DocumentReference",
            "id": f"docref-{doc_id}",
            "meta": {"tag": [{"system": "http://ips-hackathon/tags", "code": "mock-kis"}]},
            "status": "current",
            "type": {"coding": [{"system": "http://loinc.org", "code": loinc}],
                     "text": doc.get("typ", "")},
            "category": [{"coding": [{"system": "http://loinc.org", "code": "11503-0",
                                       "display": "Medical records"}]}],
            "subject": {"reference": f"Patient/{patient_fhir_id}"},
            "date": doc["datum"] + ":00+01:00" if len(doc["datum"]) == 16 else doc["datum"],
            "author": [{"display": f"{doc.get('autor_rolle','')} – {doc.get('einrichtung','')}"}],
            "custodian": {"reference": f"Organization/{org_id}"},
            "description": doc.get("titel", ""),
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain; charset=utf-8",
                        "data": content_b64,
                        "title": doc.get("titel", ""),
                        "language": "de-AT",
                    }
                }
            ],
            "context": {
                "related": [{"identifier": {"value": doc["id"]}}]
            },
            "extension": [
                {
                    "url": "http://ips-hackathon/extensions/source-doc-id",
                    "valueString": doc["id"],
                },
                {
                    "url": "http://ips-hackathon/extensions/fachrichtung",
                    "valueString": doc.get("fachrichtung", ""),
                },
            ],
        })
    print(f"  Seeded {len(docs)} DocumentReferences for {pid}", flush=True)


def seed_care_team(pid: str, patient_fhir_id: str) -> None:
    practitioner_ids = PATIENT_ASSIGNMENTS.get(pid, [])
    participants = [
        {
            "role": [{"coding": [{"system": "http://snomed.info/sct",
                                  "code": "223366009",
                                  "display": "Healthcare professional"}]}],
            "member": {"reference": f"Practitioner/{prac_id}"},
        }
        for prac_id in practitioner_ids
    ]
    ct_id = f"careteam-{pid.lower()}"
    put_resource("CareTeam", ct_id, {
        "resourceType": "CareTeam",
        "id": ct_id,
        "meta": {"tag": [{"system": "http://ips-hackathon/tags", "code": "mock-kis"}]},
        "status": "active",
        "subject": {"reference": f"Patient/{patient_fhir_id}"},
        "participant": participants,
    })
    print(f"  Seeded CareTeam/{ct_id}", flush=True)


def _doc_type_loinc(typ: str) -> str:
    mapping = {
        "Aufnahmebefund": "34133-9",
        "Verlaufseintrag": "11506-3",
        "Pflegebericht": "46240-8",
        "Laborbefund": "26436-6",
        "Radiologiebefund": "18748-4",
        "Konsiliarbefund": "11488-4",
        "OP-Bericht": "11504-8",
        "Anaesthesieprotokoll": "11504-8",
        "Intensivverlegungsbericht": "34133-9",
        "Medikationsanordnung": "57833-6",
        "Physiotherapiebericht": "11506-3",
        "Ambulanzbefund": "34133-9",
        "Zuweisung": "57133-1",
        "Vorbefund": "34133-9",
        "Entlassungsbrief": "18842-5",
    }
    return mapping.get(typ, "34133-9")


def main() -> None:
    wait_for_fhir()

    org_id = seed_organization()
    seed_practitioners()

    patient_dirs = sorted(PATIENTS_DIR.glob("P*"))
    if not patient_dirs:
        print(f"WARNING: No patient directories found under {PATIENTS_DIR}", flush=True)

    for patient_dir in patient_dirs:
        pid = patient_dir.name
        patient_file = patient_dir / "patient.json"
        docs_file = patient_dir / "documents.json"

        if not patient_file.exists() or not docs_file.exists():
            print(f"  Skipping {pid}: missing patient.json or documents.json", flush=True)
            continue

        demo = json.loads(patient_file.read_text(encoding="utf-8"))
        docs = json.loads(docs_file.read_text(encoding="utf-8"))

        fhir_patient_id = seed_patient(demo, org_id)
        seed_documents(docs, fhir_patient_id, pid, org_id)
        seed_care_team(pid, fhir_patient_id)

    print("\nSeed complete.", flush=True)


if __name__ == "__main__":
    main()

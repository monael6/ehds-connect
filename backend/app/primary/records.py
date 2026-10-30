"""Patient record bundles in `patients/Pxxx/`: identity, clinical documents and the structured
record taken from those documents (`ground_truth_ips.json`).

Primary use only: the patients are added to kis.* after the hdab schema is built, so they never
reach secondary-use statistics. Every statement keeps the documents it comes from.
"""
from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from ..config import BACKEND_DIR
from ..datastore import DataStore

PATIENTS_DIR = Path(os.getenv("EHDS_PATIENTS_DIR", BACKEND_DIR.parent / "patients"))
SEX = {"weiblich": "female", "maennlich": "male", "männlich": "male"}
TYPE = {"Entlassungsbrief": "Discharge letter", "Ambulanzbefund": "Outpatient report", "Zuweisung": "Referral", "Aufnahmebefund": "Admission report",
        "Pflegebericht": "Nursing report", "Laborbefund": "Laboratory report", "Radiologiebefund": "Radiology report", "Verlaufseintrag": "Progress note",
        "Anaesthesieprotokoll": "Anaesthesia record", "OP-Bericht": "Surgery report", "Konsiliarbefund": "Consultation report", "Vorbefund": "Previous report",
        "Medikationsanordnung": "Medication order", "Physiotherapiebericht": "Physiotherapy report", "Intensivverlegungsbericht": "ICU transfer report"}
WORDS = {"Pädiatrie": "Paediatrics", "Pneumologie": "Pulmonology", "Allgemeinmedizin": "General practice", "Allgemeinchirurgie": "General surgery",
         "Pflege": "Nursing", "Labor": "Laboratory", "Radiologie": "Radiology", "Anästhesiologie": "Anaesthesiology", "Gynäkologie": "Gynaecology",
         "Kardiologie": "Cardiology", "Interventionskardiologe": "Interventional cardiology", "Neurologie": "Neurology", "Innere Medizin": "Internal medicine",
         "Onkologie": "Oncology", "Unfallchirurgie": "Trauma surgery", "Physiotherapie": "Physiotherapy", "Intensivmedizin": "Intensive care",
         "Oberarzt": "Senior doctor", "Hausarzt": "General practitioner", "Assistenzarzt": "Resident doctor", "Chirurgie": "Surgery"}
FACILITY = [("Landesklinikum Musterstadt", "Musterstadt Regional Hospital"), ("Landeskrankenhaus", "Regional Hospital"), ("LKH", "Regional Hospital"),
            ("Universitätsklinik", "University Hospital"), ("Kinderkrankenhaus", "Children's Hospital"), ("Krankenhaus", "Hospital"),
            ("Ordination Dr.", "Practice of Dr."), ("Ärztlicher Bereitschaftsdienst", "Out-of-hours medical service"),
            ("Ambulatorium Atemwegszentrum", "Respiratory outpatient centre"), ("Gedächtnisambulanz", "Memory clinic,"),
            ("Neurologische Ambulanz", "Neurology outpatient clinic,"), ("Zentrallabor", "Central laboratory"), ("Institut für Radiologie", "Radiology"),
            ("Schrittmacherambulanz", "Pacemaker clinic"), ("Herzkatheterlabor", "Cardiac catheter lab")]


def english(text: str) -> str:
    for de, en in [*FACILITY, *sorted(WORDS.items(), key=lambda kv: -len(kv[0]))]:
        text = text.replace(de, en)
    return text


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_all() -> dict[str, dict]:
    out = {}
    if not PATIENTS_DIR.is_dir():
        return out
    for d in sorted(PATIENTS_DIR.iterdir()):
        if not (d / "patient.json").exists():
            continue
        patient = _read(d / "patient.json")
        docs = sorted(_read(d / "documents.json"), key=lambda x: x["datum"]) if (d / "documents.json").exists() else []
        record = _read(d / "ground_truth_ips.json") if (d / "ground_truth_ips.json").exists() else {}
        en = _read(d / "en.json") if (d / "en.json").exists() else {}
        if en:
            record = en.get("record", record)
            docs = [{**x, **({"titel": en["documents"][x["id"]]["title"], "text": en["documents"][x["id"]]["text"]}
                             if x["id"] in en.get("documents", {}) else {})} for x in docs]
        out[patient["patient_id"]] = {"patient": patient, "documents": docs, "record": record, "stay": _stay(patient, docs, record)}
    return out


def get(pid: str) -> dict | None:
    return load_all().get(pid)


def name(rec: dict) -> str:
    p = rec["patient"]
    return f"{p['vorname']} {p['nachname']}"


def matching(text: str) -> list[str]:
    t = text.lower()
    return [pid for pid, r in load_all().items() if t and t in name(r).lower()]


def _stay(patient: dict, docs: list[dict], record: dict) -> dict | None:
    admissions = [d for d in docs if d["typ"] == "Aufnahmebefund"]
    if not admissions:
        return None
    adm = admissions[-1]
    after = [d for d in docs if d["datum"] >= adm["datum"]]
    letters = [d for d in after if d["typ"] == "Entlassungsbrief"]
    end = (letters[-1] if letters else after[-1])["datum"][:10]
    problems = record.get("problems_active") or []
    return {"encounter_id": f"{patient['patient_id']}-STAY", "start_date": adm["datum"][:10], "end_date": end,
            "department": english((letters[-1] if letters else adm)["fachrichtung"]),
            "primary_icd10": problems[0].get("icd10") if problems else None,
            "admission_doc": adm["id"], "discharge_doc": letters[-1]["id"] if letters else None}


def sources(rec: dict, ids: list[str]) -> str:
    types = {d["id"]: TYPE.get(d["typ"], d["typ"]) for d in rec["documents"]}
    return "; ".join(f"{i} {types.get(i, 'document')}" for i in ids)


def documents(rec: dict) -> list[dict]:
    return [{"id": d["id"], "date": d["datum"], "type": TYPE.get(d["typ"], d["typ"]), "specialty": english(d["fachrichtung"]),
             "author_role": english(d["autor_rolle"]), "facility": english(d["einrichtung"]), "title": d["titel"], "text": d["text"]}
            for d in reversed(rec["documents"])]


def checks(rec: dict) -> list[dict]:
    """Statements the documents mention but the record does not take over; the doctor decides."""
    record = rec["record"]
    ai_record = "unverified" in record
    ai_labels = {
        "negated": "Negative statement in the documents",
        "ruled_out": "Suspicion discussed in the documents",
        "family_history": "Family history",
        "unconfirmed": "Reported, not confirmed in the documents",
    }
    checks = []
    for item in record.get("must_not_include", []):
        if ai_record:
            label = ai_labels.get(item.get("reason"), "Mentioned in the documents")
            item_text = (item.get("text") or "").rstrip(" .")
            text = f"{label}: {item_text}. Please review the sources."
        else:
            text = f"{item['text']}: mentioned in the source documents, not included in this summary. Please review the sources."
        checks.append({"text": text, "source": sources(rec, item.get("sources", []))})
    checks.extend({"text": f"{x['text']}: the AI could not find this statement word-for-word in the source documents. Please review the sources.",
                   "source": sources(rec, x.get("sources", []))}
                  for x in record.get("unverified", []))
    return checks


def add_to_kis(store: DataStore, hospital: str, reference_date: str) -> int:
    """Adds the bundles as patients of `hospital` in kis.* only (hdab is already built)."""
    recs = load_all()
    if not recs:
        return 0
    ref_year = date.fromisoformat(reference_date).year
    ids = list(recs)
    marks = ",".join("?" * len(ids))
    with store.lock:
        con = store.con
        con.execute(f"DELETE FROM kis.patients WHERE patient_id IN ({marks})", ids)
        con.execute(f"DELETE FROM kis.encounters WHERE patient_id IN ({marks})", ids)
        for pid, r in recs.items():
            p = r["patient"]
            born = p["geburtsdatum"]
            con.execute("INSERT INTO kis.patients (patient_id, sex, birth_date, age, region, data_holder, opted_out, deceased_date) "
                        "VALUES (?, ?, CAST(? AS DATE), ?, ?, ?, FALSE, NULL)",
                        [pid, SEX.get(p["geschlecht"], p["geschlecht"]), born, ref_year - int(born[:4]), p["wohnort_bundesland"], hospital])
            s = r["stay"]
            if s:
                con.execute("INSERT INTO kis.encounters (encounter_id, patient_id, type, start_date, end_date, primary_icd10, "
                            "data_holder, length_of_stay) VALUES (?, ?, 'inpatient', CAST(? AS DATE), CAST(? AS DATE), ?, ?, "
                            "date_diff('day', CAST(? AS DATE), CAST(? AS DATE)))",
                            [s["encounter_id"], pid, s["start_date"], s["end_date"], s["primary_icd10"], hospital,
                             s["start_date"], s["end_date"]])
    return len(recs)

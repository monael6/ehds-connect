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
            "department": (letters[-1] if letters else adm)["fachrichtung"],
            "primary_icd10": problems[0].get("icd10") if problems else None,
            "admission_doc": adm["id"], "discharge_doc": letters[-1]["id"] if letters else None}


def sources(rec: dict, ids: list[str]) -> str:
    types = {d["id"]: d["typ"] for d in rec["documents"]}
    return "; ".join(f"{i} {types.get(i, 'document')}" for i in ids)


def documents(rec: dict) -> list[dict]:
    return [{"id": d["id"], "date": d["datum"], "type": d["typ"], "specialty": d["fachrichtung"], "author_role": d["autor_rolle"],
             "facility": d["einrichtung"], "title": d["titel"], "text": d["text"]} for d in reversed(rec["documents"])]


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

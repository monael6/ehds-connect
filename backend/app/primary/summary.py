"""Patient Summary (IPS content) built on demand from the KIS view, readable in EN/DE/IT.

Primary use reads kis.* (all patients, opt-out does not apply to treatment).
"""
from __future__ import annotations

from ..config import settings
from ..datastore import DataStore
from . import terminology as T


def patient(store: DataStore, pid: str) -> dict | None:
    rows = store.sql("SELECT * FROM kis.patients WHERE patient_id = ?", [pid])
    return rows[0] if rows else None


def search(store: DataStore, text: str = "", data_holder: str | None = None, limit: int = 50) -> list[dict]:
    where, params = ["1=1"], []
    if text:
        where.append("patient_id ILIKE ?")
        params.append(f"%{text}%")
    if data_holder:
        where.append("data_holder = ?")
        params.append(data_holder)
    params.append(limit)
    return store.sql(f"""SELECT p.patient_id, p.sex, year(p.birth_date) AS birth_year, p.age, p.region, p.data_holder,
                p.opted_out, (SELECT count(*) FROM kis.encounters e WHERE e.patient_id = p.patient_id AND e.type = 'inpatient') AS stays
                FROM kis.patients p WHERE {' AND '.join(where)}
                ORDER BY (p.patient_id = 'p-4cfd3cf1') DESC, stays DESC, p.patient_id LIMIT ?""", params)


def build(store: DataStore, pid: str, lang: str = "en", sections: set[str] | None = None) -> dict | None:
    p = patient(store, pid)
    if not p:
        return None
    ref = settings.reference_date
    cond = store.sql("SELECT code, description, date FROM kis.conditions WHERE patient_id = ? ORDER BY date", [pid])
    meds = store.sql("""SELECT code, description, date, end_date FROM kis.medications WHERE patient_id = ?
                        AND date <= CAST(? AS DATE) AND (end_date IS NULL OR end_date >= CAST(? AS DATE)) ORDER BY date""",
                     [pid, ref, ref])
    obs = store.sql("""SELECT code, description, arg_max(value, date) AS value, arg_max(unit, date) AS unit, max(date) AS date
                       FROM kis.observations WHERE patient_id = ? GROUP BY code, description ORDER BY code""", [pid])
    stays = store.sql("""SELECT encounter_id, start_date, end_date, primary_icd10, data_holder FROM kis.encounters
                         WHERE patient_id = ? AND type = 'inpatient' ORDER BY start_date DESC""", [pid])
    want = sections or {"problems", "medications", "allergies", "results"}

    problems = [{"code": c["code"], "system": "ICD-10", "label": T.label(c["code"], lang, c["description"]),
                 "since": str(c["date"]), "source": f"KIS {p['data_holder']}: diagnosis {c['date']}"} for c in cond]
    medications = [{"code": m["code"], "system": "ATC", "label": T.label(m["code"], lang, m["description"]),
                    "since": str(m["date"]), "dose": None, "source": f"KIS {p['data_holder']}: prescription {m['date']}"}
                   for m in meds]
    results = [{"code": o["code"], "system": "LOINC", "label": T.label(o["code"], lang, o["description"]),
                "value": o["value"], "unit": o["unit"], "date": str(o["date"]),
                "source": f"KIS {p['data_holder']}: measurement {o['date']}"} for o in obs]

    emergency = []
    for m in meds:
        for prefix, text in T.EMERGENCY_ATC.items():
            if m["code"].startswith(prefix):
                emergency.append({"type": "medication", "text": f"{T.label(m['code'], lang, m['description'])}: {text.get(lang, text['en'])}"})
    for c in cond:
        if c["code"].startswith(T.EMERGENCY_ICD):
            emergency.append({"type": "condition", "text": T.label(c["code"], lang, c["description"])})

    out = {
        "patient": {"id": pid, "sex": p["sex"], "birth_date": str(p["birth_date"]), "age": p["age"], "region": p["region"],
                    "data_holder": p["data_holder"], "opted_out_of_secondary_use": p["opted_out"]},
        "language": lang,
        "generated_from": f"KIS {p['data_holder']} (on demand)",
        "headings": {k: T.ui(k, lang) for k in ("problems", "medications", "allergies", "results", "emergency")},
        "emergency": emergency,
        "last_stay": stays[0] if stays else None,
    }
    if "problems" in want:
        out["problems"] = problems
    if "medications" in want:
        out["medications"] = medications
    if "allergies" in want:
        out["allergies"] = {"items": [], "note": T.ui("no_allergy", lang)}
    if "results" in want:
        out["results"] = results
    out["hidden_sections"] = sorted({"problems", "medications", "allergies", "results"} - want)
    return out

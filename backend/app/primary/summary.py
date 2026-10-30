"""Patient Summary (IPS content) built on demand from the KIS view, readable in EN/DE/IT.

Primary use reads kis.* (all patients, opt-out does not apply to treatment).
"""
from __future__ import annotations

from ..config import settings
from ..datastore import DataStore
from . import records
from . import terminology as T


def patient(store: DataStore, pid: str) -> dict | None:
    rows = store.sql("SELECT * FROM kis.patients WHERE patient_id = ?", [pid])
    return rows[0] if rows else None


def search(store: DataStore, text: str = "", data_holder: str | None = None, limit: int = 50) -> list[dict]:
    where, params = ["1=1"], []
    if text:
        named = records.matching(text)
        where.append("(patient_id ILIKE ?" + "".join(" OR patient_id = ?" for _ in named) + ")")
        params += [f"%{text}%", *named]
    if data_holder:
        where.append("data_holder = ?")
        params.append(data_holder)
    bundles = list(records.load_all()) or [""]
    params += [*bundles, limit]
    return store.sql(f"""SELECT p.patient_id, p.sex, year(p.birth_date) AS birth_year, p.age, p.region, p.data_holder,
                p.opted_out, (SELECT count(*) FROM kis.encounters e WHERE e.patient_id = p.patient_id AND e.type = 'inpatient') AS stays,
                (SELECT max(e.start_date) FROM kis.encounters e WHERE e.patient_id = p.patient_id AND e.type = 'inpatient') AS last_stay_from,
                (SELECT arg_max(e.end_date, e.start_date) FROM kis.encounters e
                 WHERE e.patient_id = p.patient_id AND e.type = 'inpatient') AS last_stay_to
                FROM kis.patients p WHERE {' AND '.join(where)}
                ORDER BY (p.patient_id = 'p-4cfd3cf1') DESC,
                (p.patient_id IN ({','.join('?' * len(bundles))})) DESC, stays DESC, p.patient_id LIMIT ?""", params)


def build(store: DataStore, pid: str, lang: str = "en", sections: set[str] | None = None) -> dict | None:
    p = patient(store, pid)
    if not p:
        return None
    rec = records.get(pid)
    if rec:
        return _from_record(p, rec, lang, sections)
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
                emergency.append({"type": "medication", "code": m["code"],
                                  "text": f"{T.label(m['code'], lang, m['description'])}: {text.get(lang, text['en'])}"})
    for c in cond:
        if c["code"].startswith(T.EMERGENCY_ICD):
            emergency.append({"type": "condition", "code": c["code"], "text": T.label(c["code"], lang, c["description"])})

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


def _from_record(p: dict, rec: dict, lang: str, sections: set[str] | None) -> dict:
    """Patient Summary for a record bundle: every entry names the documents it was taken from."""
    r, src = rec["record"], lambda x: records.sources(rec, x.get("sources", []))
    want = sections or {"problems", "medications", "allergies", "results"}
    problems = [{"code": x["icd10"], "system": "ICD-10", "label": x["text"], "since": x.get("onset"), "source": src(x)}
                for x in r.get("problems_active", []) if x.get("icd10")]
    medications = [{"code": m["atc"], "system": "ATC", "label": m["active_ingredient"], "since": None, "dose": m.get("dose"),
                    "status": m.get("status"), "source": src(m)} for m in r.get("medication_at_discharge", []) if m.get("atc")]
    allergies = [{"code": f"{p['patient_id']}-A{i + 1}",
                  "label": a["substance"] + (" (unconfirmed)" if a.get("verification") == "unconfirmed" else ""),
                  "severity": a.get("criticality"), "reaction": a.get("reaction"), "verification": a.get("verification"),
                  "source": src(a)} for i, a in enumerate(r.get("allergies_intolerances", []))]
    results = [{"code": f"{p['patient_id']}-R{i + 1}", "system": "document", "label": k["text"], "value": k["value"], "unit": None,
                "date": k.get("date"), "source": src(k)} for i, k in enumerate(r.get("key_results", []))]
    emergency = [{"type": "allergy", "code": a["code"], "text": f"{a['label']}: {a['reaction']}"} for a in allergies]
    for m in medications:
        for prefix, text in T.EMERGENCY_ATC.items():
            if m["code"].startswith(prefix):
                emergency.append({"type": "medication", "code": m["code"], "text": f"{m['label']}: {text.get(lang, text['en'])}"})
    for x in problems:
        if x["code"].startswith(T.EMERGENCY_ICD):
            emergency.append({"type": "condition", "code": x["code"], "text": x["label"]})
    emergency += [{"type": "device", "text": d["text"]} for d in r.get("medical_devices_implants", [])]
    stay = rec["stay"]
    out = {
        "patient": {"id": p["patient_id"], "name": records.name(rec), "sex": p["sex"], "birth_date": str(p["birth_date"]), "age": p["age"],
                    "region": p["region"], "data_holder": p["data_holder"], "opted_out_of_secondary_use": p["opted_out"]},
        "language": lang,
        "generated_from": f"{len(rec['documents'])} clinical documents of {records.name(rec)} (on demand)",
        "headings": {k: T.ui(k, lang) for k in ("problems", "medications", "allergies", "results", "emergency")},
        "emergency": emergency,
        "last_stay": {**stay, "data_holder": p["data_holder"]} if stay else None,
        "past_history": [{"code": x.get("icd10"), "label": x["text"], "resolved": x.get("resolved"), "source": src(x)}
                         for x in r.get("past_history", [])],
        "procedures": [{"label": x["text"], "date": x.get("date"), "source": src(x)} for x in r.get("procedures", [])],
        "devices": [{"label": x["text"], "since": x.get("since"), "source": src(x)} for x in r.get("medical_devices_implants", [])],
        "checks": records.checks(rec),
    }
    if "problems" in want:
        out["problems"] = problems
    if "medications" in want:
        out["medications"] = medications
    if "allergies" in want:
        out["allergies"] = {"items": allergies, "note": "" if allergies else T.ui("no_allergy", lang)}
    if "results" in want:
        out["results"] = results
    out["hidden_sections"] = sorted({"problems", "medications", "allergies", "results"} - want)
    return out

"""Discharge letter (Entlassungsbrief) following the Austrian ELGA guide's section order.

- the draft is filled only from KIS data, each statement with its source; missing data is
  marked "No data in the KIS – please complete" (nothing is invented)
- every edit is stored with before/after, editor and optional reason
- signing (Vidierung) needs the confirmation, a second factor and all required sections filled
- after signing the letter is read-only; corrections create a new version that supersedes it
- only signed letters can be sent to ELGA / GP
"""
from __future__ import annotations

import json
import uuid

from fastapi import HTTPException

from .. import state
from ..datastore import DataStore
from . import terminology as T

NO_DATA = "No data in the KIS – please complete"

# (key, ELGA heading, required)
SECTIONS = [
    ("brieftext", "Brieftext", False),
    ("aufnahmegrund", "Aufnahmegrund", True),
    ("diagnosen", "Diagnose bei Entlassung", True),
    ("massnahmen", "Durchgeführte Maßnahmen", False),
    ("medikation", "Empfohlene Medikation", True),
    ("empfehlungen", "Weitere empfohlene Maßnahmen", True),
    ("zusammenfassung", "Zusammenfassung des Aufenthalts", False),
    ("allergien", "Allergien, Unverträglichkeiten und Risiken", False),
    ("befunde", "Erhobene Befunde", False),
    ("anamnese", "Anamnese", False),
    ("fruehere", "Frühere Erkrankungen", False),
    ("medikation_einweisung", "Medikation bei Einweisung", False),
    ("bemerkungen", "Abschließende Bemerkungen", False),
]
REQUIRED = [k for k, _, r in SECTIONS if r]


def _section(key: str, items: list[dict] | None = None, text: str = "") -> dict:
    heading, required = next((h, r) for k, h, r in SECTIONS if k == key)
    empty = not items and not text
    return {"key": key, "heading": heading, "required": required, "items": items or [],
            "text": text or (NO_DATA if empty else ""), "empty": empty, "last_edited_by": None}


def draft_from_kis(store: DataStore, pid: str, encounter_id: str | None = None) -> dict:
    stays = store.sql("""SELECT * FROM kis.encounters WHERE patient_id = ? AND type = 'inpatient'
                         AND (? IS NULL OR encounter_id = ?) ORDER BY start_date DESC""", [pid, encounter_id, encounter_id])
    if not stays:
        raise HTTPException(404, "No inpatient stay for this patient in the KIS")
    stay = stays[0]
    p = store.sql("SELECT * FROM kis.patients WHERE patient_id = ?", [pid])[0]
    src = f"KIS {stay['data_holder']}"
    end = stay["end_date"] or stay["start_date"]
    cond = store.sql("SELECT code, description, date FROM kis.conditions WHERE patient_id = ? ORDER BY date", [pid])
    meds = store.sql("SELECT code, description, date, end_date FROM kis.medications WHERE patient_id = ? ORDER BY date", [pid])
    obs = store.sql("""SELECT code, description, value, unit, date FROM kis.observations WHERE patient_id = ?
                       AND date BETWEEN CAST(? AS DATE) - INTERVAL 365 DAY AND CAST(? AS DATE) ORDER BY date""",
                    [pid, stay["start_date"], end])

    main = stay["primary_icd10"]
    diag = []
    if main:
        diag.append({"role": "Hauptdiagnose", "code": main, "system": "ICD-10", "text": T.label(main, "de"),
                     "source": f"{src}: Aufenthalt {stay['encounter_id']}, Hauptdiagnose"})
    for c in cond:
        if c["code"] != main:
            diag.append({"role": "Nebendiagnose", "code": c["code"], "system": "ICD-10",
                         "text": T.label(c["code"], "de", c["description"]),
                         "source": f"{src}: Diagnose seit {c['date']}"})

    def status(m: dict) -> str:
        if m["end_date"] and m["end_date"] <= end:
            return "stopped"
        if stay["start_date"] <= m["date"] <= end:
            return "new"
        return "unchanged"

    rec = [{"code": m["code"], "system": "ATC", "text": T.label(m["code"], "de", m["description"]), "dose": None,
            "status": status(m), "source": f"{src}: Verordnung {m['date']}"}
           for m in meds if m["date"] <= end and status(m) != "stopped"]
    stopped = [{"code": m["code"], "system": "ATC", "text": T.label(m["code"], "de", m["description"]), "status": "stopped",
                "source": f"{src}: beendet {m['end_date']}"} for m in meds if m["date"] <= end and status(m) == "stopped"]
    on_admission = [{"code": m["code"], "system": "ATC", "text": T.label(m["code"], "de", m["description"]),
                     "source": f"{src}: Verordnung {m['date']}"} for m in meds if m["date"] < stay["start_date"]
                    and (m["end_date"] is None or m["end_date"] >= stay["start_date"])]
    findings = [{"code": o["code"], "system": "LOINC", "text": T.label(o["code"], "de", o["description"]),
                 "value": o["value"], "unit": o["unit"], "date": str(o["date"]),
                 "abnormal": _abnormal(o["code"], o["value"]), "source": f"{src}: Messung {o['date']}"} for o in obs]
    earlier = [d for d in diag if d["role"] == "Nebendiagnose"]

    reason = [{"text": f"Stationäre Aufnahme am {stay['start_date']} mit Hauptdiagnose {T.label(main, 'de')} ({main}).",
               "source": f"{src}: Aufenthalt {stay['encounter_id']}"}] if main else []
    summary = [{"text": f"Stationärer Aufenthalt vom {stay['start_date']} bis {stay['end_date']} "
                        f"({stay['length_of_stay']:.0f} Tage) im {stay['data_holder']}.",
                "source": f"{src}: Aufenthalt {stay['encounter_id']}"}]
    sections = [
        _section("brieftext"),
        _section("aufnahmegrund", reason),
        _section("diagnosen", diag),
        _section("massnahmen"),
        _section("medikation", rec + stopped),
        _section("empfehlungen"),
        _section("zusammenfassung", summary),
        _section("allergien"),
        _section("befunde", findings),
        _section("anamnese"),
        _section("fruehere", earlier),
        _section("medikation_einweisung", on_admission),
        _section("bemerkungen"),
    ]
    return {
        "header": {"patient_id": pid, "sex": p["sex"], "birth_date": str(p["birth_date"]),
                   "stay": {"encounter_id": stay["encounter_id"], "from": str(stay["start_date"]), "to": str(stay["end_date"])},
                   "hospital": stay["data_holder"], "author": None, "signing_physician": None, "contact_person": None},
        "sections": sections,
        "not_written_by_system": ["no doses that are not in the data", "no diagnoses inferred from lab values",
                                  "no prognosis statements"],
    }


def _abnormal(code: str, v) -> bool:
    if v is None:
        return False
    limits = {"4548-4": (None, 6.5), "39156-5": (18.5, 30), "8480-6": (None, 140), "62238-1": (60, None)}
    lo, hi = limits.get(code, (None, None))
    return (lo is not None and v < lo) or (hi is not None and v >= hi)


# ------------------------------------------------------------------ storage
def _row(letter_id: str) -> dict:
    row = state.one("SELECT * FROM letters WHERE id = ?", (letter_id,))
    if not row:
        raise HTTPException(404, "Letter not found")
    row["content"] = json.loads(row["content"])
    row["edit_history"] = state.query("SELECT * FROM letter_edits WHERE letter_id = ? ORDER BY id", (letter_id,))
    row["versions"] = state.query("SELECT id, version, status, signed_by, signed_at, created_at FROM letters "
                                  "WHERE patient_id = ? AND encounter_id IS ? ORDER BY version",
                                  (row["patient_id"], row["encounter_id"]))
    row["missing_required"] = missing_required(row["content"])
    return row


def missing_required(content: dict) -> list[str]:
    return [s["heading"] for s in content["sections"] if s["required"] and s["empty"]]


def create(store: DataStore, pid: str, user: dict, encounter_id: str | None = None) -> dict:
    content = draft_from_kis(store, pid, encounter_id)
    content["header"]["author"] = "EHDS Connect (draft from KIS data)"
    content["header"]["signing_physician"] = None
    content["header"]["contact_person"] = user["name"]
    enc = content["header"]["stay"]["encounter_id"]
    last = state.one("SELECT max(version) v FROM letters WHERE patient_id = ? AND encounter_id = ?", (pid, enc))
    lid = f"L-{uuid.uuid4().hex[:8]}"
    with state.tx() as c:
        now = state.now()
        c.execute("INSERT INTO letters (id,patient_id,encounter_id,version,status,content,created_at,updated_at) "
                  "VALUES (?,?,?,?,?,?,?,?)", (lid, pid, enc, (last["v"] or 0) + 1, "draft",
                                               json.dumps(content, ensure_ascii=False, default=str), now, now))
        state.audit(user, "primary", "letter_draft_created", patient_id=pid, outcome="draft",
                    details={"letter_id": lid, "encounter_id": enc}, conn=c)
    return _row(lid)


def get(letter_id: str) -> dict:
    return _row(letter_id)


def edit_section(letter_id: str, key: str, text: str | None, items: list[dict] | None, reason: str | None, user: dict) -> dict:
    row = _row(letter_id)
    if row["status"] != "draft":
        raise HTTPException(409, "Signed letters are read-only. Create a corrected version.")
    content = row["content"]
    sec = next((s for s in content["sections"] if s["key"] == key), None)
    if sec is None:
        raise HTTPException(404, f"Unknown section {key}")
    before = {"text": sec["text"], "items": sec["items"]}
    if text is not None:
        sec["text"] = text
    if items is not None:
        sec["items"] = items
    sec["empty"] = not sec["items"] and (not sec["text"] or sec["text"] == NO_DATA)
    sec["last_edited_by"] = {"name": user["name"], "at": state.now()}
    with state.tx() as c:
        c.execute("UPDATE letters SET content = ?, updated_at = ? WHERE id = ?",
                  (json.dumps(content, ensure_ascii=False, default=str), state.now(), letter_id))
        c.execute("INSERT INTO letter_edits (letter_id, section, before, after, reason, editor_id, editor_name, ts) "
                  "VALUES (?,?,?,?,?,?,?,?)", (letter_id, key, json.dumps(before, ensure_ascii=False, default=str),
                                               json.dumps({"text": sec["text"], "items": sec["items"]}, ensure_ascii=False, default=str),
                                               reason, user["id"], user["name"], state.now()))
        state.audit(user, "primary", "letter_section_edited", patient_id=row["patient_id"], outcome="saved",
                    details={"letter_id": letter_id, "section": key, "reason": reason}, conn=c)
    return _row(letter_id)


def sign(letter_id: str, confirmed: bool, second_factor: str | None, user: dict) -> dict:
    row = _row(letter_id)
    if row["status"] != "draft":
        raise HTTPException(409, f"Letter is already {row['status']}")
    if not confirmed:
        raise HTTPException(400, "Confirm that you reviewed the letter and take medical responsibility")
    if not second_factor or not second_factor.isdigit() or len(second_factor) != 6:
        state.audit(user, "primary", "letter_sign_failed", patient_id=row["patient_id"], outcome="second_factor",
                    details={"letter_id": letter_id})
        raise HTTPException(401, "Second factor required (6 digits)")
    missing = row["missing_required"]
    if missing:
        state.audit(user, "primary", "letter_sign_blocked", patient_id=row["patient_id"], outcome="required_missing",
                    details={"letter_id": letter_id, "missing": missing})
        raise HTTPException(422, {"message": "Required sections are empty", "missing": missing})
    content = row["content"]
    content["header"]["signing_physician"] = user["name"]
    with state.tx() as c:
        now = state.now()
        c.execute("UPDATE letters SET status='signed', signed_by=?, signed_at=?, content=?, updated_at=? WHERE id=?",
                  (user["name"], now, json.dumps(content, ensure_ascii=False, default=str), now, letter_id))
        state.audit(user, "primary", "letter_signed", patient_id=row["patient_id"], outcome="signed",
                    details={"letter_id": letter_id, "method": "personal login + second factor"}, conn=c)
    return _row(letter_id)


def correct(letter_id: str, user: dict) -> dict:
    row = _row(letter_id)
    if row["status"] != "signed":
        raise HTTPException(409, "Only signed letters can be corrected; edit the draft instead")
    lid = f"L-{uuid.uuid4().hex[:8]}"
    content = row["content"]
    content["header"]["signing_physician"] = None
    with state.tx() as c:
        now = state.now()
        c.execute("UPDATE letters SET status='superseded', updated_at=? WHERE id=?", (now, letter_id))
        c.execute("INSERT INTO letters (id,patient_id,encounter_id,version,status,supersedes,content,created_at,updated_at) "
                  "VALUES (?,?,?,?,?,?,?,?,?)", (lid, row["patient_id"], row["encounter_id"], row["version"] + 1, "draft",
                                                 letter_id, json.dumps(content, ensure_ascii=False, default=str), now, now))
        state.audit(user, "primary", "letter_correction_started", patient_id=row["patient_id"], outcome="draft",
                    details={"letter_id": lid, "supersedes": letter_id}, conn=c)
    return _row(lid)


def send(letter_id: str, user: dict) -> dict:
    row = _row(letter_id)
    if row["status"] != "signed":
        state.audit(user, "primary", "letter_send_blocked", patient_id=row["patient_id"], outcome="not_signed",
                    details={"letter_id": letter_id})
        raise HTTPException(409, "Only signed letters can be sent.")
    state.audit(user, "primary", "letter_sent", patient_id=row["patient_id"], outcome="sent",
                details={"letter_id": letter_id, "to": ["ELGA (simulated)", "GP (simulated)"]})
    return {"letter_id": letter_id, "sent_to": ["ELGA (simulated)", "GP (simulated)"], "at": state.now()}

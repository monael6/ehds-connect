"""Secure processing environment (Art. 73).

Each approved access application gets its own DuckDB file under var/spe/<request>.duckdb.
Only the selected patients (opted-out patients are already removed in the hdab schema) and
only the record types the request names are copied, with their patient IDs kept.
There is no download path: the API answers every download attempt with 403 and logs it.
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

from ..config import settings
from ..datastore import DataStore
from .query import Q, population_sql
from .spec import Spec

ALLOWED_TABLES = ("conditions", "medications", "observations", "encounters")


def spe_path(request_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", request_id)
    return settings.spe_dir / f"SPE-{safe}.duckdb"


def create(store: DataStore, spec: Spec, obs_codes: list[str] | None = None) -> dict:
    path = spe_path(spec.request_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    q = Q()
    cohort_sql = f"SELECT patient_id FROM ({population_sql(q, spec.population)})"
    tables = [t for t in spec.record_types if t in ALLOWED_TABLES]
    counts = {}
    with store.lock:
        con = store.con
        con.execute(f"ATTACH '{path}' AS spe")
        try:
            con.execute(f"CREATE TABLE spe.cohort AS {cohort_sql} ORDER BY patient_id", q.params)
            for t in tables:
                extra = ""
                params: list = []
                if t == "observations" and obs_codes:
                    extra = " AND (" + " OR ".join("code LIKE ?" for _ in obs_codes) + ")"
                    params = [c + "%" for c in obs_codes]
                con.execute(f"CREATE TABLE spe.{t} AS SELECT * FROM hdab.{t} "
                            f"WHERE patient_id IN (SELECT patient_id FROM spe.cohort){extra}", params)
                counts[t] = con.execute(f"SELECT count(*) FROM spe.{t}").fetchone()[0]
            n = con.execute("SELECT count(*) FROM spe.cohort").fetchone()[0]
            opted_in_spe = con.execute(
                "SELECT count(*) FROM spe.cohort c JOIN kis.patients p USING (patient_id) WHERE p.opted_out").fetchone()[0]
        finally:
            con.execute("DETACH spe")
    return {
        "id": f"SPE-{spec.request_id}",
        "patient_count": int(n),
        "record_types": tables,
        "observation_codes": obs_codes or [],
        "rows": counts,
        "patient_ids_kept": True,
        "opted_out_in_spe": int(opted_in_spe),
        "download": "blocked",
        "location": str(path.relative_to(settings.var_dir.parent)) if path.is_relative_to(settings.var_dir.parent) else str(path),
    }


def describe(request_id: str) -> dict | None:
    path = spe_path(request_id)
    if not path.exists():
        return None
    con = duckdb.connect(str(path), read_only=True)
    try:
        tables = [r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()]
        return {"id": f"SPE-{request_id}", "tables": {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables},
                "download": "blocked"}
    finally:
        con.close()


def aggregate(request_id: str) -> dict | None:
    """Example analysis inside the SPE: aggregate output only, small cells suppressed."""
    from . import smallcell
    path = spe_path(request_id)
    if not path.exists():
        return None
    con = duckdb.connect(str(path), read_only=True)
    try:
        tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        out = {"cohort_size": smallcell.safe_count(con.execute("SELECT count(*) FROM cohort").fetchone()[0])}
        if "observations" in tables:
            rows = con.execute("SELECT code, count(DISTINCT patient_id), avg(value) FROM observations GROUP BY code").fetchall()
            out["observations"] = [{"code": c, "patients": smallcell.safe_count(n), "mean": smallcell.safe_mean(m * n, n)}
                                   for c, n, m in rows]
        if "medications" in tables:
            rows = con.execute("SELECT substr(code,1,5), count(DISTINCT patient_id) FROM medications GROUP BY 1 ORDER BY 2 DESC LIMIT 10").fetchall()
            out["top_drug_classes"] = [{"atc": c, "patients": smallcell.safe_count(n)} for c, n in rows]
        return out
    finally:
        con.close()

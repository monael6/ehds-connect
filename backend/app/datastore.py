"""Loads the five Track-3 CSVs into DuckDB with separate schemas, like in the real EHDS:

  raw   the CSV files as delivered
  kis   per-hospital clinical view (primary use: treatment), canonical column names
  hdab  copy for secondary use: opted-out patients removed everywhere

Column names are detected from a list of aliases so the loader survives small
differences in the delivered files (see data/README.md).
"""
from __future__ import annotations

import threading
from pathlib import Path

import duckdb

from .config import settings

TABLES = ("patients", "conditions", "medications", "observations", "encounters")

# canonical column -> accepted source names (first match wins, case-insensitive)
ALIASES: dict[str, dict[str, list[str]]] = {
    "patients": {
        "patient_id": ["patient_id", "id", "patient", "pseudonym", "subject_id"],
        "sex": ["sex", "gender", "administrative_gender"],
        "birth_date": ["birth_date", "birthdate", "date_of_birth", "dob"],
        "birth_year": ["birth_year", "year_of_birth"],
        "age": ["age", "age_years"],
        "region": ["region", "state", "bundesland", "province", "district"],
        "data_holder": ["data_holder", "hospital", "data_holder_id", "site", "provider"],
        "opted_out": ["opted_out", "opt_out", "opt_out_secondary_use", "secondary_use_opt_out",
                      "secondary_opt_out", "optout", "opted_out_secondary_use", "ehds_opt_out"],
        "deceased_date": ["deceased_date", "death_date", "date_of_death"],
    },
    "conditions": {
        "patient_id": ["patient_id", "patient", "subject_id"],
        "code": ["icd10", "icd10_code", "icd_10", "code", "condition_code", "diagnosis_code"],
        "description": ["description", "display", "condition", "diagnosis", "label", "name"],
        "date": ["onset_date", "date", "recorded_date", "diagnosis_date", "start_date", "onset"],
        "data_holder": ["data_holder", "hospital"],
    },
    "medications": {
        "patient_id": ["patient_id", "patient", "subject_id"],
        "code": ["atc", "atc_code", "code", "medication_code"],
        "description": ["description", "display", "medication", "drug", "name", "substance"],
        "date": ["start_date", "date", "prescribed_date", "authored_on", "dispensed_date", "start"],
        "end_date": ["end_date", "stop_date", "end", "stop"],
        "data_holder": ["data_holder", "hospital"],
    },
    "observations": {
        "patient_id": ["patient_id", "patient", "subject_id"],
        "code": ["loinc", "loinc_code", "code", "observation_code"],
        "description": ["description", "display", "observation", "name", "test"],
        "value": ["value", "value_numeric", "numeric_value", "result", "value_quantity"],
        "unit": ["unit", "units", "value_unit"],
        "date": ["date", "effective_date", "observation_date", "effective_datetime", "issued"],
        "data_holder": ["data_holder", "hospital"],
    },
    "encounters": {
        "encounter_id": ["encounter_id", "id", "encounter", "stay_id", "visit_id"],
        "patient_id": ["patient_id", "patient", "subject_id"],
        "type": ["encounter_class", "class", "type", "encounter_type", "setting", "kind"],
        "start_date": ["start_date", "admission_date", "start", "admit_date", "period_start", "date"],
        "end_date": ["end_date", "discharge_date", "end", "period_end"],
        "primary_icd10": ["primary_icd10", "main_diagnosis", "primary_diagnosis", "principal_icd10"],
        "data_holder": ["data_holder", "hospital", "facility", "site"],
        "department": ["department", "ward", "specialty"],
        "length_of_stay": ["length_of_stay", "los", "los_days"],
    },
}

INPATIENT_VALUES = ("inpatient", "stationary", "stationaer", "stationär", "imp", "ip", "hospitalization",
                    "inpatient stay", "admission")


class DataStore:
    def __init__(self, data_dir: Path | None = None, reference_date: str | None = None):
        self.data_dir = Path(data_dir or settings.data_dir)
        self.con = duckdb.connect(":memory:")
        self.lock = threading.RLock()
        self.columns: dict[str, dict[str, str]] = {}
        self.loaded = False
        self.reference_date = reference_date or settings.reference_date

    # ------------------------------------------------------------------ loading
    def _csv(self, table: str) -> Path | None:
        for cand in (f"{table}.csv", f"{table}.CSV"):
            p = self.data_dir / cand
            if p.exists():
                return p
        hits = sorted(self.data_dir.glob(f"*{table}*.csv"))
        return hits[0] if hits else None

    def load(self) -> "DataStore":
        with self.lock:
            con = self.con
            for s in ("raw", "kis", "hdab"):
                con.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
            for t in TABLES:
                path = self._csv(t)
                if path is None:
                    raise FileNotFoundError(f"{t}.csv not found in {self.data_dir}")
                con.execute(f"CREATE OR REPLACE TABLE raw.{t} AS SELECT * FROM read_csv_auto(?, header=true, sample_size=-1)",
                            [str(path)])
                src = [r[0] for r in con.execute(f"DESCRIBE raw.{t}").fetchall()]
                self.columns[t] = self._map_columns(t, src)
            self._build_kis()
            self._build_hdab()
            self.loaded = True
        return self

    @staticmethod
    def _map_columns(table: str, src_cols: list[str]) -> dict[str, str]:
        lower = {c.lower(): c for c in src_cols}
        out = {}
        for canon, names in ALIASES[table].items():
            for n in names:
                if n in lower:
                    out[canon] = lower[n]
                    break
        return out

    def _col(self, table: str, canon: str, cast: str | None = None, default: str = "NULL") -> str:
        src = self.columns[table].get(canon)
        expr = f'"{src}"' if src else default
        return f"TRY_CAST({expr} AS {cast})" if cast and src else expr

    def _build_kis(self) -> None:
        c, ref = self._col, self.reference_date
        p = self.columns["patients"]
        if "birth_date" in p:
            # data/README.md: "A patient's age on that date is 2025 minus their birth year."
            age = f"year(DATE '{ref}') - year(TRY_CAST({c('patients','birth_date')} AS DATE))"
        elif "birth_year" in p:
            age = f"year(DATE '{ref}') - TRY_CAST({c('patients','birth_year')} AS INTEGER)"
        else:
            age = c("patients", "age", "INTEGER")
        opt = p.get("opted_out")
        opted = (f"""CASE WHEN lower(CAST("{opt}" AS VARCHAR)) IN ('true','1','yes','y','t','opted_out','opt_out','opted out')
                     THEN TRUE ELSE FALSE END""" if opt else "FALSE")
        # data holder of the patient: from patients, else the hospital of the first encounter
        e = self.columns["encounters"]
        if "data_holder" in p:
            dh = c("patients", "data_holder")
        elif "data_holder" in e:
            dh = f"""(SELECT first("{e['data_holder']}" ORDER BY "{e.get('start_date', e['data_holder'])}")
                      FROM raw.encounters x WHERE x."{e['patient_id']}" = r."{p['patient_id']}")"""
        else:
            dh = "NULL"
        self.con.execute(f"""
            CREATE OR REPLACE TABLE kis.patients AS
            SELECT CAST({c('patients','patient_id')} AS VARCHAR) AS patient_id,
                   {c('patients','sex')} AS sex,
                   {c('patients','birth_date', 'DATE') if 'birth_date' in p else 'NULL::DATE'} AS birth_date,
                   CAST({age} AS INTEGER) AS age,
                   {c('patients','region')} AS region,
                   {dh} AS data_holder,
                   {opted} AS opted_out,
                   {c('patients','deceased_date', 'DATE') if 'deceased_date' in p else 'NULL::DATE'} AS deceased_date
            FROM raw.patients r""")
        for t in ("conditions", "medications", "observations"):
            extra = ""
            if t == "observations":
                extra = f", TRY_CAST({c(t,'value')} AS DOUBLE) AS value, {c(t,'value')} AS value_text, {c(t,'unit')} AS unit"
            if t == "medications":
                extra = f", {c(t,'end_date','DATE')} AS end_date"
            self.con.execute(f"""
                CREATE OR REPLACE TABLE kis.{t} AS
                SELECT CAST({c(t,'patient_id')} AS VARCHAR) AS patient_id,
                       upper(trim(CAST({c(t,'code')} AS VARCHAR))) AS code,
                       {c(t,'description')} AS description,
                       {c(t,'date','DATE')} AS date,
                       {c(t,'data_holder')} AS data_holder {extra}
                FROM raw.{t}""")
        t = "encounters"
        enc_id = c(t, "encounter_id") if "encounter_id" in e else "row_number() OVER ()"
        self.con.execute(f"""
            CREATE OR REPLACE TABLE kis.encounters AS
            SELECT CAST({enc_id} AS VARCHAR) AS encounter_id,
                   CAST({c(t,'patient_id')} AS VARCHAR) AS patient_id,
                   lower(CAST({c(t,'type')} AS VARCHAR)) AS type,
                   {c(t,'start_date','DATE')} AS start_date,
                   {c(t,'end_date','DATE')} AS end_date,
                   upper(trim(CAST({c(t,'primary_icd10')} AS VARCHAR))) AS primary_icd10,
                   {c(t,'data_holder')} AS data_holder,
                   {c(t,'department')} AS department,
                   COALESCE({c(t,'length_of_stay','DOUBLE')},
                            date_diff('day', {c(t,'start_date','DATE')}, {c(t,'end_date','DATE')})) AS length_of_stay
            FROM raw.encounters""")
        self.con.execute(f"""CREATE OR REPLACE VIEW kis.encounters_x AS
            SELECT *, type IN {INPATIENT_VALUES} OR type LIKE '%inpatient%' OR type LIKE '%station%' AS inpatient
            FROM kis.encounters""")

    def _build_hdab(self) -> None:
        """Secondary-use copy. Opted-out patients are removed here, once, for every query."""
        self.con.execute("CREATE OR REPLACE TABLE hdab.patients AS SELECT * EXCLUDE (opted_out) FROM kis.patients WHERE NOT opted_out")
        for t in ("conditions", "medications", "observations", "encounters"):
            self.con.execute(f"CREATE OR REPLACE TABLE hdab.{t} AS SELECT * FROM kis.{t} WHERE patient_id IN (SELECT patient_id FROM hdab.patients)")
        self.con.execute(f"""CREATE OR REPLACE VIEW hdab.encounters_x AS
            SELECT *, type IN {INPATIENT_VALUES} OR type LIKE '%inpatient%' OR type LIKE '%station%' AS inpatient
            FROM hdab.encounters""")

    # ------------------------------------------------------------------ helpers
    def sql(self, q: str, params: list | None = None) -> list[dict]:
        with self.lock:
            cur = self.con.execute(q, params or [])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def scalar(self, q: str, params: list | None = None):
        with self.lock:
            r = self.con.execute(q, params or []).fetchone()
            return r[0] if r else None

    def code_list(self, table: str) -> list[dict]:
        """Distinct codes + descriptions. Contains no patient data, may be sent to an LLM."""
        return self.sql(f"SELECT code, any_value(description) AS description, count(DISTINCT patient_id) AS n "
                        f"FROM kis.{table} GROUP BY code ORDER BY code")

    def opted_out_count(self) -> int:
        return int(self.scalar("SELECT count(*) FROM kis.patients WHERE opted_out") or 0)

    def data_holders(self) -> list[str]:
        return [r["data_holder"] for r in self.sql(
            "SELECT DISTINCT data_holder FROM kis.encounters WHERE data_holder IS NOT NULL "
            "UNION SELECT DISTINCT data_holder FROM kis.patients WHERE data_holder IS NOT NULL ORDER BY 1")]

    def summary(self) -> dict:
        return {
            "patients": self.scalar("SELECT count(*) FROM kis.patients"),
            "opted_out": self.opted_out_count(),
            "secondary_use_patients": self.scalar("SELECT count(*) FROM hdab.patients"),
            "data_holders": self.data_holders(),
            "reference_date": self.reference_date,
            "column_mapping": self.columns,
            **{t: self.scalar(f"SELECT count(*) FROM kis.{t}") for t in TABLES if t != "patients"},
        }


_store: DataStore | None = None


def get_store() -> DataStore:
    global _store
    if _store is None:
        _store = DataStore().load()
    return _store


def set_store(store: DataStore) -> None:
    global _store
    _store = store

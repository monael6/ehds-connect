"""New requests in the style the jury announced (primary_icd10, data_holder, thresholds, new groupings).

Each expected value is computed with independently hand-written SQL on the same data,
so the test checks the generic parser + query generator, not a copy of itself.
"""
import json
from pathlib import Path

import pytest

from app.engine import smallcell
from app.engine.pipeline import evaluate

JURY = Path(__file__).parent / "jury"
REF = "DATE '2025-12-31'"
ACTIVE = f"m.start_date <= {REF} AND (m.end_date IS NULL OR m.end_date >= {REF})"


def load(rid):
    return json.loads((JURY / f"{rid}.json").read_text(encoding="utf-8"))


def raw(store, sql):
    """Hand-written SQL on the raw CSV tables (not the engine's views)."""
    return store.sql(sql)


NOT_OPTED = "p.opted_out = false"
AGE = "(2025 - year(p.birth_date))"


def test_j01_hip_fracture_stays_by_hospital(store):
    res = evaluate(load("J01"), store, persist=False)
    assert res["decision"] == "APPROVE_STATISTICAL"
    rows = raw(store, f"""SELECT e.data_holder g, count(*) n FROM raw.encounters e JOIN raw.patients p USING (patient_id)
        WHERE {NOT_OPTED} AND e.type='inpatient' AND e.primary_icd10 LIKE 'S72%'
        AND e.start_date BETWEEN DATE '2024-01-01' AND DATE '2025-12-31' GROUP BY 1""")
    for r in rows:
        assert list(res["answer"][r["g"]].values())[0] == smallcell.safe_count(r["n"])


def test_j02_poor_control_share_by_hospital(store):
    res = evaluate(load("J02"), store, persist=False)
    rows = raw(store, f"""WITH t2d AS (SELECT DISTINCT patient_id FROM raw.conditions WHERE icd10 LIKE 'E11%'),
        latest AS (SELECT patient_id, arg_max(value, date) v FROM raw.observations WHERE loinc='4548-4' GROUP BY 1)
        SELECT p.data_holder g, count(*) den, count(*) FILTER (WHERE l.v > 8) num
        FROM raw.patients p JOIN t2d USING (patient_id) LEFT JOIN latest l USING (patient_id)
        WHERE {NOT_OPTED} AND {AGE} >= 18 GROUP BY 1""")
    for r in rows:
        vals = list(res["answer"][r["g"]].values())
        assert vals == [smallcell.safe_count(r["den"]), smallcell.safe_count(r["num"]),
                        smallcell.safe_percentage(r["num"], r["den"])]


def test_j03_two_dimensions_all_groups_shown(store):
    res = evaluate(load("J03"), store, persist=False)
    rows = raw(store, f"""SELECT p.sex || ' / ' || p.region g, count(DISTINCT p.patient_id) n FROM raw.patients p
        JOIN raw.conditions c USING (patient_id) WHERE {NOT_OPTED} AND c.icd10 LIKE 'I50%' GROUP BY 1""")
    assert len(res["answer"]) == 18  # 2 sexes x 9 regions, empty ones too
    for r in rows:
        assert list(res["answer"][r["g"]].values())[0] == smallcell.safe_count(r["n"])


def test_j04_mean_egfr_by_custom_bands(store):
    res = evaluate(load("J04"), store, persist=False)
    rows = raw(store, f"""WITH latest AS (SELECT patient_id, arg_max(value, date) v FROM raw.observations
                                       WHERE loinc='62238-1' GROUP BY 1)
        SELECT CASE WHEN {AGE} BETWEEN 18 AND 49 THEN '18-49' WHEN {AGE} BETWEEN 50 AND 64 THEN '50-64'
                    WHEN {AGE} BETWEEN 65 AND 79 THEN '65-79' ELSE '80+' END g, count(*) n, sum(l.v) s
        FROM raw.patients p JOIN latest l USING (patient_id)
        WHERE {NOT_OPTED} AND {AGE} >= 18 AND p.patient_id IN (SELECT patient_id FROM raw.conditions WHERE icd10 LIKE 'E11%')
        GROUP BY 1""")
    for r in rows:
        assert list(res["answer"][r["g"]].values()) == [smallcell.safe_count(r["n"]), smallcell.safe_mean(r["s"], r["n"])]


def test_j05_share_active_drug(store):
    res = evaluate(load("J05"), store, persist=False)
    rows = raw(store, f"""SELECT p.data_holder g, count(*) den,
        count(*) FILTER (WHERE p.patient_id IN (SELECT patient_id FROM raw.medications m WHERE atc LIKE 'R03BB04%' AND {ACTIVE})) num
        FROM raw.patients p WHERE {NOT_OPTED} AND p.patient_id IN (SELECT patient_id FROM raw.conditions WHERE icd10 LIKE 'J44%')
        GROUP BY 1""")
    for r in rows:
        assert list(res["answer"][r["g"]].values()) == [smallcell.safe_count(r["den"]), smallcell.safe_percentage(r["num"], r["den"])]


def test_j06_sales_representatives_rejected(store):
    res = evaluate(load("J06"), store, persist=False)
    assert res["decision"] == "REJECT" and res["articles"] == [54] and res["answer"] is None


def test_j07_spe_cohort(store):
    res = evaluate(load("J07"), store, persist=False)
    n = raw(store, f"""SELECT count(*) n FROM raw.patients p WHERE {NOT_OPTED} AND {AGE} >= 18
        AND p.patient_id IN (SELECT patient_id FROM raw.conditions WHERE icd10 LIKE 'I63%')""")[0]["n"]
    assert res["decision"] == "APPROVE_SPE" and res["spe"]["patient_count"] == n
    assert set(res["spe"]["record_types"]) == {"conditions", "encounters"}
    assert res["spe"]["opted_out_in_spe"] == 0


def test_j08_emergency_visits(store):
    res = evaluate(load("J08"), store, persist=False)
    rows = raw(store, f"""SELECT e.data_holder g, count(*) n FROM raw.encounters e JOIN raw.patients p USING (patient_id)
        WHERE {NOT_OPTED} AND e.type='emergency' AND year(e.start_date) = 2025 GROUP BY 1""")
    for r in rows:
        assert list(res["answer"][r["g"]].values())[0] == smallcell.safe_count(r["n"])


def test_j09_threshold_and_share(store):
    res = evaluate(load("J09"), store, persist=False)
    rows = raw(store, f"""WITH latest AS (SELECT patient_id, arg_max(value, date) v FROM raw.observations WHERE loinc='39156-5' GROUP BY 1)
        SELECT p.region g, count(*) den, count(*) FILTER (WHERE l.v >= 30) num FROM raw.patients p LEFT JOIN latest l USING (patient_id)
        WHERE {NOT_OPTED} AND p.sex='female' AND {AGE} >= 18
        AND p.patient_id IN (SELECT patient_id FROM raw.conditions WHERE icd10 LIKE 'F32%') GROUP BY 1""")
    for r in rows:
        assert list(res["answer"][r["g"]].values()) == [smallcell.safe_count(r["den"]), smallcell.safe_count(r["num"]),
                                                         smallcell.safe_percentage(r["num"], r["den"])]

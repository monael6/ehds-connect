"""Measures the five Track-3 metrics on requests/*.json against requests/expected.json.

    python scripts/evaluate.py            # 10 official requests, 3 runs each
    python scripts/evaluate.py --json     # machine-readable output

Writes var/metrics.json, which the API serves at GET /api/metrics.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import state  # noqa: E402
from app.config import settings  # noqa: E402
from app.datastore import DataStore  # noqa: E402
from app.engine import smallcell  # noqa: E402
from app.engine.pipeline import applicant_view, evaluate  # noqa: E402

OPTIONAL_ARTICLES = {"67", "71"}
PATIENT_ID = re.compile(r"\bp-[0-9a-f]{8}\b")


def norm_label(s: str) -> str:
    return re.sub(r"\s+", "", str(s)).lower()


def values_equal(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(float(a) - float(b)) < 1e-9
    return a == b


def numbers_correct(expected, answer) -> tuple[bool, list[str]]:
    """Every expected value must appear under its group. Layout and key names do not matter."""
    problems = []
    if isinstance(expected, dict) and all(not isinstance(v, dict) for v in expected.values()):
        flat_expected = {"": expected}
    else:
        flat_expected = expected
    ans = answer or {}
    ans_by_group = {norm_label(k): v for k, v in ans.items()} if isinstance(ans, dict) else {}
    for group, exp_vals in flat_expected.items():
        if group == "":
            for k, v in exp_vals.items():
                g = ans_by_group.get(norm_label(k))
                cand = [g] if not isinstance(g, dict) else list(g.values())
                if g is None:
                    cand = list(ans.values()) if not any(isinstance(x, dict) for x in ans.values()) else []
                if not any(values_equal(v, c) for c in cand):
                    problems.append(f"{k}: expected {v}, got {g}")
            continue
        got = ans_by_group.get(norm_label(group))
        if got is None:
            problems.append(f"group {group} missing")
            continue
        got_vals = list(got.values()) if isinstance(got, dict) else [got]
        exp_list = exp_vals.values() if isinstance(exp_vals, dict) else [exp_vals]
        for v in exp_list:
            if not any(values_equal(v, g) for g in got_vals):
                problems.append(f"{group}: expected {v} in {got_vals}")
    return not problems, problems


def leaks(view: dict, result: dict, store: DataStore) -> list[str]:
    out = []
    text = json.dumps(view, ensure_ascii=False, default=str)
    if PATIENT_ID.search(text):
        out.append("patient ID in applicant view")
    if result["decision"] == "APPROVE_STATISTICAL":
        for m in result.get("statistics", []):
            for g in m["groups"]:
                for key in ("value", "numerator", "denominator", "n"):
                    v = g.get(key)
                    if v is None:
                        continue
                    if isinstance(v, int) and not isinstance(v, bool) and v < smallcell.THRESHOLD:
                        out.append(f"{m['id']} {g['group']}: count {v} below 10")
                if m["kind"] in ("percentage", "mean") and isinstance(g.get("value"), float):
                    base = [g.get(k) for k in ("numerator", "denominator", "n") if k in g]
                    if any(b == smallcell.LESS_THAN for b in base):
                        out.append(f"{m['id']} {g['group']}: unsuppressed value from a small group")
    if result.get("spe") and result["spe"].get("opted_out_in_spe"):
        out.append("opted-out patients inside the SPE")
    if store.scalar("SELECT count(*) FROM hdab.patients p JOIN kis.patients k USING (patient_id) WHERE k.opted_out"):
        out.append("opted-out patients in the secondary-use schema")
    return out


def stable(result: dict) -> str:
    keep = {k: result.get(k) for k in ("decision", "articles", "answer")}
    if result.get("spe"):
        keep["spe"] = {k: result["spe"][k] for k in ("patient_count", "record_types", "rows")}
    return json.dumps(keep, sort_keys=True, ensure_ascii=False, default=str)


def run(requests_dir: Path, runs: int = 3, store: DataStore | None = None) -> dict:
    store = store or DataStore().load()
    state.connect(":memory:")
    expected = json.loads((requests_dir / "expected.json").read_text(encoding="utf-8"))
    rows = []
    for path in sorted(requests_dir.glob("R*.json")):
        req = json.loads(path.read_text(encoding="utf-8"))
        rid = req.get("id", path.stem)
        exp = expected.get(rid)
        outs, times = [], []
        for _ in range(runs):
            t0 = time.perf_counter()
            res = evaluate(req, store, persist=True)
            times.append(time.perf_counter() - t0)
            outs.append(res)
        res = outs[0]
        view = applicant_view(res)
        row = {"id": rid, "decision": res["decision"], "articles": [str(a) for a in res["articles"]],
               "consistent": len({stable(o) for o in outs}) == 1, "seconds": round(max(times), 3),
               "leaks": leaks(view, res, store)}
        if exp:
            got_art = set(row["articles"]) - OPTIONAL_ARTICLES
            row["decision_correct"] = res["decision"] == exp["decision"] and got_art == set(exp["articles"]) - OPTIONAL_ARTICLES
            if exp.get("answer") is not None:
                ok, problems = numbers_correct(exp["answer"], res.get("answer"))
                row["numbers_correct"], row["number_problems"] = ok, problems
        rows.append(row)

    with_exp = [r for r in rows if "decision_correct" in r]
    numeric = [r for r in rows if "numbers_correct" in r]
    summary = {
        "correct_decisions": f"{sum(r['decision_correct'] for r in with_exp)} of {len(with_exp)}",
        "correct_numbers": f"{sum(r['numbers_correct'] for r in numeric)} of {len(numeric)}",
        "privacy_leaks": sum(1 for r in rows if r["leaks"]),
        "consistency": f"{sum(r['consistent'] for r in rows)} of {len(rows)}",
        "slowest_seconds": max(r["seconds"] for r in rows) if rows else None,
        "runs_per_request": runs,
    }
    return {"summary": summary, "requests": rows, "measured_at": state.now()}


def main() -> None:
    req_dir = Path(sys.argv[sys.argv.index("--requests") + 1]) if "--requests" in sys.argv else settings.requests_dir
    report = run(req_dir)
    settings.var_dir.mkdir(parents=True, exist_ok=True)
    if req_dir == settings.requests_dir:
        (settings.var_dir / "metrics.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    print(f"{'Request':8} {'Decision':20} {'Dec ok':7} {'Nums ok':8} {'Leaks':6} {'Consist':8} {'Time s':6}")
    for r in report["requests"]:
        print(f"{r['id']:8} {r['decision']:20} {str(r.get('decision_correct', '-')):7} "
              f"{str(r.get('numbers_correct', '-')):8} {len(r['leaks']):<6} {str(r['consistent']):8} {r['seconds']:<6}")
        for p in r.get("number_problems", []) + r["leaks"]:
            print("   !", p)
    print()
    for k, v in report["summary"].items():
        print(f"{k:20} {v}")


if __name__ == "__main__":
    main()

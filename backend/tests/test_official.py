"""The 10 official requests: all five Track-3 metrics."""
from pathlib import Path

from scripts.evaluate import run

REQ = Path(__file__).resolve().parent.parent / "requests"


def test_track3_metrics(store):
    report = run(REQ, runs=3, store=store)
    s = report["summary"]
    assert s["correct_decisions"] == "10 of 10"
    assert s["correct_numbers"] == "6 of 6"
    assert s["privacy_leaks"] == 0
    assert s["consistency"] == "10 of 10"
    assert s["slowest_seconds"] < 60

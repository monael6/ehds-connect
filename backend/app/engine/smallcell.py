"""Small-cell rule (Track 3 task, enforced on every statistical answer).

- every requested group is shown, even if empty
- counts below 10 (including 0) are shown as "<10"
- a percentage is "suppressed" if its numerator or denominator is below 10
- a mean is "suppressed" if it is based on fewer than 10 patients
- values are rounded to one decimal, halves up
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

THRESHOLD = 10
LESS_THAN = "<10"
SUPPRESSED = "suppressed"


def round_half_up(value: float | Decimal, places: int = 1) -> float:
    q = Decimal(1).scaleb(-places)
    # str() avoids binary float artefacts such as 2.675 -> 2.67499999
    return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def safe_count(n: int) -> int | str:
    return LESS_THAN if n < THRESHOLD else int(n)


def safe_percentage(numerator: int, denominator: int) -> float | str:
    if numerator < THRESHOLD or denominator < THRESHOLD:
        return SUPPRESSED
    return round_half_up(Decimal(numerator) * 100 / Decimal(denominator))


def safe_mean(total: float | None, n: int) -> float | str:
    if n < THRESHOLD or total is None:
        return SUPPRESSED
    return round_half_up(Decimal(str(total)) / Decimal(n))


def is_safe_value(v) -> bool:
    """True if a published cell can not reveal a small group. Used by the leak check."""
    if v in (LESS_THAN, SUPPRESSED):
        return True
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return v >= THRESHOLD
    return isinstance(v, float)

from app.engine import smallcell as sc


def test_counts_below_ten_including_zero():
    assert sc.safe_count(0) == "<10"
    assert sc.safe_count(9) == "<10"
    assert sc.safe_count(10) == 10


def test_percentage_suppressed_when_numerator_or_denominator_small():
    assert sc.safe_percentage(9, 100) == "suppressed"
    assert sc.safe_percentage(9, 9) == "suppressed"
    assert sc.safe_percentage(10, 200) == 5.0


def test_mean_suppressed_below_ten_patients():
    assert sc.safe_mean(90.0, 9) == "suppressed"
    assert sc.safe_mean(100.0, 10) == 10.0


def test_round_half_up():
    assert sc.round_half_up(0.05) == 0.1
    assert sc.round_half_up(2.25) == 2.3
    assert sc.round_half_up(2.675, 2) == 2.68
    assert sc.safe_percentage(37, 154) == 24.0  # 24.0259...

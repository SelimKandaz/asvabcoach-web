from app.scoring.afqt_estimator import (
    calculate_afqt_raw,
    calculate_percentile_estimate,
    calculate_percentile_range,
    calculate_ve_estimate,
)
from app.scoring.irt import normal_cdf, probability_correct, theta_to_standard_score, update_theta
from app.scoring.line_scores import calculate_gt_estimate


def test_probability_correct_increases_with_theta() -> None:
    low = probability_correct(theta=-1.0, a=1.0, b=0.0, c=0.25)
    high = probability_correct(theta=1.0, a=1.0, b=0.0, c=0.25)
    assert high > low


def test_update_theta_moves_up_for_correct_answer() -> None:
    updated = update_theta(theta=0.0, is_correct=True, a=1.0, b=0.0, c=0.25)
    assert updated > 0.0


def test_update_theta_moves_down_for_wrong_answer() -> None:
    updated = update_theta(theta=0.0, is_correct=False, a=1.0, b=0.0, c=0.25)
    assert updated < 0.0


def test_theta_to_standard_score_maps_zero_to_fifty() -> None:
    assert theta_to_standard_score(0.0) == 50.0


def test_normal_cdf_midpoint() -> None:
    assert round(normal_cdf(0.0), 4) == 0.5


def test_afqt_helpers() -> None:
    ve = calculate_ve_estimate(55.0, 50.0)
    raw = calculate_afqt_raw(52.0, 54.0, ve)
    percentile = calculate_percentile_estimate(raw)
    percentile_range = calculate_percentile_range(percentile)
    gt = calculate_gt_estimate(52.0, 55.0, 50.0)

    assert ve is not None
    assert raw is not None
    assert percentile is not None
    assert percentile_range is not None
    assert gt is not None

from __future__ import annotations

from math import ceil

from app.scoring.irt import normal_cdf, theta_to_standard_score


STANDARD_SECTION_ORDER = ["GS", "AR", "WK", "PC", "MK", "EI", "AI", "AS", "SI", "MC", "AO"]
DIFFICULTY_WEIGHTS = {
    1: 0.65,
    2: 1.0,
    3: 1.35,
    4: 1.65,
    5: 1.85,
}


def calculate_standard_scores_from_theta(theta_map: dict[str, float]) -> dict[str, float]:
    scores = {section: round(theta_to_standard_score(theta), 2) for section, theta in theta_map.items()}
    if scores.get("WK") is not None and scores.get("PC") is not None:
        scores["VE"] = calculate_ve_estimate(scores.get("WK"), scores.get("PC"))
    if scores.get("AI") is not None or scores.get("SI") is not None:
        scores["AS_COMPOSITE"] = calculate_as_estimate(scores.get("AI"), scores.get("SI"))
    return scores


def calculate_section_standard_scores(section_scores: dict[str, float]) -> dict[str, float]:
    return {section: round(float(score), 2) for section, score in section_scores.items()}


def calculate_ve_estimate(wk_std: float | None, pc_std: float | None, method: str = "weighted_average") -> float | None:
    if wk_std is None and pc_std is None:
        return None
    if wk_std is None:
        return round(float(pc_std), 2) if pc_std is not None else None
    if pc_std is None:
        return round(float(wk_std), 2)
    if method == "weighted_average":
        return round((wk_std * 0.67) + (pc_std * 0.33), 2)
    return round((wk_std + pc_std) / 2.0, 2)


def calculate_as_estimate(ai_std: float | None, si_std: float | None) -> float | None:
    if ai_std is None and si_std is None:
        return None
    if ai_std is None:
        return round(float(si_std), 2) if si_std is not None else None
    if si_std is None:
        return round(float(ai_std), 2)
    return round((ai_std + si_std) / 2.0, 2)


def calculate_afqt_raw(ar_std: float | None, mk_std: float | None, ve_std: float | None) -> float | None:
    if ar_std is None or mk_std is None or ve_std is None:
        return None
    return round(ar_std + mk_std + (2.0 * ve_std), 2)


def calculate_percentile_estimate(
    afqt_raw_estimate: float | None,
    composite_mean: float = 200.0,
    composite_sd: float = 40.0,
) -> float | None:
    if afqt_raw_estimate is None:
        return None
    z_score = (afqt_raw_estimate - composite_mean) / composite_sd
    percentile = normal_cdf(z_score) * 100.0
    return round(max(1.0, min(99.0, percentile)), 2)


def calculate_percentile_range(percentile_estimate: float | None, band_size: int = 5) -> str | None:
    if percentile_estimate is None:
        return None
    lower = max(1, int(ceil(percentile_estimate - band_size)))
    upper = min(99, int(ceil(percentile_estimate + band_size)))
    return f"{lower}-{upper}"


def calculate_afqt_confidence(
    *,
    answered_sections: int,
    scored_questions: int,
    excluded_bad_questions: int,
    full_blueprint_complete: bool,
) -> str:
    if not full_blueprint_complete or scored_questions < 30 or answered_sections < 3:
        return "low"
    if excluded_bad_questions > 20 or scored_questions < 55:
        return "medium"
    return "high"


def calculate_scored_question_total(section_counts: dict[str, int]) -> int:
    return int(sum(section_counts.values()))


def difficulty_weight(level: int) -> float:
    return DIFFICULTY_WEIGHTS.get(max(1, min(5, int(level))), 1.0)


def calculate_weighted_accuracy(answer_rows: list[tuple[int, bool]]) -> float | None:
    if not answer_rows:
        return None
    weighted_total = 0.0
    weighted_correct = 0.0
    for difficulty_level, is_correct in answer_rows:
        weight = difficulty_weight(difficulty_level)
        weighted_total += weight
        if is_correct:
            weighted_correct += weight
    if weighted_total <= 0:
        return None
    return round(weighted_correct / weighted_total, 4)


def calculate_readiness_score(
    *,
    weighted_accuracy: float,
    coverage_factor: float,
    difficulty_factor: float,
    consistency_factor: float,
    time_factor: float,
) -> float:
    readiness = 100.0 * weighted_accuracy * coverage_factor * difficulty_factor * consistency_factor * time_factor
    return round(max(0.0, min(100.0, readiness)), 2)


def calculate_readiness_confidence(
    *,
    readiness_score: float,
    coverage_factor: float,
    consistency_factor: float,
    time_factor: float,
) -> str:
    if readiness_score >= 80 and coverage_factor >= 0.95 and consistency_factor >= 0.95 and time_factor >= 0.95:
        return "high"
    if readiness_score >= 60 and coverage_factor >= 0.75:
        return "medium"
    return "low"

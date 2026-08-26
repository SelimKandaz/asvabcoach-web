from __future__ import annotations


def clamp_difficulty_level(level: int) -> int:
    return max(1, min(5, int(level)))


def difficulty_irt_b(level: int) -> float:
    return {
        1: -2.0,
        2: -1.0,
        3: 0.0,
        4: 1.0,
        5: 2.0,
    }.get(clamp_difficulty_level(level), 0.0)


def rate_to_difficulty_level(correct_rate: float) -> int:
    if correct_rate >= 0.85:
        return 1
    if correct_rate >= 0.70:
        return 2
    if correct_rate >= 0.50:
        return 3
    if correct_rate >= 0.35:
        return 4
    return 5


def complexity_to_difficulty_level(complexity_score: int | None, *, fallback_level: int) -> int:
    if complexity_score is None:
        return clamp_difficulty_level(fallback_level)
    if complexity_score <= 25:
        return 1
    if complexity_score <= 43:
        return 2
    if complexity_score <= 63:
        return 3
    if complexity_score <= 81:
        return 4
    return 5


def resolved_difficulty_level(question: object) -> int:
    return clamp_difficulty_level(getattr(question, "difficulty_level", 3))


def resolved_irt_b(question: object) -> float:
    calibrated_irt_b = getattr(question, "calibrated_irt_b", None)
    if calibrated_irt_b is not None:
        return float(calibrated_irt_b)
    irt_b = getattr(question, "irt_b", None)
    if irt_b is not None:
        return float(irt_b)
    return difficulty_irt_b(resolved_difficulty_level(question))


def infer_difficulty_level(
    *,
    base_level: int,
    observed_correct_rate: float | None = None,
    observed_sample_size: int = 0,
    complexity_score: int | None = None,
    response_correct_rate: float | None = None,
    response_count: int = 0,
    prior_level: int | None = None,
) -> tuple[int, float]:
    current_level = clamp_difficulty_level(prior_level or base_level)
    evidence: list[tuple[int, float]] = [(current_level, 0.25)]
    evidence_strength = 0.0

    if observed_correct_rate is not None:
        if observed_sample_size >= 10:
            observed_weight = 0.45
        elif observed_sample_size >= 5:
            observed_weight = 0.35
        elif observed_sample_size >= 1:
            observed_weight = 0.20
        else:
            observed_weight = 0.35 if complexity_score is not None else 0.20
        observed_level = rate_to_difficulty_level(max(0.05, min(0.95, float(observed_correct_rate))))
        evidence.append((observed_level, observed_weight))
        evidence_strength += observed_weight

    if complexity_score is not None:
        complexity_level = complexity_to_difficulty_level(complexity_score, fallback_level=current_level)
        evidence.append((complexity_level, 0.35))
        evidence_strength += 0.35

    if response_correct_rate is not None and response_count >= 3:
        if response_count >= 10:
            response_weight = 0.45
        elif response_count >= 5:
            response_weight = 0.35
        else:
            response_weight = 0.20
        response_level = rate_to_difficulty_level(max(0.05, min(0.95, float(response_correct_rate))))
        evidence.append((response_level, response_weight))
        evidence_strength += response_weight

    if evidence_strength < 0.35:
        return current_level, round(evidence_strength, 2)

    blended_level = round(
        sum(level * weight for level, weight in evidence) / sum(weight for _, weight in evidence)
    )
    return clamp_difficulty_level(blended_level), round(evidence_strength, 2)

from math import erf, exp, sqrt


def clamp_theta(theta: float, minimum: float = -3.0, maximum: float = 3.0) -> float:
    return max(minimum, min(maximum, theta))


def probability_correct(theta: float, a: float, b: float, c: float) -> float:
    return c + (1.0 - c) / (1.0 + exp(-1.7 * a * (theta - b)))


def update_theta(theta: float, is_correct: bool, a: float, b: float, c: float, learning_rate: float = 0.45) -> float:
    expected_probability = probability_correct(theta=theta, a=a, b=b, c=c)
    if is_correct:
        updated = theta + learning_rate * (1.0 - expected_probability) * a
    else:
        updated = theta - learning_rate * expected_probability * a
    return clamp_theta(updated)


def theta_to_standard_score(theta: float) -> float:
    score = 50.0 + clamp_theta(theta) * 10.0
    return max(20.0, min(80.0, round(score, 2)))


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))

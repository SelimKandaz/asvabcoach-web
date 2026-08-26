from __future__ import annotations

from app.scoring.afqt_estimator import calculate_as_estimate
from app.scoring.irt import normal_cdf


def raw_to_1_99(raw_score: float | None, mean: float = 200.0, sd: float = 40.0) -> float | None:
    if raw_score is None:
        return None
    z_score = (raw_score - mean) / sd
    return round(max(1.0, min(99.0, (normal_cdf(z_score) * 98.0) + 1.0)), 2)


def calculate_gt_estimate(ar_standard: float | None, wk_standard: float | None, pc_standard: float | None) -> float | None:
    ve_standard = calculate_as_estimate(wk_standard, pc_standard)
    if ar_standard is None or ve_standard is None:
        return None
    return round(ar_standard + ve_standard, 2)


def calculate_army_composites(scores: dict[str, float | None]) -> dict[str, float | None]:
    ve = scores.get("VE")
    ar = scores.get("AR")
    mk = scores.get("MK")
    ai = scores.get("AI")
    si = scores.get("SI")
    as_score = scores.get("AS") if scores.get("AS") is not None else scores.get("AS_COMPOSITE")
    mc = scores.get("MC")
    gs = scores.get("GS")
    ei = scores.get("EI")
    ao = scores.get("AO")
    return {
        "GT": _sum([ve, ar]),
        "CL": _sum([ve, ar, mk]),
        "CO": _sum([ve, as_score, mc]),
        "EL": _sum([gs, ar, mk, ei]),
        "FA": _sum([ar, mk, mc]),
        "GM": _sum([gs, as_score, mk, ei]),
        "MM": _sum([as_score, mc, ei]),
        "OF": _sum([ve, as_score, mc]),
        "SC": _sum([ve, ar, as_score, mc]),
        "ST": _sum([gs, ve, mk, mc]),
    }


def calculate_airforce_composites(scores: dict[str, float | None]) -> dict[str, float | None]:
    ar = scores.get("AR")
    mk = scores.get("MK")
    ve = scores.get("VE")
    ai = scores.get("AI")
    si = scores.get("SI")
    as_score = scores.get("AS") if scores.get("AS") is not None else scores.get("AS_COMPOSITE")
    mc = scores.get("MC")
    ei = scores.get("EI")
    gs = scores.get("GS")
    components = {
        "M": _sum([ar, as_score, mc, ve]),
        "A": _sum([mk, ve]),
        "G": _sum([ar, ve]),
        "E": _sum([ar, ei, gs, mk]),
    }
    return {key: raw_to_1_99(value) for key, value in components.items()}


def calculate_navy_composites(scores: dict[str, float | None]) -> dict[str, float | None]:
    ar = scores.get("AR")
    mk = scores.get("MK")
    ve = scores.get("VE")
    ai = scores.get("AI")
    si = scores.get("SI")
    as_score = scores.get("AS") if scores.get("AS") is not None else scores.get("AS_COMPOSITE")
    mc = scores.get("MC")
    gs = scores.get("GS")
    ei = scores.get("EI")
    ao = scores.get("AO")
    return {
        "GT": _sum([ve, ar]),
        "EL": _sum([gs, ar, mk, ei]),
        "BEE": _sum([ar, gs, mk, mk]),
        "ENG": _sum([as_score, mk]),
        "MEC": _sum([ar, as_score, mc]),
        "MEC2": _sum([ao, ar, mc]),
        "NUC": _sum([ar, mc, mk, ve]),
        "OPS": _sum([ar, mk, ao]),
        "HM": _sum([gs, mk, ve]),
        "ADM": _sum([mk, ve]),
    }


def calculate_marine_composites(scores: dict[str, float | None]) -> dict[str, float | None]:
    ve = scores.get("VE")
    ar = scores.get("AR")
    mk = scores.get("MK")
    gs = scores.get("GS")
    ei = scores.get("EI")
    ai = scores.get("AI")
    si = scores.get("SI")
    as_score = scores.get("AS") if scores.get("AS") is not None else scores.get("AS_COMPOSITE")
    mc = scores.get("MC")
    return {
        "MM": _sum([mc, ei, as_score]),
        "GT": _sum([ve, ar]),
        "EL": _sum([gs, ar, mk, ei]),
        "CL": _sum([ve, mk]),
    }


def _sum(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return round(sum(valid), 2)

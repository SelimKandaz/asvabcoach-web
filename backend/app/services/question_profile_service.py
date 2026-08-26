from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.data_import.normalize_questions import normalize_skill_tag, normalize_text_for_hash
from app.services.difficulty_service import clamp_difficulty_level


TEMPLATE_FAMILY_LEVELS = {
    "conceptual_definition": 1,
    "direct_formula": 2,
    "formula_rearrangement": 3,
    "multi_step_formula": 4,
    "diagnosis_scenario": 3,
    "diagram_interpretation": 3,
    "combined_concepts": 4,
}

CONCEPT_RULES: list[tuple[str, dict[str, object]]] = [
    ("synonym", {"template_family": "conceptual_definition", "reasoning_steps": 1, "difficulty_level": 1}),
    ("ac_abbreviation", {"template_family": "conceptual_definition", "reasoning_steps": 1, "difficulty_level": 1}),
    ("ohmmeter_measures_resistance", {"template_family": "conceptual_definition", "reasoning_steps": 1, "difficulty_level": 1}),
    ("travel_speed_time", {"template_family": "direct_formula", "reasoning_steps": 1, "difficulty_level": 1, "formula_stack": ["distance = rate x time"]}),
    ("average_basic", {"template_family": "direct_formula", "reasoning_steps": 1, "difficulty_level": 1, "formula_stack": ["average = total / count"]}),
    ("rate_time_distance", {"template_family": "direct_formula", "reasoning_steps": 1, "difficulty_level": 2, "formula_stack": ["distance = rate x time"]}),
    ("fraction_part", {"template_family": "direct_formula", "reasoning_steps": 1, "difficulty_level": 2}),
    ("percent_change", {"template_family": "direct_formula", "reasoning_steps": 2, "difficulty_level": 2}),
    ("linear_equation", {"template_family": "formula_rearrangement", "reasoning_steps": 2, "difficulty_level": 2}),
    ("perimeter", {"template_family": "direct_formula", "reasoning_steps": 2, "difficulty_level": 2, "formula_stack": ["perimeter = 2(length + width)"]}),
    ("order_of_operations", {"template_family": "combined_concepts", "reasoning_steps": 2, "difficulty_level": 3}),
    ("density", {"template_family": "direct_formula", "reasoning_steps": 2, "difficulty_level": 3, "formula_stack": ["density = mass / volume"]}),
    ("ohms_law", {"template_family": "direct_formula", "reasoning_steps": 1, "difficulty_level": 2, "formula_stack": ["I = V / R"]}),
    ("parallel_resistance", {"template_family": "multi_step_formula", "reasoning_steps": 3, "difficulty_level": 4}),
    ("series_resistance", {"template_family": "direct_formula", "reasoning_steps": 2, "difficulty_level": 2}),
    ("gear", {"template_family": "diagram_interpretation", "reasoning_steps": 2, "difficulty_level": 2}),
    ("lever", {"template_family": "combined_concepts", "reasoning_steps": 3, "difficulty_level": 4}),
    ("torque", {"template_family": "direct_formula", "reasoning_steps": 2, "difficulty_level": 3, "formula_stack": ["torque = force x distance"]}),
    ("rotation", {"template_family": "diagram_interpretation", "reasoning_steps": 2, "difficulty_level": 3}),
    ("mirror", {"template_family": "diagram_interpretation", "reasoning_steps": 2, "difficulty_level": 3}),
    ("3d_orientation", {"template_family": "diagram_interpretation", "reasoning_steps": 3, "difficulty_level": 4}),
    ("main_idea", {"template_family": "diagnosis_scenario", "reasoning_steps": 2, "difficulty_level": 2}),
    ("inference", {"template_family": "diagnosis_scenario", "reasoning_steps": 2, "difficulty_level": 3}),
    ("battery", {"template_family": "conceptual_definition", "reasoning_steps": 1, "difficulty_level": 1}),
    ("brake", {"template_family": "conceptual_definition", "reasoning_steps": 1, "difficulty_level": 1}),
    ("engine", {"template_family": "conceptual_definition", "reasoning_steps": 1, "difficulty_level": 2}),
    ("tool", {"template_family": "conceptual_definition", "reasoning_steps": 1, "difficulty_level": 2}),
    ("charging_system", {"template_family": "diagnosis_scenario", "reasoning_steps": 3, "difficulty_level": 4}),
    ("starter_system", {"template_family": "diagnosis_scenario", "reasoning_steps": 3, "difficulty_level": 4}),
    ("cooling_system", {"template_family": "diagnosis_scenario", "reasoning_steps": 3, "difficulty_level": 4}),
    ("fuel_system", {"template_family": "diagnosis_scenario", "reasoning_steps": 3, "difficulty_level": 4}),
    ("brake_hydraulics", {"template_family": "diagnosis_scenario", "reasoning_steps": 3, "difficulty_level": 4}),
    ("engine_diagnostics", {"template_family": "combined_concepts", "reasoning_steps": 4, "difficulty_level": 5}),
    ("electrical_diagnostics", {"template_family": "combined_concepts", "reasoning_steps": 4, "difficulty_level": 5}),
    ("transmission_symptom", {"template_family": "combined_concepts", "reasoning_steps": 4, "difficulty_level": 5}),
    ("steering_alignment", {"template_family": "combined_concepts", "reasoning_steps": 4, "difficulty_level": 4}),
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "for",
    "from",
    "how",
    "if",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "which",
}


@dataclass(slots=True)
class QuestionProfile:
    concept_tag: str
    template_family: str
    variant_signature: str
    reasoning_steps: int
    formula_stack: list[str] | None
    concept_stack: list[str] | None
    trap_type: str | None
    requires_figure: bool
    figure_quality_status: str
    license_status: str
    source_profile: str | None
    recommended_difficulty_level: int
    derived_complexity_score: int


def _clean_tag(value: object, *, fallback: str) -> str:
    text = normalize_skill_tag(value)
    if text in {"", "general", "unknown", "none", "null"}:
        text = ""
    return text or fallback


def _clean_variant_signature(value: object, *, fallback: str) -> str:
    raw = str(value).strip() if value is not None else ""
    lowered = raw.lower()
    if lowered in {"", "unknown", "general", "none", "null"} or ":general:" in lowered or ":unknown:" in lowered:
        raw = ""
    if not raw:
        raw = fallback
    raw = raw.lower()
    raw = re.sub(r"[^a-z0-9:_-]+", "_", raw)
    raw = re.sub(r"_+", "_", raw)
    return raw.strip("_") or fallback


def _parse_jsonish_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or None
    if isinstance(value, tuple):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("["):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            cleaned = [str(item).strip() for item in payload if str(item).strip()]
            return cleaned or None
    cleaned = [part.strip() for part in re.split(r"[|,;/]+", text) if part.strip()]
    return cleaned or None


def _as_optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _has_numeric_work(text: str) -> bool:
    return bool(re.search(r"\d", text)) or any(
        token in text
        for token in ("miles", "hours", "volts", "ohms", "amps", "meters", "degrees", "percent", "ratio")
    )


def _concept_rule(concept_tag: str, skill_tag: str) -> dict[str, object]:
    haystack = f"{concept_tag} {skill_tag}"
    best_payload: dict[str, object] = {}
    best_needle_length = -1
    for needle, payload in CONCEPT_RULES:
        if needle in haystack and len(needle) > best_needle_length:
            best_payload = payload
            best_needle_length = len(needle)
    return best_payload


def _infer_requires_figure(question_text: str, has_figure: bool, figure_type: str | None) -> bool:
    if has_figure or bool((figure_type or "").strip()):
        return True
    text = normalize_text_for_hash(question_text)
    return any(token in text for token in ("figure", "diagram", "shown", "circuit", "gear", "shape", "mirror"))


def _infer_template_family(
    *,
    section: str,
    skill_tag: str,
    concept_tag: str,
    question_text: str,
    requires_figure: bool,
) -> str:
    text = normalize_text_for_hash(question_text)
    if requires_figure:
        return "diagram_interpretation"
    if section == "WK":
        return "conceptual_definition"
    if section == "PC" or "read the passage" in text:
        return "diagnosis_scenario"
    concept_rule = _concept_rule(concept_tag, skill_tag)
    if concept_rule.get("template_family"):
        return str(concept_rule["template_family"])
    if "solve for" in text or re.search(r"\bx\b", text):
        return "formula_rearrangement"
    if any(token in text for token in ("after", "remaining", "combined", "together", "repeats", "then")) and _has_numeric_work(text):
        return "multi_step_formula"
    if _has_numeric_work(text):
        return "direct_formula"
    if any(token in text for token in ("most nearly means", "primarily", "purpose", "responsible", "part of", "which tool")):
        return "conceptual_definition"
    return "combined_concepts" if section in {"AO", "MC"} else "conceptual_definition"


def _infer_reasoning_steps(
    *,
    section: str,
    concept_tag: str,
    skill_tag: str,
    question_text: str,
    template_family: str,
    requires_figure: bool,
) -> int:
    concept_rule = _concept_rule(concept_tag, skill_tag)
    if concept_rule.get("reasoning_steps") is not None:
        return max(1, min(4, int(concept_rule["reasoning_steps"])))

    base = {
        "conceptual_definition": 1,
        "direct_formula": 1,
        "formula_rearrangement": 2,
        "multi_step_formula": 3,
        "diagnosis_scenario": 2,
        "diagram_interpretation": 2,
        "combined_concepts": 3,
    }.get(template_family, 2)
    text = normalize_text_for_hash(question_text)
    if any(token in text for token in ("after", "remaining", "combined", "repeat", "repeat this pattern", "then")):
        base += 1
    if requires_figure and template_family in {"diagram_interpretation", "combined_concepts"}:
        base += 1
    if section == "PC":
        base = max(base, 2)
    return max(1, min(4, base))


def _infer_formula_stack(
    *,
    concept_tag: str,
    skill_tag: str,
    template_family: str,
    question_text: str,
) -> list[str] | None:
    concept_rule = _concept_rule(concept_tag, skill_tag)
    if concept_rule.get("formula_stack"):
        return [str(item) for item in concept_rule["formula_stack"]]
    text = normalize_text_for_hash(question_text)
    if template_family not in {"direct_formula", "formula_rearrangement", "multi_step_formula", "combined_concepts"}:
        return None
    if "percent" in text:
        return ["part = base x rate", "new value = original +/- change"]
    if "average" in text:
        return ["average = total / count"]
    if "distance" in text or "miles per hour" in text:
        return ["distance = rate x time"]
    if "perimeter" in text:
        return ["perimeter = sum of side lengths"]
    if "density" in text:
        return ["density = mass / volume"]
    if "volts" in text or "ohms" in text or "amps" in text:
        return ["I = V / R"]
    if "torque" in text or "pivot" in text:
        return ["torque = force x distance"]
    return None


def _infer_concept_stack(concept_tag: str, skill_tag: str, template_family: str) -> list[str]:
    items = [concept_tag]
    if skill_tag and skill_tag != concept_tag:
        items.append(skill_tag)
    items.append(template_family)
    return items


def _infer_trap_type(question_text: str, template_family: str, formula_stack: list[str] | None) -> str | None:
    text = normalize_text_for_hash(question_text)
    if template_family == "formula_rearrangement":
        return "inverse_operation"
    if template_family == "direct_formula" and formula_stack:
        if any(token in text for token in ("percent", "ratio", "fraction")):
            return "wrong_base"
        return "wrong_operation"
    if template_family == "diagram_interpretation":
        return "orientation_misread"
    if template_family == "diagnosis_scenario":
        return "detail_confusion"
    return None


def _infer_prompt_shape(question_text: str, template_family: str, requires_figure: bool) -> str:
    text = normalize_text_for_hash(question_text)
    if requires_figure:
        if "gear" in text:
            return "gear_direction"
        if "circuit" in text or "volts" in text or "ohms" in text:
            return "circuit_read"
        if "mirror" in text:
            return "mirror_shape"
        if "rotate" in text or "rotated" in text:
            return "rotation_shape"
        return "figure_read"
    if "most nearly means" in text:
        return "vocabulary_match"
    if "read the passage" in text:
        return "passage_inference"
    if "solve for" in text:
        return "solve_variable"
    if "what does" in text or "purpose" in text or "part of" in text or "primarily" in text:
        return "definition"
    if any(token in text for token in ("after", "remaining", "combined", "together", "repeat")):
        return "multi_step"
    if _has_numeric_work(text):
        return "direct_compute"
    words = [word for word in re.split(r"[^a-z0-9]+", text) if word and word not in STOPWORDS]
    return "_".join(words[:3]) or template_family


def _infer_variant_signature(
    *,
    section: str,
    concept_tag: str,
    template_family: str,
    question_text: str,
    requires_figure: bool,
) -> str:
    prompt_shape = _infer_prompt_shape(question_text, template_family, requires_figure)
    presentation = "figure" if requires_figure else "text"
    return f"{section}:{concept_tag}:{prompt_shape}:{presentation}"


def _infer_figure_quality_status(
    *,
    requires_figure: bool,
    has_figure: bool,
    figure_svg: str | None,
) -> str:
    if not requires_figure and not has_figure:
        return "no_figure_needed"
    if figure_svg and str(figure_svg).strip():
        return "generated_svg"
    if requires_figure or has_figure:
        return "missing"
    return "needs_review"


def _infer_license_status(explicit_value: object, copyright_status: object, generation_method: str | None) -> str:
    explicit = normalize_skill_tag(explicit_value)
    if explicit:
        return explicit
    copyright_text = normalize_text_for_hash(copyright_status)
    if "open" in copyright_text:
        return "open_license"
    if "original" in copyright_text or "generated" in copyright_text or normalize_text_for_hash(generation_method) in {"template", "deterministic_generator"}:
        return "original_generated"
    return "needs_review"


def _infer_source_profile(explicit_value: object, source_name: str | None, generation_method: str | None) -> str | None:
    explicit = str(explicit_value).strip() if explicit_value is not None else ""
    if explicit:
        return explicit
    parts = [part.strip() for part in [source_name or "", generation_method or ""] if part and str(part).strip()]
    return ":".join(parts) if parts else None


def _recommended_difficulty_level(
    *,
    concept_tag: str,
    skill_tag: str,
    template_family: str,
    reasoning_steps: int,
    requires_figure: bool,
    source_difficulty_level: int | None = None,
) -> int:
    if source_difficulty_level is not None:
        return clamp_difficulty_level(source_difficulty_level)
    concept_rule = _concept_rule(concept_tag, skill_tag)
    if concept_rule.get("difficulty_level") is not None:
        level = int(concept_rule["difficulty_level"])
    else:
        level = TEMPLATE_FAMILY_LEVELS.get(template_family, 2)
        if reasoning_steps >= 3:
            level += 1
        if reasoning_steps >= 4:
            level += 1
    if requires_figure and template_family in {"diagram_interpretation", "combined_concepts"}:
        level += 1
    return clamp_difficulty_level(level)


def _derived_complexity_score(
    *,
    template_family: str,
    reasoning_steps: int,
    requires_figure: bool,
) -> int:
    base = 12 + reasoning_steps * 15
    base += {
        "conceptual_definition": 0,
        "direct_formula": 6,
        "formula_rearrangement": 10,
        "multi_step_formula": 18,
        "diagnosis_scenario": 12,
        "diagram_interpretation": 14,
        "combined_concepts": 22,
    }.get(template_family, 8)
    if requires_figure:
        base += 8
    return max(10, min(95, base))


def derive_question_profile(
    *,
    section: str,
    skill_tag: str,
    question_text: str,
    has_figure: bool = False,
    figure_type: str | None = None,
    figure_svg: str | None = None,
    generation_method: str | None = None,
    source_name: str | None = None,
    copyright_status: str | None = None,
    concept_tag: object = None,
    template_family: object = None,
    variant_signature: object = None,
    reasoning_steps: object = None,
    formula_stack: object = None,
    concept_stack: object = None,
    trap_type: object = None,
    requires_figure: object = None,
    figure_quality_status: object = None,
    license_status: object = None,
    source_profile: object = None,
    difficulty_num: object = None,
) -> QuestionProfile:
    normalized_skill = _clean_tag(skill_tag, fallback="general")
    normalized_concept = _clean_tag(concept_tag, fallback=normalized_skill)
    explicit_requires_figure = _as_optional_bool(requires_figure)
    resolved_requires_figure = (
        explicit_requires_figure
        if explicit_requires_figure is not None
        else _infer_requires_figure(question_text, has_figure, figure_type)
    )
    resolved_template_family = _clean_tag(
        template_family,
        fallback=_infer_template_family(
            section=section,
            skill_tag=normalized_skill,
            concept_tag=normalized_concept,
            question_text=question_text,
            requires_figure=resolved_requires_figure,
        ),
    )
    resolved_reasoning_steps = (
        max(1, min(4, int(reasoning_steps)))
        if reasoning_steps is not None and str(reasoning_steps).strip() != ""
        else _infer_reasoning_steps(
            section=section,
            concept_tag=normalized_concept,
            skill_tag=normalized_skill,
            question_text=question_text,
            template_family=resolved_template_family,
            requires_figure=resolved_requires_figure,
        )
    )
    resolved_formula_stack = _parse_jsonish_list(formula_stack) or _infer_formula_stack(
        concept_tag=normalized_concept,
        skill_tag=normalized_skill,
        template_family=resolved_template_family,
        question_text=question_text,
    )
    resolved_concept_stack = _parse_jsonish_list(concept_stack) or _infer_concept_stack(
        normalized_concept,
        normalized_skill,
        resolved_template_family,
    )
    resolved_trap_type = _clean_tag(
        trap_type,
        fallback=_infer_trap_type(question_text, resolved_template_family, resolved_formula_stack) or "",
    ) or None
    resolved_variant_signature = _clean_variant_signature(
        variant_signature,
        fallback=_infer_variant_signature(
            section=section,
            concept_tag=normalized_concept,
            template_family=resolved_template_family,
            question_text=question_text,
            requires_figure=resolved_requires_figure,
        ),
    )
    resolved_figure_quality_status = _clean_tag(
        figure_quality_status,
        fallback=_infer_figure_quality_status(
            requires_figure=resolved_requires_figure,
            has_figure=has_figure,
            figure_svg=figure_svg,
        ),
    )
    resolved_license_status = _infer_license_status(license_status, copyright_status, generation_method)
    resolved_source_profile = _infer_source_profile(source_profile, source_name, generation_method)
    resolved_source_difficulty_level = None
    if difficulty_num is not None and str(difficulty_num).strip() != "":
        try:
            resolved_source_difficulty_level = clamp_difficulty_level(int(float(difficulty_num)))
        except (TypeError, ValueError):
            resolved_source_difficulty_level = None
    recommended_level = _recommended_difficulty_level(
        concept_tag=normalized_concept,
        skill_tag=normalized_skill,
        template_family=resolved_template_family,
        reasoning_steps=resolved_reasoning_steps,
        requires_figure=resolved_requires_figure,
        source_difficulty_level=resolved_source_difficulty_level,
    )
    derived_complexity_score = _derived_complexity_score(
        template_family=resolved_template_family,
        reasoning_steps=resolved_reasoning_steps,
        requires_figure=resolved_requires_figure,
    )
    return QuestionProfile(
        concept_tag=normalized_concept,
        template_family=resolved_template_family,
        variant_signature=resolved_variant_signature,
        reasoning_steps=resolved_reasoning_steps,
        formula_stack=resolved_formula_stack,
        concept_stack=resolved_concept_stack,
        trap_type=resolved_trap_type,
        requires_figure=resolved_requires_figure,
        figure_quality_status=resolved_figure_quality_status,
        license_status=resolved_license_status,
        source_profile=resolved_source_profile,
        recommended_difficulty_level=recommended_level,
        derived_complexity_score=derived_complexity_score,
    )


def question_profile_from_question(question: object) -> QuestionProfile:
    return derive_question_profile(
        section=str(getattr(question, "section", "AR")),
        skill_tag=str(getattr(question, "skill_tag", "general")),
        question_text=str(getattr(question, "question_text", "")),
        has_figure=bool(getattr(question, "has_figure", False)),
        figure_type=getattr(question, "figure_type", None),
        figure_svg=getattr(question, "figure_svg", None),
        generation_method=getattr(question, "generation_method", None),
        source_name=getattr(question, "source_name", None),
        copyright_status=getattr(question, "copyright_status", None),
        concept_tag=getattr(question, "concept_tag", None),
        template_family=getattr(question, "template_family", None),
        variant_signature=getattr(question, "variant_signature", None),
        reasoning_steps=getattr(question, "reasoning_steps", None),
        formula_stack=getattr(question, "formula_stack", None),
        concept_stack=getattr(question, "concept_stack", None),
        trap_type=getattr(question, "trap_type", None),
        requires_figure=getattr(question, "requires_figure", None),
        figure_quality_status=getattr(question, "figure_quality_status", None),
        license_status=getattr(question, "license_status", None),
        source_profile=getattr(question, "source_profile", None),
        difficulty_num=getattr(question, "difficulty_num", None),
    )

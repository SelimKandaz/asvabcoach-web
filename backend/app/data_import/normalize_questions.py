from __future__ import annotations

import hashlib
import re
import unicodedata


SECTION_ALIASES = {
    "AR": "AR",
    "ARITHMETIC REASONING": "AR",
    "MATHEMATICS KNOWLEDGE": "MK",
    "MATH KNOWLEDGE": "MK",
    "MK": "MK",
    "WORD KNOWLEDGE": "WK",
    "WK": "WK",
    "PARAGRAPH COMPREHENSION": "PC",
    "PC": "PC",
    "GENERAL SCIENCE": "GS",
    "GS": "GS",
    "ELECTRONICS INFORMATION": "EI",
    "EI": "EI",
    "AUTO INFORMATION": "AI",
    "AUTO AND SHOP": "AS",
    "AUTO SHOP": "AS",
    "AS": "AS",
    "SHOP INFORMATION": "SI",
    "SI": "SI",
    "MECHANICAL COMPREHENSION": "MC",
    "MC": "MC",
    "ASSEMBLING OBJECTS": "AO",
    "AO": "AO",
}

SECTION_LABELS = {
    "AR": "Arithmetic Reasoning",
    "MK": "Mathematics Knowledge",
    "WK": "Word Knowledge",
    "PC": "Paragraph Comprehension",
    "GS": "General Science",
    "EI": "Electronics Information",
    "AI": "Auto Information",
    "AS": "Auto Shop",
    "SI": "Shop Information",
    "MC": "Mechanical Comprehension",
    "AO": "Assembling Objects",
}

HEADER_ALIASES = {
    "id": ["id", "question_id", "question id"],
    "source_question_id": ["source_question_id", "source id", "external_id", "legacy_id"],
    "source_id": ["source_id"],
    "section": ["section", "subtest", "domain"],
    "skill_tag": ["skill", "skill_tag", "topic", "concept"],
    "skill_tags": ["skill_tags"],
    "concept_tag": ["concept_tag", "concept"],
    "question_type": ["question_type"],
    "subtype": ["subtype"],
    "template_family": ["template_family"],
    "variant_signature": ["variant_signature"],
    "reasoning_steps": ["reasoning_steps"],
    "formula_stack": ["formula_stack"],
    "concept_stack": ["concept_stack"],
    "trap_type": ["trap_type"],
    "difficulty_level": ["difficulty", "difficulty_level", "difficulty_estimate", "level"],
    "difficulty_num": ["difficulty_num"],
    "difficulty_label": ["difficulty_label"],
    "irt_a": ["irt_a", "a", "discrimination"],
    "irt_b": ["irt_b", "b", "difficulty_param"],
    "irt_c": ["irt_c", "c", "guessing"],
    "passage_id": ["passage_id"],
    "passage_topic": ["passage_topic"],
    "passage_text": ["passage_text"],
    "passage_word_count": ["passage_word_count"],
    "vocab_word": ["vocab_word"],
    "part_of_speech": ["part_of_speech"],
    "question_text": ["question", "question_text", "prompt"],
    "passage_text": ["passage_text", "passage"],
    "question_stem": ["question_stem"],
    "choice_a": ["choice_a", "answer_a", "a_text", "option_a", "option a"],
    "choice_b": ["choice_b", "answer_b", "b_text", "option_b", "option b"],
    "choice_c": ["choice_c", "answer_c", "c_text", "option_c", "option c"],
    "choice_d": ["choice_d", "answer_d", "d_text", "option_d", "option d"],
    "correct_answer": ["correct_answer", "correct", "answer_key", "answer"],
    "correct_value": ["correct_value"],
    "definition": ["definition"],
    "base_explanation": ["base_explanation", "explanation", "solution"],
    "wrong_a_explanation": ["wrong_a_explanation"],
    "wrong_b_explanation": ["wrong_b_explanation"],
    "wrong_c_explanation": ["wrong_c_explanation"],
    "wrong_d_explanation": ["wrong_d_explanation"],
    "wrong_answer_explanation": ["wrong_answer_explanation"],
    "quick_method": ["quick_method", "shortcut", "tip"],
    "source_name": ["source_name", "source"],
    "source_alignment": ["source_alignment"],
    "source_url": ["source_url"],
    "source_confidence": ["source_confidence"],
    "source_profile": ["source_profile"],
    "content_origin": ["content_origin"],
    "asset_path": ["asset_path"],
    "reading_source_profile": ["reading_source_profile"],
    "lexical_source_profile": ["lexical_source_profile"],
    "frequency_source_profile": ["frequency_source_profile"],
    "canonical_hash": ["canonical_hash"],
    "confidence": ["confidence"],
    "copyright_status": ["copyright_status", "copyright"],
    "license_status": ["license_status"],
    "observed_correct_rate": ["observed_correct_rate", "observed_correct_rate_estimate"],
    "average_response_time_seconds": ["average_response_time_seconds", "sample_time_seconds"],
    "complexity_score": ["complexity_score"],
    "generation_method": ["generation_method"],
    "validation_status": ["validation_status"],
    "content_status": ["content_status"],
    "issue_notes": ["issue_notes", "notes"],
    "validator_name": ["validator_name"],
    "calibrated_difficulty_level": ["calibrated_difficulty_level"],
    "calibrated_irt_b": ["calibrated_irt_b"],
    "times_seen": ["times_seen"],
    "sample_size_estimate": ["sample_size_estimate"],
    "has_figure": ["has_figure", "figure", "figure_present"],
    "requires_figure": ["requires_figure"],
    "figure_type": ["figure_type", "figure_kind"],
    "figure_data": ["figure_data"],
    "figure_svg": ["figure_svg"],
    "figure_alt_text": ["figure_alt_text", "figure_alt"],
    "figure_quality_status": ["figure_quality_status"],
    "active": ["active"],
    "eligible_for_study": ["eligible_for_study"],
    "eligible_for_cat": ["eligible_for_cat"],
    "eligible_for_review": ["eligible_for_review"],
}

DIFFICULTY_TO_B = {1: -2.0, 2: -1.0, 3: 0.0, 4: 1.0, 5: 2.0}


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def build_header_map(columns: list[str]) -> dict[str, str]:
    normalized_columns = {normalize_header(column): column for column in columns}
    header_map: dict[str, str] = {}
    for target, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            match = normalized_columns.get(normalize_header(alias))
            if match:
                header_map[target] = match
                break
    return header_map


def normalize_section_name(value: str | None) -> str:
    if value is None:
        return "AR"
    normalized = str(value).strip().upper()
    return SECTION_ALIASES.get(normalized, normalized[:2] if normalized else "AR")


def normalize_text_for_hash(value: str | None) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u00c2\u00b2", "^2").replace("\u00c2\u00b3", "^3")
    text = text.replace("\u00b2", "^2").replace("\u00b3", "^3")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = text.lower().strip()
    text = re.sub(r"[\u200b\u200c\u200d]", "", text)
    text = re.sub(r"[^a-z0-9^]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_choice_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def canonical_hash_for_question(question_text: str, choices: dict[str, str]) -> str:
    normalized_choices = sorted(
        normalize_text_for_hash(choices.get(label, ""))
        for label in ("A", "B", "C", "D")
    )
    blob = " | ".join(
        [
            normalize_text_for_hash(question_text),
            *normalized_choices,
        ]
    )
    digest = hashlib.sha1(blob.encode("utf-8")).hexdigest()
    return digest


def normalize_correct_answer(value: object, choices: dict[str, str]) -> str:
    if value is None:
        return ""
    text = str(value).strip().upper()
    if text in {"A", "B", "C", "D"}:
        return text
    for key, choice in choices.items():
        if text == choice.strip().upper():
            return key
    return ""


def normalize_skill_tag(value: object) -> str:
    text = str(value).strip().lower() if value is not None else ""
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "general"


def normalize_difficulty(value: object) -> int:
    try:
        difficulty = int(float(value))
    except (TypeError, ValueError):
        difficulty = 3
    return max(1, min(5, difficulty))


def default_irt_values(difficulty_level: int) -> tuple[float, float, float]:
    return 1.0, DIFFICULTY_TO_B.get(difficulty_level, 0.0), 0.25


def generate_stable_question_id(source_question_id: str | None, section: str, question_text: str, choices: dict[str, str]) -> str:
    if source_question_id:
        base = f"{section}:{source_question_id}"
    else:
        base = canonical_hash_for_question(question_text, choices)
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
    return f"q_{digest}"

from __future__ import annotations

from .deterministic import GeneratedQuestionDraft, generate_questions_for_section as _generate_questions_for_section
from .deterministic import generate_questions_for_sections as _generate_questions_for_sections
from .validators import validate_generated_question
from app.services.question_profile_service import derive_question_profile


def _apply_skill_tags(items: list[GeneratedQuestionDraft], skill_tags: list[str] | None) -> list[GeneratedQuestionDraft]:
    if not skill_tags:
        return items
    cleaned = [tag.strip() for tag in skill_tags if tag and tag.strip()]
    if not cleaned:
        return items
    for index, item in enumerate(items):
        item.skill_tag = cleaned[index % len(cleaned)]
        profile = derive_question_profile(
            section=item.section,
            skill_tag=item.skill_tag,
            question_text=item.question_text,
            has_figure=bool(getattr(item, "has_figure", False)),
            figure_type=getattr(item, "figure_type", None),
            figure_svg=getattr(item, "figure_svg", None),
            generation_method="template",
            source_name="deterministic_generator",
        )
        item.concept_tag = profile.concept_tag
        item.template_family = profile.template_family
        item.variant_signature = profile.variant_signature
        item.reasoning_steps = profile.reasoning_steps
        item.formula_stack = profile.formula_stack
        item.concept_stack = profile.concept_stack
        item.trap_type = profile.trap_type
        item.requires_figure = profile.requires_figure
        item.figure_quality_status = profile.figure_quality_status
        item.license_status = profile.license_status
        item.source_profile = profile.source_profile
        item.difficulty_level = profile.recommended_difficulty_level
        item.complexity_score = max(item.complexity_score, profile.derived_complexity_score)
    return items


def generate_questions_for_section(
    section: str,
    *,
    questions_per_section: int,
    difficulty_levels: list[int],
    skill_tags: list[str] | None = None,
) -> list[GeneratedQuestionDraft]:
    items = _generate_questions_for_section(
        section,
        questions_per_section=questions_per_section,
        difficulty_levels=difficulty_levels,
    )
    items = _apply_skill_tags(items, skill_tags)
    return [item for item in items if validate_generated_question(item).passed]


def generate_questions_for_sections(
    sections: list[str],
    *,
    questions_per_section: int,
    difficulty_levels: list[int],
    skill_tags: list[str] | None = None,
) -> list[GeneratedQuestionDraft]:
    items = _generate_questions_for_sections(
        sections,
        questions_per_section=questions_per_section,
        difficulty_levels=difficulty_levels,
    )
    items = _apply_skill_tags(items, skill_tags)
    return [item for item in items if validate_generated_question(item).passed]

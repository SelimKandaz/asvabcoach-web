from __future__ import annotations

from dataclasses import dataclass

from .base import GeneratedQuestionDraft
from app.services.question_profile_service import derive_question_profile


@dataclass(slots=True)
class ValidationResult:
    passed: bool
    issues: list[str]


def validate_generated_question(draft: GeneratedQuestionDraft) -> ValidationResult:
    issues: list[str] = []
    choices = draft.choices
    if set(choices) != {"A", "B", "C", "D"}:
        issues.append("Question must have exactly four labeled choices.")
    values = [choices.get("A"), choices.get("B"), choices.get("C"), choices.get("D")]
    if any(value is None or not str(value).strip() for value in values):
        issues.append("One or more choices are empty.")
    if len({str(value).strip() for value in values if value is not None}) < 4:
        issues.append("Choice text must be unique.")
    if draft.correct_answer not in choices:
        issues.append("Correct answer label must be one of A/B/C/D.")
    if draft.correct_answer in choices and not str(choices[draft.correct_answer]).strip():
        issues.append("Correct choice text is empty.")
    if getattr(draft, "has_figure", False) and not getattr(draft, "figure_svg", None):
        issues.append("Figure questions must include SVG markup.")
    if not getattr(draft, "concept_tag", ""):
        issues.append("Generated question must set concept_tag.")
    if not getattr(draft, "template_family", ""):
        issues.append("Generated question must set template_family.")
    if not getattr(draft, "variant_signature", ""):
        issues.append("Generated question must set variant_signature.")
    profile = derive_question_profile(
        section=draft.section,
        skill_tag=draft.skill_tag,
        question_text=draft.question_text,
        has_figure=bool(getattr(draft, "has_figure", False)),
        figure_type=getattr(draft, "figure_type", None),
        figure_svg=getattr(draft, "figure_svg", None),
        generation_method="template",
        concept_tag=getattr(draft, "concept_tag", None),
        template_family=getattr(draft, "template_family", None),
        variant_signature=getattr(draft, "variant_signature", None),
        reasoning_steps=getattr(draft, "reasoning_steps", None),
        formula_stack=getattr(draft, "formula_stack", None),
        concept_stack=getattr(draft, "concept_stack", None),
        trap_type=getattr(draft, "trap_type", None),
        requires_figure=getattr(draft, "requires_figure", None),
        figure_quality_status=getattr(draft, "figure_quality_status", None),
        license_status=getattr(draft, "license_status", None),
        source_profile=getattr(draft, "source_profile", None),
    )
    if abs(int(draft.difficulty_level) - int(profile.recommended_difficulty_level)) >= 2:
        issues.append("Difficulty level does not match reasoning depth and template family.")
    return ValidationResult(passed=not issues, issues=issues)

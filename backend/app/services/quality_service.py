from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.generation import generate_questions_for_sections
from app.models import CareerRequirement, Question, ResponseRecord
from app.schemas import (
    AdminGenerateRequest,
    AdminMaintenanceResult,
    CareerRequirementRead,
    DashboardSummary,
    QuestionAuditIssue,
    SectionSummary,
)
from app.data_import.normalize_questions import canonical_hash_for_question, generate_stable_question_id
from app.services.difficulty_service import (
    difficulty_irt_b,
    infer_difficulty_level,
    resolved_difficulty_level,
)
from app.services.bank_rules import (
    BANK_ROLE_MAIN_PRACTICE,
    BANK_ROLE_LEGACY,
    BANK_ROLE_ELITE_ORIGINAL_PRACTICE,
    is_elite_original_practice_source,
    is_replacement_bank_source,
    is_review_archive_question,
    is_simulator_question,
    normalize_bank_role,
)
from app.services.question_profile_service import question_profile_from_question


SECTION_REPORT_ORDER = ["GS", "AR", "WK", "PC", "MK", "EI", "AI", "AS", "SI", "MC", "AO"]
SELECTABLE_CONTENT_STATUSES = {"verified", "active"}
CAT_BLUEPRINT_TARGETS = {
    "GS": 15,
    "AR": 15,
    "WK": 15,
    "PC": 10,
    "MK": 15,
    "EI": 15,
    "AI": 10,
    "SI": 10,
    "MC": 15,
    "AO": 15,
}
AFQT_BLUEPRINT_TARGETS = {"AR": 15, "WK": 15, "PC": 10, "MK": 15}


def _selectable_filter():
    return Question.active.is_(True), Question.content_status.in_(SELECTABLE_CONTENT_STATUSES), Question.duplicate_of_question_id.is_(None)


def _normalize_issue_type(issue_type: str) -> str:
    return issue_type.replace(" ", "_").lower()


def _quality_rank(question: Question) -> tuple[int, int, int, int, float, datetime]:
    content_rank = {
        "verified": 0,
        "active": 1,
        "needs_review": 2,
        "draft": 3,
        "duplicate": 4,
        "bad": 5,
        None: 3,
    }.get(question.content_status, 3)
    validation_rank = 0 if question.validation_status == "passed" else 1
    active_rank = 0 if question.active else 1
    times_seen = -(question.times_seen or 0)
    correct_rate = -(question.observed_correct_rate or 0.0)
    updated_at = question.updated_at or question.created_at
    return content_rank, validation_rank, active_rank, times_seen, correct_rate, updated_at


def _question_canonical_hash(question: Question) -> str:
    if question.canonical_hash:
        return question.canonical_hash
    return canonical_hash_for_question(
        question.question_text,
        {
            "A": question.choice_a,
            "B": question.choice_b,
            "C": question.choice_c,
            "D": question.choice_d,
        },
    )


def audit_questions(db: Session, *, limit: int = 500) -> list[QuestionAuditIssue]:
    questions = list(db.scalars(select(Question)).all())
    issues: list[QuestionAuditIssue] = []

    canonical_groups: dict[str, list[Question]] = defaultdict(list)

    for question in questions:
        profile = question_profile_from_question(question)
        canonical_hash = _question_canonical_hash(question)
        canonical_groups[canonical_hash].append(question)

        if not question.base_explanation:
            issues.append(
                QuestionAuditIssue(
                    issue_type="missing_explanation",
                    question_id=question.id,
                    details="Question is missing a base explanation.",
                    severity="medium",
                )
            )
        if question.correct_answer not in {"A", "B", "C", "D"}:
            issues.append(
                QuestionAuditIssue(
                    issue_type="invalid_correct_answer",
                    question_id=question.id,
                    details="Correct answer is missing or invalid.",
                    severity="high",
                )
            )
        if len({question.choice_a, question.choice_b, question.choice_c, question.choice_d}) < 4:
            issues.append(
                QuestionAuditIssue(
                    issue_type="duplicate_choices",
                    question_id=question.id,
                    details="One or more answer choices are duplicated.",
                    severity="medium",
                )
            )
        if question.has_figure and not question.figure_svg:
            issues.append(
                QuestionAuditIssue(
                    issue_type="figure_missing_svg",
                    question_id=question.id,
                    details="Question is marked as a figure item but does not include SVG markup.",
                    severity="medium",
                )
            )
        if "according to the figure" in (question.question_text or "").lower() and not question.figure_svg:
            issues.append(
                QuestionAuditIssue(
                    issue_type="figure_reference_without_svg",
                    question_id=question.id,
                    details="Question text references a figure but no SVG was stored.",
                    severity="high",
                )
            )
        if not question.concept_tag:
            issues.append(
                QuestionAuditIssue(
                    issue_type="missing_concept_tag",
                    question_id=question.id,
                    details="Question is missing concept_tag.",
                    severity="high",
                )
            )
        if not question.template_family:
            issues.append(
                QuestionAuditIssue(
                    issue_type="missing_template_family",
                    question_id=question.id,
                    details="Question is missing template_family.",
                    severity="high",
                )
            )
        if not question.variant_signature:
            issues.append(
                QuestionAuditIssue(
                    issue_type="missing_variant_signature",
                    question_id=question.id,
                    details="Question is missing variant_signature.",
                    severity="high",
                )
            )
        effective_level = resolved_difficulty_level(question)
        if effective_level not in {1, 2, 3, 4, 5}:
            issues.append(
                QuestionAuditIssue(
                    issue_type="difficulty_out_of_range",
                    question_id=question.id,
                    details="Difficulty level is outside the 1-5 range.",
                    severity="medium",
                )
            )
        if abs(effective_level - profile.recommended_difficulty_level) >= 2:
            issues.append(
                QuestionAuditIssue(
                    issue_type="difficulty_profile_mismatch",
                    question_id=question.id,
                    details=(
                        f"Difficulty {effective_level} conflicts with reasoning_steps={profile.reasoning_steps} "
                        f"and template_family={profile.template_family}."
                    ),
                    severity="medium",
                )
            )
        if question.content_status not in SELECTABLE_CONTENT_STATUSES and question.content_status != "duplicate":
            issues.append(
                QuestionAuditIssue(
                    issue_type=f"content_status_{_normalize_issue_type(question.content_status or 'unknown')}",
                    question_id=question.id,
                    details=f"Question content status is '{question.content_status or 'unknown'}'.",
                    severity="low" if question.content_status in {"needs_review", "draft"} else "high",
                )
            )
        has_reliable_rate_signal = (
            question.observed_correct_rate is not None
            and ((question.times_seen or 0) >= 3 or question.complexity_score is not None)
        )
        if has_reliable_rate_signal:
            if effective_level <= 2 and question.observed_correct_rate < 0.35:
                issues.append(
                    QuestionAuditIssue(
                        issue_type="difficulty_too_easy",
                        question_id=question.id,
                        details="Observed correct rate suggests this item is harder than its current difficulty.",
                        severity="medium",
                    )
                )
            if effective_level >= 4 and question.observed_correct_rate > 0.85:
                issues.append(
                    QuestionAuditIssue(
                        issue_type="difficulty_too_hard",
                        question_id=question.id,
                        details="Observed correct rate suggests this item is easier than its current difficulty.",
                        severity="medium",
                    )
                )
        stem = question.question_text.lower()
        if "one solution" in stem and ("x^2" in stem or "x²" in stem):
            numeric_choices = 0
            for choice in (question.choice_a, question.choice_b, question.choice_c, question.choice_d):
                choice_text = choice.strip()
                if choice_text and choice_text.replace(".", "", 1).replace("-", "", 1).isdigit():
                    numeric_choices += 1
            if numeric_choices >= 2:
                issues.append(
                    QuestionAuditIssue(
                        issue_type="possible_multiple_valid_roots",
                        question_id=question.id,
                        details="Stem suggests a single solution but choices look like multiple valid roots.",
                        severity="high",
                    )
                )
        if not question.canonical_hash:
            issues.append(
                QuestionAuditIssue(
                    issue_type="missing_canonical_hash",
                    question_id=question.id,
                    details="Question is missing a canonical hash and should be reindexed.",
                    severity="medium",
                )
            )
        if question.observed_correct_rate is not None and question.times_seen >= 10:
            if not 0.2 <= question.observed_correct_rate <= 0.95:
                issues.append(
                    QuestionAuditIssue(
                        issue_type="outlier_correct_rate",
                        question_id=question.id,
                        details="Observed correct rate looks inconsistent with a normal ASVAB item.",
                        severity="low",
                    )
                )

    for canonical_hash, items in canonical_groups.items():
        if len(items) <= 1:
            continue
        sorted_items = sorted(items, key=_quality_rank)
        winner = sorted_items[0]
        for duplicate in sorted_items[1:]:
            issues.append(
                QuestionAuditIssue(
                    issue_type="duplicate_canonical_hash",
                    question_id=duplicate.id,
                    details=f"Duplicate of {winner.id} via canonical hash {canonical_hash[:12]}.",
                    severity="high",
                )
            )

    active_questions = [
        question
        for question in questions
        if question.active and question.content_status in SELECTABLE_CONTENT_STATUSES and not question.duplicate_of_question_id
    ]
    by_section_variant: dict[tuple[str, str], int] = defaultdict(int)
    by_section_template: dict[tuple[str, str], int] = defaultdict(int)
    section_totals: dict[str, int] = defaultdict(int)
    for question in active_questions:
        active_profile = question_profile_from_question(question)
        section_totals[question.section] += 1
        by_section_variant[(question.section, question.variant_signature or active_profile.variant_signature)] += 1
        by_section_template[(question.section, question.template_family or active_profile.template_family)] += 1
    for (section, variant_signature), count in by_section_variant.items():
        total = max(section_totals.get(section, 1), 1)
        if count > max(3, round(total * 0.05)):
            issues.append(
                QuestionAuditIssue(
                    issue_type="variant_signature_overload",
                    details=f"{section} variant {variant_signature} has {count} active questions out of {total}.",
                    severity="medium",
                )
            )
    for (section, template_family), count in by_section_template.items():
        total = max(section_totals.get(section, 1), 1)
        if count > max(5, round(total * 0.2)):
            issues.append(
                QuestionAuditIssue(
                    issue_type="template_family_overload",
                    details=f"{section} template_family {template_family} has {count} active questions out of {total}.",
                    severity="low",
                )
            )

    return issues[:limit]


def dedupe_questions(db: Session) -> AdminMaintenanceResult:
    questions = list(db.scalars(select(Question)).all())
    groups: dict[str, list[Question]] = defaultdict(list)
    for question in questions:
        if not question.canonical_hash:
            question.canonical_hash = _question_canonical_hash(question)
        groups[question.canonical_hash].append(question)

    processed = 0
    deduped = 0
    messages: list[str] = []
    for canonical_hash, items in groups.items():
        processed += len(items)
        if len(items) <= 1:
            continue
        sorted_items = sorted(items, key=_quality_rank)
        winner = sorted_items[0]
        for duplicate in sorted_items[1:]:
            if duplicate.duplicate_of_question_id == winner.id and duplicate.content_status == "duplicate":
                continue
            duplicate.duplicate_of_question_id = winner.id
            duplicate.content_status = "duplicate"
            duplicate.active = False
            duplicate.issue_notes = (
                (duplicate.issue_notes + " | " if duplicate.issue_notes else "")
                + f"Marked duplicate of {winner.id} during dedupe run."
            )
            deduped += 1
        messages.append(f"Canonical hash {canonical_hash[:12]} kept {winner.id} and marked {max(0, len(sorted_items) - 1)} duplicates.")

    db.commit()
    return AdminMaintenanceResult(
        status="completed",
        processed_count=processed,
        deduped_count=deduped,
        messages=messages,
    )


def recalibrate_difficulties(db: Session) -> AdminMaintenanceResult:
    questions = list(
        db.scalars(
            select(Question).where(
                Question.active.is_(True),
                Question.content_status.in_(SELECTABLE_CONTENT_STATUSES),
            )
        ).all()
    )

    response_rows = db.execute(
        select(
            ResponseRecord.question_id,
            func.count(ResponseRecord.id),
            func.sum(case((ResponseRecord.is_correct.is_(True), 1), else_=0)),
            func.avg(ResponseRecord.response_time_seconds),
        ).group_by(ResponseRecord.question_id)
    ).all()
    response_stats = {
        question_id: {
            "count": int(count or 0),
            "correct": int(correct or 0),
            "correct_rate": (float(correct or 0) / max(int(count or 0), 1)),
            "avg_time": float(avg_time or 0.0),
        }
        for question_id, count, correct, avg_time in response_rows
    }

    recalibrated = 0
    messages: list[str] = []
    for question in questions:
        response_stats_row = response_stats.get(question.id, {})
        profile = question_profile_from_question(question)
        current_level = resolved_difficulty_level(question)
        resolved_complexity = question.complexity_score or profile.derived_complexity_score
        blended_level, evidence_strength = infer_difficulty_level(
            base_level=profile.recommended_difficulty_level,
            observed_correct_rate=question.observed_correct_rate,
            observed_sample_size=question.times_seen or 0,
            complexity_score=resolved_complexity,
            response_correct_rate=response_stats_row.get("correct_rate"),
            response_count=response_stats_row.get("count", 0),
            prior_level=current_level,
        )
        if evidence_strength < 0.35:
            continue
        new_b = difficulty_irt_b(blended_level)
        if (
            question.concept_tag != profile.concept_tag
            or question.template_family != profile.template_family
            or question.variant_signature != profile.variant_signature
            or question.reasoning_steps != profile.reasoning_steps
            or question.formula_stack != profile.formula_stack
            or question.concept_stack != profile.concept_stack
            or question.trap_type != profile.trap_type
            or question.requires_figure != profile.requires_figure
            or question.figure_quality_status != profile.figure_quality_status
            or question.license_status != profile.license_status
            or question.source_profile != profile.source_profile
            or question.complexity_score != resolved_complexity
            or question.difficulty_level != blended_level
            or question.calibrated_difficulty_level != blended_level
            or question.irt_b != new_b
            or question.calibrated_irt_b != new_b
        ):
            question.concept_tag = profile.concept_tag
            question.template_family = profile.template_family
            question.variant_signature = profile.variant_signature
            question.reasoning_steps = profile.reasoning_steps
            question.formula_stack = profile.formula_stack
            question.concept_stack = profile.concept_stack
            question.trap_type = profile.trap_type
            question.requires_figure = profile.requires_figure
            question.figure_quality_status = profile.figure_quality_status
            question.license_status = profile.license_status
            question.source_profile = profile.source_profile
            question.complexity_score = resolved_complexity
            question.difficulty_level = blended_level
            question.calibrated_difficulty_level = blended_level
            question.irt_b = new_b
            question.calibrated_irt_b = new_b
            if question.figure_quality_status == "missing":
                question.content_status = "needs_review"
                question.validation_status = "needs_review"
                question.active = False
            recalibrated += 1
    db.commit()
    messages.append(f"Recalibrated {recalibrated} active questions with sufficient evidence.")
    return AdminMaintenanceResult(
        status="completed",
        processed_count=len(questions),
        recalibrated_count=recalibrated,
        messages=messages,
    )


def _build_question_payload_from_draft(draft, *, source_name: str, generation_method: str, active: bool) -> dict:
    return {
        "section": draft.section,
        "skill_tag": draft.skill_tag,
        "concept_tag": draft.concept_tag,
        "template_family": draft.template_family,
        "variant_signature": draft.variant_signature,
        "reasoning_steps": draft.reasoning_steps,
        "formula_stack": draft.formula_stack,
        "concept_stack": draft.concept_stack,
        "trap_type": draft.trap_type,
        "difficulty_level": draft.difficulty_level,
        "irt_a": getattr(draft, "irt_a", 1.0),
        "irt_b": difficulty_irt_b(draft.difficulty_level),
        "irt_c": getattr(draft, "irt_c", 0.25),
        "calibrated_difficulty_level": draft.difficulty_level,
        "calibrated_irt_b": difficulty_irt_b(draft.difficulty_level),
        "question_text": draft.question_text,
        "choice_a": draft.choices["A"],
        "choice_b": draft.choices["B"],
        "choice_c": draft.choices["C"],
        "choice_d": draft.choices["D"],
        "correct_answer": draft.correct_answer,
        "has_figure": bool(getattr(draft, "has_figure", False)),
        "requires_figure": bool(getattr(draft, "requires_figure", False)),
        "figure_type": getattr(draft, "figure_type", None),
        "figure_data": getattr(draft, "figure_data", None),
        "figure_svg": getattr(draft, "figure_svg", None),
        "figure_alt_text": getattr(draft, "figure_alt_text", None),
        "figure_quality_status": getattr(draft, "figure_quality_status", None),
        "base_explanation": draft.base_explanation,
        "wrong_a_explanation": draft.wrong_a_explanation,
        "wrong_b_explanation": draft.wrong_b_explanation,
        "wrong_c_explanation": draft.wrong_c_explanation,
        "wrong_d_explanation": draft.wrong_d_explanation,
        "quick_method": draft.quick_method,
        "source_name": source_name,
        "source_confidence": "estimated",
        "copyright_status": "original",
        "license_status": getattr(draft, "license_status", "original_generated"),
        "source_profile": getattr(draft, "source_profile", None),
        "content_status": "verified",
        "issue_notes": None,
        "complexity_score": draft.complexity_score,
        "generation_method": generation_method,
        "validator_name": "deterministic_generator",
        "validation_status": "passed",
        "times_seen": 0,
        "observed_correct_rate": draft.observed_correct_rate,
        "average_response_time_seconds": draft.average_response_time_seconds,
        "active": active,
    }


def generate_questions(db: Session, request: AdminGenerateRequest) -> AdminMaintenanceResult:
    generated = generate_questions_for_sections(
        request.sections,
        questions_per_section=request.questions_per_section,
        difficulty_levels=request.difficulty_levels,
        skill_tags=request.skill_tags,
    )
    existing_ids = set(db.scalars(select(Question.id)).all())
    existing_hashes = set(
        db.scalars(select(Question.canonical_hash).where(Question.canonical_hash.is_not(None))).all()
    )
    existing_variant_counts = {
        (section, variant_signature): int(count or 0)
        for section, variant_signature, count in db.execute(
            select(Question.section, Question.variant_signature, func.count(Question.id))
            .where(*_selectable_filter(), Question.variant_signature.is_not(None))
            .group_by(Question.section, Question.variant_signature)
        ).all()
    }
    section_totals = {
        section: int(count or 0)
        for section, count in db.execute(
            select(Question.section, func.count(Question.id))
            .where(*_selectable_filter())
            .group_by(Question.section)
        ).all()
    }

    created = 0
    skipped = 0
    messages: list[str] = []
    for draft in generated:
        question_id = generate_stable_question_id(None, draft.section, draft.question_text, draft.choices)
        canonical_hash = canonical_hash_for_question(draft.question_text, draft.choices)
        if question_id in existing_ids or canonical_hash in existing_hashes:
            skipped += 1
            continue

        payload = _build_question_payload_from_draft(
            draft,
            source_name=request.source_name,
            generation_method=request.generation_method,
            active=request.active,
        )
        section_total = section_totals.get(draft.section, 0)
        current_variant_count = existing_variant_counts.get((draft.section, draft.variant_signature), 0)
        if current_variant_count >= max(3, round(max(section_total, 1) * 0.05)):
            skipped += 1
            continue
        payload["id"] = question_id
        payload["canonical_hash"] = canonical_hash
        question = Question(**payload)
        db.add(question)
        existing_ids.add(question_id)
        existing_hashes.add(canonical_hash)
        existing_variant_counts[(draft.section, draft.variant_signature)] = current_variant_count + 1
        section_totals[draft.section] = section_total + 1
        created += 1

    db.commit()
    messages.append(f"Generated {created} new questions across {len(request.sections)} sections.")
    if skipped:
        messages.append(f"Skipped {skipped} duplicates already present in the bank.")
    return AdminMaintenanceResult(
        status="completed",
        processed_count=len(generated),
        created_count=created,
        messages=messages,
    )


def _active_pool(questions: list[Question]) -> list[Question]:
    return [
        question
        for question in questions
        if question.active and question.content_status in SELECTABLE_CONTENT_STATUSES and not question.duplicate_of_question_id
    ]


def _pool_shape_report(questions: list[Question]) -> dict:
    active_questions = _active_pool(questions)
    by_section: dict[str, int] = defaultdict(int)
    by_difficulty: dict[str, int] = defaultdict(int)
    by_template_family: dict[str, int] = defaultdict(int)
    by_variant_signature: dict[str, int] = defaultdict(int)
    for question in active_questions:
        by_section[question.section] += 1
        by_difficulty[f"{question.section}:L{question.difficulty_level}"] += 1
        by_template_family[f"{question.section}:{question.template_family}"] += 1
        by_variant_signature[f"{question.section}:{question.variant_signature}"] += 1
    return {
        "by_section": dict(sorted(by_section.items())),
        "by_difficulty": dict(sorted(by_difficulty.items())),
        "by_template_family": dict(sorted(by_template_family.items())),
        "by_variant_signature": dict(sorted(by_variant_signature.items())),
    }


def rebalance_question_bank(db: Session) -> AdminMaintenanceResult:
    questions = list(db.scalars(select(Question)).all())
    processed = len(questions)
    updated = 0
    messages: list[str] = []
    restored = 0
    deactivated = 0

    for question in questions:
        if question.figure_quality_status == "missing" and question.active:
            question.active = False
            question.content_status = "needs_review"
            question.validation_status = "needs_review"
            question.issue_notes = (
                (question.issue_notes + " | " if question.issue_notes else "")
                + "Deactivated during rebalance because figure SVG is missing."
            )
            updated += 1
            deactivated += 1

    for question in questions:
        if not (is_replacement_bank_source(question.source_name) or is_elite_original_practice_source(question.source_name)):
            continue
        desired_bank_role = (
            BANK_ROLE_ELITE_ORIGINAL_PRACTICE
            if is_elite_original_practice_source(question.source_name)
            else BANK_ROLE_MAIN_PRACTICE
        )
        if normalize_bank_role(question.bank_role) != BANK_ROLE_LEGACY and normalize_bank_role(question.bank_role) != desired_bank_role:
            question.bank_role = desired_bank_role
            updated += 1
        desired_active = (
            question.content_status in SELECTABLE_CONTENT_STATUSES
            and question.validation_status == "passed"
            and question.duplicate_of_question_id is None
            and question.figure_quality_status != "missing"
            and not is_simulator_question(question)
            and not is_review_archive_question(question)
        )
        if desired_active and not question.active:
            question.active = True
            updated += 1
            restored += 1
            if question.content_status in {"needs_review", "draft"}:
                question.content_status = "verified"
            if question.validation_status != "passed":
                question.validation_status = "passed"
            if question.eligible_for_study is not True:
                question.eligible_for_study = True
            if question.eligible_for_cat is not True:
                question.eligible_for_cat = True
            if question.eligible_for_review is not True:
                question.eligible_for_review = True
            if question.issue_notes and "Inactive reserve after rebalance." in question.issue_notes:
                parts = [part.strip() for part in question.issue_notes.split(" | ") if part.strip() and part.strip() != "Inactive reserve after rebalance."]
                question.issue_notes = " | ".join(parts) or None

    active_after = sum(
        1
        for question in questions
        if question.active and question.content_status in SELECTABLE_CONTENT_STATUSES and not question.duplicate_of_question_id
    )
    replacement_active = sum(
        1
        for question in questions
        if question.active and is_replacement_bank_source(question.source_name) and question.content_status in SELECTABLE_CONTENT_STATUSES and not question.duplicate_of_question_id
    )
    messages.append(f"Deactivated {deactivated} figure-missing questions.")
    messages.append(f"Restored {restored} replacement-bank questions to active.")
    messages.append(f"Active after rebalance: {active_after} total, {replacement_active} from replacement banks.")

    db.commit()
    refreshed_questions = list(db.scalars(select(Question)).all())
    return AdminMaintenanceResult(
        status="completed",
        processed_count=processed,
        updated_count=updated,
        issue_count=updated,
        messages=messages,
        details=_pool_shape_report(refreshed_questions),
    )


def _section_summary_row(section: str, questions: list[Question]) -> SectionSummary:
    total_questions = len(questions)
    active_questions = sum(
        1
        for question in questions
        if question.active and question.content_status in SELECTABLE_CONTENT_STATUSES and not question.duplicate_of_question_id
    )
    verified_questions = sum(1 for question in questions if question.content_status == "verified")
    duplicate_questions = sum(1 for question in questions if question.content_status == "duplicate" or question.duplicate_of_question_id)
    needs_review_questions = sum(1 for question in questions if question.validation_status != "passed" or question.content_status in {"needs_review", "draft"})
    bad_questions = sum(1 for question in questions if question.content_status == "bad")
    average_difficulty = round(sum(question.difficulty_level for question in questions) / total_questions, 2) if total_questions else 0.0
    return SectionSummary(
        section=section,
        total_questions=total_questions,
        active_questions=active_questions,
        verified_questions=verified_questions,
        duplicate_questions=duplicate_questions,
        needs_review_questions=needs_review_questions,
        bad_questions=bad_questions,
        average_difficulty=average_difficulty,
    )


def build_dashboard_summary(db: Session) -> DashboardSummary:
    questions = list(db.scalars(select(Question)).all())
    by_section_map: dict[str, list[Question]] = defaultdict(list)
    for question in questions:
        by_section_map[question.section].append(question)

    by_section = [_section_summary_row(section, by_section_map.get(section, [])) for section in SECTION_REPORT_ORDER]
    if extra_sections := sorted(set(by_section_map) - set(SECTION_REPORT_ORDER)):
        by_section.extend(_section_summary_row(section, by_section_map[section]) for section in extra_sections)

    by_difficulty_rows = db.execute(
        select(Question.difficulty_level, func.count(Question.id)).group_by(Question.difficulty_level).order_by(Question.difficulty_level)
    ).all()
    by_difficulty = [
        {"difficulty_level": int(difficulty_level), "count": int(count or 0)}
        for difficulty_level, count in by_difficulty_rows
    ]

    active_questions = sum(
        1
        for question in questions
        if question.active and question.content_status in SELECTABLE_CONTENT_STATUSES and not question.duplicate_of_question_id
    )
    verified_questions = sum(1 for question in questions if question.content_status == "verified")
    duplicate_questions = sum(1 for question in questions if question.content_status == "duplicate" or question.duplicate_of_question_id)
    needs_review_questions = sum(1 for question in questions if question.validation_status != "passed" or question.content_status in {"needs_review", "draft"})
    bad_questions = sum(1 for question in questions if question.content_status == "bad")

    selectable_counts = {
        section: sum(
            1
            for question in by_section_map.get(section, [])
            if question.active and question.content_status in SELECTABLE_CONTENT_STATUSES and not question.duplicate_of_question_id
        )
        for section in SECTION_REPORT_ORDER
    }
    cat_ready = {
        "full_cat": all(selectable_counts.get(section, 0) >= target for section, target in CAT_BLUEPRINT_TARGETS.items()),
        "full_afqt": all(selectable_counts.get(section, 0) >= target for section, target in AFQT_BLUEPRINT_TARGETS.items()),
    }
    cat_ready.update({section: selectable_counts.get(section, 0) >= target for section, target in CAT_BLUEPRINT_TARGETS.items()})

    return DashboardSummary(
        total_questions=len(questions),
        active_questions=active_questions,
        verified_questions=verified_questions,
        duplicate_questions=duplicate_questions,
        needs_review_questions=needs_review_questions,
        bad_questions=bad_questions,
        by_section=by_section,
        by_difficulty=by_difficulty,
        cat_ready=cat_ready,
    )


def list_career_requirements(db: Session) -> list[CareerRequirementRead]:
    rows = list(
        db.scalars(
            select(CareerRequirement).where(CareerRequirement.active.is_(True)).order_by(CareerRequirement.branch, CareerRequirement.job_code)
        ).all()
    )
    return [CareerRequirementRead.model_validate(row) for row in rows]

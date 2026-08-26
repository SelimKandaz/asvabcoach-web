from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data_import.normalize_questions import canonical_hash_for_question
from app.models import Question, ResponseRecord, TestSession, UserQuestionStat
from app.services.bank_rules import (
    BANK_ROLE_REVIEW_ARCHIVE,
    BANK_ROLE_SCORE_SIMULATOR,
    normalize_bank_role,
)
from app.services.question_profile_service import question_profile_from_question
from app.services.repeat_policy import build_repeat_policy, get_user_answered_question_ids, get_user_seen_hash_records


SELECTABLE_CONTENT_STATUSES = {"verified", "active"}
PC_QUESTION_TYPES = {
    "main_idea",
    "direct_detail",
    "inference",
    "vocabulary_in_context",
    "author_purpose",
    "cause_effect",
}
MATH_SHARED_SECTIONS = {"AR", "MK"}


def _utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def effective_question_difficulty(question: Question) -> float:
    if question.calibrated_irt_b is not None:
        return float(question.calibrated_irt_b)
    return float(question.irt_b)


def effective_question_difficulty_level(question: Question) -> int:
    return int(question.difficulty_level)


def candidate_quality_key(question: Question) -> tuple[int, int, float, str]:
    return (
        1 if question.duplicate_of_question_id else 0,
        -(question.times_seen or 0),
        -(question.observed_correct_rate or 0.0),
        question.id,
    )


def dedupe_candidates_by_canonical_hash(candidates: list[Question]) -> list[Question]:
    winners: dict[str, Question] = {}
    fallback: list[Question] = []
    for question in candidates:
        canonical_hash = question.canonical_hash or canonical_hash_for_question(
            question.question_text,
            {
                "A": question.choice_a,
                "B": question.choice_b,
                "C": question.choice_c,
                "D": question.choice_d,
            },
        )
        if not canonical_hash:
            fallback.append(question)
            continue
        current = winners.get(canonical_hash)
        if current is None or candidate_quality_key(question) < candidate_quality_key(current):
            winners[canonical_hash] = question
    deduped = list(winners.values())
    deduped.extend(fallback)
    return deduped


def question_concept_tag(question: Question) -> str:
    if question.concept_tag:
        return question.concept_tag
    return question_profile_from_question(question).concept_tag


def question_template_family(question: Question) -> str:
    if question.template_family:
        return question.template_family
    return question_profile_from_question(question).template_family


def question_variant_signature(question: Question) -> str:
    if question.variant_signature:
        return question.variant_signature
    return question_profile_from_question(question).variant_signature


def question_type_value(question: Question) -> str:
    raw_type = (question.question_type or "").strip().lower()
    if raw_type and raw_type not in {"multiple_choice", "multiple choice", "mcq"}:
        return question.question_type or "general"
    if question.template_family:
        return question.template_family
    return question_concept_tag(question)


def question_passage_id(question: Question) -> str | None:
    return question.passage_id or None


def is_pc_drill_session(session: TestSession) -> bool:
    settings = session.settings or {}
    raw_filters = settings.get("section_filters", [])
    section_filters = [str(item).strip().upper() for item in raw_filters if str(item).strip()]
    return session.mode in {"study", "standard_quiz"} and len(section_filters) == 1 and section_filters[0] == "PC"


def get_candidate_questions(
    db: Session,
    *,
    section: str | None,
    excluded_question_ids: set[str],
    excluded_canonical_hashes: set[str],
    excluded_passage_ids: set[str],
    skill_filters: list[str],
    difficulty_filters: list[int],
    require_study_eligible: bool,
    require_cat_eligible: bool,
    require_review_eligible: bool,
    require_active: bool = True,
    required_bank_role: str | None = None,
    excluded_bank_roles: set[str] | None = None,
) -> list[Question]:
    statement = select(Question)
    if require_active:
        statement = statement.where(
            Question.active.is_(True),
            Question.content_status.in_(SELECTABLE_CONTENT_STATUSES),
            Question.duplicate_of_question_id.is_(None),
        )
    if required_bank_role:
        statement = statement.where(Question.bank_role == normalize_bank_role(required_bank_role))
    if excluded_bank_roles:
        normalized_roles = [normalize_bank_role(role) for role in excluded_bank_roles if normalize_bank_role(role)]
        if normalized_roles:
            statement = statement.where((Question.bank_role.is_(None)) | (Question.bank_role.not_in(normalized_roles)))
    if section:
        statement = statement.where(Question.section == section)
    if skill_filters:
        statement = statement.where(Question.skill_tag.in_(skill_filters))
    if difficulty_filters:
        statement = statement.where(
            Question.difficulty_level.in_(difficulty_filters)
        )
    if require_study_eligible:
        statement = statement.where(Question.eligible_for_study.is_(True))
    if require_cat_eligible:
        statement = statement.where(Question.eligible_for_cat.is_(True))
    if require_review_eligible:
        statement = statement.where(Question.eligible_for_review.is_(True))
    if excluded_question_ids:
        statement = statement.where(Question.id.not_in(excluded_question_ids))
    if excluded_canonical_hashes:
        statement = statement.where(
            (Question.canonical_hash.is_(None)) | (Question.canonical_hash.not_in(excluded_canonical_hashes))
        )
    if section == "PC" and excluded_passage_ids:
        statement = statement.where(
            (Question.passage_id.is_(None)) | (Question.passage_id.not_in(excluded_passage_ids))
        )
    return dedupe_candidates_by_canonical_hash(list(db.scalars(statement).all()))


def recent_profile_rows(db: Session, session_id: str, *, limit: int = 3) -> list[tuple[str, str, str, str]]:
    rows = list(
        db.execute(
            select(Question.skill_tag, Question.concept_tag, Question.template_family, Question.question_type)
            .join(ResponseRecord, ResponseRecord.question_id == Question.id)
            .where(ResponseRecord.session_id == session_id)
            .order_by(ResponseRecord.created_at.desc())
            .limit(limit)
        ).all()
    )
    def _normalize_question_type(question_type: str | None, template_family: str | None, concept_tag: str | None, skill_tag: str | None) -> str:
        raw_type = (question_type or "").strip().lower()
        if raw_type and raw_type not in {"multiple_choice", "multiple choice", "mcq"}:
            return question_type or "general"
        return template_family or concept_tag or skill_tag or "general"

    return [
        (
            skill_tag or "general",
            concept_tag or skill_tag or "general",
            template_family or "conceptual_definition",
            _normalize_question_type(question_type, template_family, concept_tag, skill_tag),
        )
        for skill_tag, concept_tag, template_family, question_type in rows
    ]


def answered_variant_signatures(db: Session, session_id: str) -> set[str]:
    return {
        value
        for value in db.scalars(
            select(Question.variant_signature)
            .join(ResponseRecord, ResponseRecord.question_id == Question.id)
            .where(ResponseRecord.session_id == session_id, Question.variant_signature.is_not(None))
        ).all()
        if value
    }


def get_user_variant_counts(db: Session, user_id: str) -> dict[str, int]:
    rows = db.execute(
        select(Question.variant_signature, func.count(ResponseRecord.id))
        .join(ResponseRecord, ResponseRecord.question_id == Question.id)
        .where(ResponseRecord.user_id == user_id, Question.variant_signature.is_not(None))
        .group_by(Question.variant_signature)
    ).all()
    return {str(variant_signature): int(count or 0) for variant_signature, count in rows if variant_signature}


def answered_passage_ids(db: Session, session_id: str) -> set[str]:
    return {
        value
        for value in db.scalars(
            select(Question.passage_id)
            .join(ResponseRecord, ResponseRecord.question_id == Question.id)
            .where(ResponseRecord.session_id == session_id, Question.passage_id.is_not(None))
        ).all()
        if value
    }


def answered_question_type_counts(db: Session, session_id: str) -> dict[str, int]:
    rows = db.execute(
        select(Question.question_type, Question.template_family, func.count(ResponseRecord.id))
        .join(ResponseRecord, ResponseRecord.question_id == Question.id)
        .where(ResponseRecord.session_id == session_id, Question.question_type.is_not(None))
        .group_by(Question.question_type, Question.template_family)
    ).all()
    counts: dict[str, int] = {}
    for question_type, template_family, count in rows:
        raw_type = (question_type or "").strip().lower()
        value = question_type if raw_type and raw_type not in {"multiple_choice", "multiple choice", "mcq"} else (template_family or question_type or "general")
        if not value:
            continue
        counts[str(value)] = int(count or 0)
    return counts


def get_user_wrong_concepts(db: Session, user_id: str) -> set[str]:
    return {
        concept_tag
        for concept_tag in db.scalars(
            select(Question.concept_tag)
            .join(ResponseRecord, ResponseRecord.question_id == Question.id)
            .where(ResponseRecord.user_id == user_id, ResponseRecord.is_correct.is_(False), Question.concept_tag.is_not(None))
        ).all()
        if concept_tag
    }


def filter_candidates_for_variety(
    candidates: list[Question],
    *,
    session_variant_signatures: set[str],
    session_passage_ids: set[str],
    session_question_type_counts: dict[str, int],
    recent_concepts: list[str],
    recent_templates: list[str],
    recent_question_types: list[str],
    allow_concept_repeats: bool,
    allow_passage_repeats: bool,
    prefer_question_type_diversity: bool,
) -> list[Question]:
    filtered = candidates
    if session_variant_signatures:
        alternate_variants = [
            question for question in filtered if question_variant_signature(question) not in session_variant_signatures
        ]
        if alternate_variants:
            filtered = alternate_variants
    if len(recent_templates) >= 2 and recent_templates[0] == recent_templates[1]:
        alternate_templates = [
            question for question in filtered if question_template_family(question) != recent_templates[0]
        ]
        if alternate_templates:
            filtered = alternate_templates
    if not allow_concept_repeats and len(recent_concepts) >= 2 and recent_concepts[0] == recent_concepts[1]:
        alternate_concepts = [
            question for question in filtered if question_concept_tag(question) != recent_concepts[0]
        ]
        if alternate_concepts:
            filtered = alternate_concepts
    if len(recent_question_types) >= 2 and recent_question_types[0] == recent_question_types[1]:
        alternate_types = [
            question for question in filtered if question_type_value(question) != recent_question_types[0]
        ]
        if alternate_types:
            filtered = alternate_types
    if prefer_question_type_diversity:
        missing_types = PC_QUESTION_TYPES.difference(session_question_type_counts)
        if missing_types:
            alternate_types = [
                question for question in filtered if question_type_value(question) in missing_types
            ]
            if alternate_types:
                filtered = alternate_types
    if not allow_passage_repeats and session_passage_ids:
        alternate_passages = [
            question for question in filtered if question_passage_id(question) not in session_passage_ids
        ]
        if alternate_passages:
            filtered = alternate_passages
    return filtered


def score_candidates(
    candidates: list[Question],
    *,
    theta: float,
    recent_skills: list[str],
    recent_concepts: list[str],
    recent_templates: list[str],
    recent_question_types: list[str],
    session_variant_signatures: set[str],
    session_passage_ids: set[str],
    session_question_type_counts: dict[str, int],
    user_variant_counts: dict[str, int],
    allow_concept_repeats: bool,
    allow_passage_repeats: bool,
    prefer_question_type_diversity: bool,
    user_stats: dict[str, UserQuestionStat],
    session_seed: str,
    preferred_review_hashes: set[str] | None = None,
    preferred_review_concepts: set[str] | None = None,
) -> list[tuple[Question, float]]:
    scored: list[tuple[Question, float]] = []
    skill_counts = defaultdict(int)
    for skill in recent_skills[-3:]:
        skill_counts[skill] += 1

    for index, question in enumerate(candidates):
        concept_tag = question_concept_tag(question)
        template_family = question_template_family(question)
        variant_signature = question_variant_signature(question)
        question_type = question_type_value(question)
        passage_id = question_passage_id(question)
        repeated_skill_penalty = 1.0 if skill_counts[question.skill_tag] >= 2 else 0.0
        repeated_template_penalty = 0.9 if len(recent_templates) >= 2 and recent_templates[0] == recent_templates[1] == template_family else 0.0
        repeated_type_penalty = 0.95 if len(recent_question_types) >= 2 and recent_question_types[0] == recent_question_types[1] == question_type else 0.0
        repeated_concept_penalty = (
            0.9
            if not allow_concept_repeats and len(recent_concepts) >= 2 and recent_concepts[0] == recent_concepts[1] == concept_tag
            else 0.0
        )
        question_type_count = session_question_type_counts.get(question_type, 0)
        repeated_variant_penalty = 1.1 if variant_signature in session_variant_signatures else 0.0
        repeated_passage_penalty = 1.4 if not allow_passage_repeats and passage_id and passage_id in session_passage_ids else 0.0
        question_type_diversity_adjustment = 0.0
        if prefer_question_type_diversity:
            if question_type_count == 0:
                question_type_diversity_adjustment = -1.05
            elif question_type_count == 1:
                question_type_diversity_adjustment = -0.35
            else:
                question_type_diversity_adjustment = min(0.9, (question_type_count - 1) * 0.25)
        user_variant_penalty = min(1.25, user_variant_counts.get(variant_signature, 0) * 0.18)
        user_stat = user_stats.get(question.id)
        seen_before_penalty = 0.75 if user_stat and user_stat.mastery_score > 0.75 else 0.25 if user_stat else 0.0
        review_bonus = 0.0
        if preferred_review_hashes:
            canonical_hash = question.canonical_hash or canonical_hash_for_question(
                question.question_text,
                {
                    "A": question.choice_a,
                    "B": question.choice_b,
                    "C": question.choice_c,
                    "D": question.choice_d,
                },
            )
            if canonical_hash in preferred_review_hashes:
                review_bonus = -0.65
        if preferred_review_concepts and concept_tag in preferred_review_concepts:
            review_bonus -= 0.35
        rng = random.Random(f"{session_seed}:{index}:{question.id}")
        random_small_noise = rng.uniform(0.0, 0.2)
        score = (
            abs(effective_question_difficulty(question) - theta) * 2.0
            - (question.irt_a * 0.75)
            + repeated_skill_penalty
            + repeated_template_penalty
            + repeated_type_penalty
            + repeated_concept_penalty
            + repeated_variant_penalty
            + repeated_passage_penalty
            + question_type_diversity_adjustment
            + user_variant_penalty
            + seen_before_penalty
            + review_bonus
            + random_small_noise
        )
        scored.append((question, score))
    scored.sort(key=lambda item: item[1])
    return scored


def select_next_question(db: Session, session: TestSession, section: str | None) -> Question | None:
    section_state = next((state for state in session.section_states if state.section == section), None)
    theta = section_state.theta_current if section_state else 0.0
    settings = session.settings or {}
    is_score_simulator = session.mode == "score_simulator"
    adaptive_group = str(settings.get("adaptive_group") or "").strip().lower()
    if section_state and adaptive_group:
        if adaptive_group == "math" and section in MATH_SHARED_SECTIONS:
            math_pressure = min(0.35, 0.18 + (0.015 * section_state.questions_answered))
            theta = min(3.0, theta + math_pressure)
        elif adaptive_group == str(section).strip().lower():
            section_pressure = min(0.28, 0.12 + (0.012 * section_state.questions_answered))
            theta = min(3.0, theta + section_pressure)
    answered_rows = list(
        db.execute(
            select(ResponseRecord.question_id, Question.canonical_hash)
            .join(Question, Question.id == ResponseRecord.question_id)
            .where(ResponseRecord.session_id == session.id)
        ).all()
    )
    answered_question_ids = {question_id for question_id, _ in answered_rows}
    if not bool(settings.get("review_only", False)) and not is_score_simulator:
        answered_question_ids.update(get_user_answered_question_ids(db, session.user_id))
    answered_canonical_hashes = {canonical_hash for _, canonical_hash in answered_rows if canonical_hash}
    seen_records = get_user_seen_hash_records(db, session.user_id)
    if is_score_simulator:
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=60)
        recent_seen_hashes = {
            record.canonical_hash
            for record in seen_records
            if record.canonical_hash and _utc_aware(record.last_seen_at) and _utc_aware(record.last_seen_at) >= recent_cutoff
        }
        excluded_seen_hashes = set()
    else:
        recent_seen_hashes = set()
        excluded_seen_hashes, preferred_review_hashes = build_repeat_policy(
            seen_records,
            allow_exact_repeats=bool(settings.get("allow_exact_repeats", settings.get("allow_repeats", False))),
            review_only=bool(settings.get("review_only", False)),
            review_wrong_questions_exact=bool(
                settings.get("review_wrong_questions_exact", settings.get("repeat_wrong_questions_in_review", False))
            ),
        )
    if is_score_simulator:
        preferred_review_hashes = set()
        excluded_canonical_hashes = answered_canonical_hashes.union(recent_seen_hashes)
    else:
        excluded_canonical_hashes = answered_canonical_hashes.union(excluded_seen_hashes)
    allow_concept_repeats = bool(
        settings.get("allow_concept_repeats")
        if settings.get("allow_concept_repeats") is not None
        else len(settings.get("skill_filters", [])) == 1
    )
    allow_passage_repeats = not (section == "PC" and not is_pc_drill_session(session))
    session_passage_ids = answered_passage_ids(db, session.id) if section == "PC" else set()
    session_question_type_counts = answered_question_type_counts(db, session.id) if section == "PC" else {}
    prefer_question_type_diversity = section == "PC" and not is_pc_drill_session(session)
    require_review_eligible = bool(settings.get("review_only", False))
    require_cat_eligible = session.mode in {"cat_simulation", "full_afqt_simulation"} and not is_score_simulator
    require_study_eligible = not require_review_eligible and not require_cat_eligible and not is_score_simulator

    if session.current_question_id:
        current_question = db.get(Question, session.current_question_id)
        if current_question is not None and not db.scalar(
            select(ResponseRecord.id).where(
                ResponseRecord.session_id == session.id,
                ResponseRecord.question_id == current_question.id,
            )
        ):
            return current_question

    candidates = get_candidate_questions(
        db,
        section=section,
        excluded_question_ids=answered_question_ids,
        excluded_canonical_hashes=excluded_canonical_hashes,
        excluded_passage_ids=session_passage_ids if not allow_passage_repeats else set(),
        skill_filters=settings.get("skill_filters", []),
        difficulty_filters=settings.get("difficulty_filters", []),
        require_study_eligible=require_study_eligible,
        require_cat_eligible=require_cat_eligible,
        require_review_eligible=require_review_eligible,
        require_active=not is_score_simulator,
        required_bank_role=BANK_ROLE_SCORE_SIMULATOR if is_score_simulator else None,
        excluded_bank_roles=set() if is_score_simulator else {BANK_ROLE_SCORE_SIMULATOR, BANK_ROLE_REVIEW_ARCHIVE},
    )
    if not candidates and section == "PC" and session_passage_ids and not allow_passage_repeats:
        candidates = get_candidate_questions(
            db,
            section=section,
            excluded_question_ids=answered_question_ids,
            excluded_canonical_hashes=excluded_canonical_hashes,
            excluded_passage_ids=set(),
            skill_filters=settings.get("skill_filters", []),
            difficulty_filters=settings.get("difficulty_filters", []),
            require_study_eligible=require_study_eligible,
            require_cat_eligible=require_cat_eligible,
            require_review_eligible=require_review_eligible,
            require_active=not is_score_simulator,
            required_bank_role=BANK_ROLE_SCORE_SIMULATOR if is_score_simulator else None,
            excluded_bank_roles=set() if is_score_simulator else {BANK_ROLE_SCORE_SIMULATOR, BANK_ROLE_REVIEW_ARCHIVE},
        )
    if not candidates:
        return None

    profile_rows = recent_profile_rows(db, session.id, limit=3)
    recent_skills = [skill for skill, _, _, _ in profile_rows]
    recent_concepts = [concept for _, concept, _, _ in profile_rows]
    recent_templates = [template for _, _, template, _ in profile_rows]
    recent_question_types = [question_type for _, _, _, question_type in profile_rows]
    session_variants = answered_variant_signatures(db, session.id)
    user_variant_counts = get_user_variant_counts(db, session.user_id)
    preferred_review_concepts = (
        get_user_wrong_concepts(db, session.user_id)
        if bool(settings.get("review_only", False)) and bool(settings.get("review_wrong_questions_similar", True))
        else set()
    )
    candidates = filter_candidates_for_variety(
        candidates,
        session_variant_signatures=session_variants,
        session_passage_ids=session_passage_ids,
        session_question_type_counts=session_question_type_counts,
        recent_concepts=recent_concepts,
        recent_templates=recent_templates,
        recent_question_types=recent_question_types,
        allow_concept_repeats=allow_concept_repeats,
        allow_passage_repeats=allow_passage_repeats,
        prefer_question_type_diversity=prefer_question_type_diversity,
    )
    user_stats = {
        stat.question_id: stat
        for stat in db.scalars(
            select(UserQuestionStat).where(UserQuestionStat.user_id == session.user_id)
        ).all()
    }
    return score_candidates(
        candidates,
        theta=theta,
        recent_skills=recent_skills,
        recent_concepts=recent_concepts,
        recent_templates=recent_templates,
        recent_question_types=recent_question_types,
        session_variant_signatures=session_variants,
        session_passage_ids=session_passage_ids,
        session_question_type_counts=session_question_type_counts,
        user_variant_counts=user_variant_counts,
        allow_concept_repeats=allow_concept_repeats,
        allow_passage_repeats=allow_passage_repeats,
        prefer_question_type_diversity=prefer_question_type_diversity,
        user_stats=user_stats,
        session_seed=session.id,
        preferred_review_hashes=preferred_review_hashes,
        preferred_review_concepts=preferred_review_concepts,
    )[0][0]

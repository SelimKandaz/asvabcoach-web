from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Question, ResponseRecord, SessionSectionState, SkillStat, TestSession, User, UserQuestionStat
from app.services.bank_rules import (
    BANK_ROLE_REVIEW_ARCHIVE,
    BANK_ROLE_SCORE_SIMULATOR,
)
from app.scoring.adaptive_engine import (
    answered_passage_ids,
    answered_question_type_counts,
    answered_variant_signatures,
    dedupe_candidates_by_canonical_hash,
    effective_question_difficulty,
    effective_question_difficulty_level,
    filter_candidates_for_variety,
    get_user_variant_counts,
    get_user_wrong_concepts,
    is_pc_drill_session,
    MATH_SHARED_SECTIONS,
    question_concept_tag,
    question_type_value,
    question_template_family,
    question_variant_signature,
    recent_profile_rows,
    score_candidates,
    select_next_question,
)
from app.scoring.irt import normal_cdf, probability_correct, theta_to_standard_score, update_theta
from app.schemas import AnswerFeedback, AnswerSubmission, SessionQuestion, SessionRead, SessionResults, SessionStartRequest
from app.services.explanation_service import build_local_explanation
from app.services.quiz_service import build_results_payload
from app.data_import.normalize_questions import SECTION_LABELS
from app.services.repeat_policy import (
    build_repeat_policy,
    get_user_answered_question_ids,
    get_user_seen_hash_records,
    record_user_seen_question,
)


AFQT_BLUEPRINT = [
    {"section": "AR", "count": 15},
    {"section": "WK", "count": 15},
    {"section": "PC", "count": 10},
    {"section": "MK", "count": 15},
]

CAT_BLUEPRINT = [
    {"section": "GS", "count": 15},
    {"section": "AR", "count": 15},
    {"section": "WK", "count": 15},
    {"section": "PC", "count": 10},
    {"section": "MK", "count": 15},
    {"section": "EI", "count": 15},
    {"section": "AI", "count": 10},
    {"section": "SI", "count": 10},
    {"section": "MC", "count": 15},
    {"section": "AO", "count": 15},
]

ADAPTIVE_MODES = {"study", "standard_quiz", "cat_simulation", "full_afqt_simulation", "score_simulator"}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _default_sections() -> list[str]:
    return ["AR", "MK", "WK", "PC", "GS", "EI", "AI", "AS", "SI", "MC", "AO"]


def _ensure_user(db: Session, display_name: str) -> User:
    user = db.scalar(select(User).where(User.display_name == display_name))
    if user:
        return user
    user = User(id=_new_id("usr"), display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _serialize_section_blueprint(request: SessionStartRequest) -> list[dict]:
    if request.mode in {"cat_simulation", "score_simulator"}:
        blueprint = CAT_BLUEPRINT
    elif request.mode == "full_afqt_simulation":
        blueprint = AFQT_BLUEPRINT
    else:
        blueprint = None

    if blueprint is not None:
        if request.section_order:
            desired_order = {section: index for index, section in enumerate(request.section_order)}
            return sorted(blueprint, key=lambda item: desired_order.get(item["section"], 999))
        return blueprint
    sections = request.section_filters or _default_sections()
    if not sections:
        sections = _default_sections()
    if request.question_count <= len(sections):
        return [{"section": section, "count": 1} for section in sections[: request.question_count]]
    base_count = request.question_count // len(sections)
    remainder = request.question_count % len(sections)
    blueprint = []
    for index, section in enumerate(sections):
        count = base_count + (1 if index < remainder else 0)
        blueprint.append({"section": section, "count": count})
    return blueprint


def _shared_theta_sections(session: TestSession, section: str | None) -> set[str]:
    settings = session.settings or {}
    if settings.get("adaptive_group") == "math" and section in MATH_SHARED_SECTIONS:
        return set(MATH_SHARED_SECTIONS)
    return {section} if section else set()


def _adaptive_pressure_for_section(session: TestSession, section: str | None, questions_answered: int) -> float:
    settings = session.settings or {}
    adaptive_group = str(settings.get("adaptive_group") or "").strip().lower()
    if not section or not adaptive_group:
        return 0.0
    section_key = section.strip().lower()
    if adaptive_group == "math" and section.upper() in MATH_SHARED_SECTIONS:
        return min(0.35, 0.18 + (0.015 * questions_answered))
    if adaptive_group == section_key:
        return min(0.28, 0.12 + (0.012 * questions_answered))
    return 0.0


def start_session(db: Session, request: SessionStartRequest) -> SessionRead:
    user = _ensure_user(db, request.display_name)
    blueprint = _serialize_section_blueprint(request)
    target_count = (
        sum(item["count"] for item in blueprint)
        if request.mode in {"cat_simulation", "full_afqt_simulation", "score_simulator"}
        else request.question_count
    )
    allow_concept_repeats = request.allow_concept_repeats if request.allow_concept_repeats is not None else len(request.skill_filters) == 1
    session = TestSession(
        id=_new_id("ses"),
        user_id=user.id,
        mode=request.mode,
        status="active",
        current_section=blueprint[0]["section"] if blueprint else None,
        target_question_count=target_count,
        settings={
            "section_filters": request.section_filters or [item["section"] for item in blueprint],
            "skill_filters": request.skill_filters,
            "difficulty_filters": request.difficulty_filters,
            "show_explanations_immediately": request.show_explanations_immediately,
            "blueprint": blueprint,
            "user_language": request.user_language,
            "review_only": request.review_only,
            "allow_repeats": request.allow_repeats,
            "allow_exact_repeats": request.allow_exact_repeats or request.allow_repeats,
            "allow_concept_repeats": allow_concept_repeats,
            "repeat_wrong_questions_in_review": request.repeat_wrong_questions_in_review,
            "review_wrong_questions_exact": request.review_wrong_questions_exact,
            "review_wrong_questions_similar": request.review_wrong_questions_similar,
            "adaptive_group": request.adaptive_group,
            "bank_role_mode": BANK_ROLE_SCORE_SIMULATOR if request.mode == "score_simulator" else None,
        },
    )
    db.add(session)
    for item in blueprint:
        db.add(
            SessionSectionState(
                id=_new_id("sec"),
                session_id=session.id,
                section=item["section"],
                theta_current=0.0,
                theta_start=0.0,
                questions_answered=0,
                correct_count=0,
                wrong_count=0,
                standard_score_estimate=50.0,
            )
        )
    db.commit()
    db.refresh(session)
    return SessionRead.model_validate(session)


def get_session_or_404(db: Session, session_id: str) -> TestSession:
    session = db.get(TestSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def _get_answered_count(db: Session, session_id: str) -> int:
    return int(db.scalar(select(func.count()).select_from(ResponseRecord).where(ResponseRecord.session_id == session_id)) or 0)


def _determine_next_section(session: TestSession) -> tuple[str | None, int]:
    blueprint = session.settings.get("blueprint", [])
    section_state_map = {state.section: state for state in session.section_states}
    for item in blueprint:
        state = section_state_map.get(item["section"])
        if state and state.questions_answered < item["count"]:
            return item["section"], item["count"]
    return None, 0


def _section_target_for(session: TestSession, section: str) -> int:
    for item in session.settings.get("blueprint", []):
        if item.get("section") == section:
            return int(item.get("count", 0))
    return 0


def _build_session_question(
    *,
    session: TestSession,
    question: Question,
    answered_count: int,
    section_target: int,
) -> SessionQuestion:
    section_state = next((state for state in session.section_states if state.section == question.section), None)
    section_theta = section_state.theta_current if section_state else None
    section_standard_score = section_state.standard_score_estimate if section_state else None
    section_percentile = section_state.percentile_estimate if section_state else None
    return SessionQuestion(
        session_id=session.id,
        question_id=question.id,
        prompt_number=answered_count + 1,
        progress_total=session.target_question_count,
        section=question.section,
        section_label=SECTION_LABELS.get(question.section, question.section),
        section_progress=(section_state.questions_answered + 1) if section_state else 1,
        section_target=section_target,
        skill_tag=question.skill_tag,
        skill_tags=question.skill_tags,
        concept_tag=question_concept_tag(question),
        question_type=question_type_value(question),
        subtype=question.subtype,
        template_family=question_template_family(question),
        variant_signature=question_variant_signature(question),
        difficulty_level=effective_question_difficulty_level(question),
        difficulty_num=question.difficulty_num,
        passage_id=question.passage_id,
        passage_topic=question.passage_topic,
        passage_text=question.passage_text,
        question_stem=question.question_stem,
        vocab_word=question.vocab_word,
        question_text=question.question_text,
        choices={
            "A": question.choice_a,
            "B": question.choice_b,
            "C": question.choice_c,
            "D": question.choice_d,
        },
        has_figure=bool(question.has_figure),
        figure_type=question.figure_type,
        figure_svg=question.figure_svg,
        figure_alt_text=question.figure_alt_text,
        asset_path=question.asset_path,
        section_theta=round(section_theta, 4) if section_theta is not None else None,
        section_standard_score_estimate=round(section_standard_score, 2) if section_standard_score is not None else None,
        section_percentile_estimate=round(section_percentile, 2) if section_percentile is not None else None,
        mode=session.mode,
        allow_backtracking=False if session.mode in {"cat_simulation", "full_afqt_simulation"} else True,
        show_immediate_explanation=bool(session.settings.get("show_explanations_immediately", True) and session.mode == "study"),
    )


def _pick_non_adaptive_question(db: Session, session: TestSession, section: str | None) -> Question | None:
    answered_ids = set(db.scalars(select(ResponseRecord.question_id).where(ResponseRecord.session_id == session.id)).all())
    is_score_simulator = session.mode == "score_simulator"
    if not bool(session.settings.get("review_only", False)) and not is_score_simulator:
        answered_ids.update(get_user_answered_question_ids(db, session.user_id))
    answered_canonical_hashes = set(
        db.scalars(
            select(Question.canonical_hash)
            .join(ResponseRecord, ResponseRecord.question_id == Question.id)
            .where(ResponseRecord.session_id == session.id, Question.canonical_hash.is_not(None))
        ).all()
    )
    seen_records = get_user_seen_hash_records(db, session.user_id)
    if is_score_simulator:
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=60)
        excluded_seen_hashes = {
            record.canonical_hash
            for record in seen_records
            if record.canonical_hash and _utc_aware(record.last_seen_at) and _utc_aware(record.last_seen_at) >= recent_cutoff
        }
        preferred_review_hashes = set()
    else:
        excluded_seen_hashes, preferred_review_hashes = build_repeat_policy(
            seen_records,
            allow_exact_repeats=bool(session.settings.get("allow_exact_repeats", session.settings.get("allow_repeats", False))),
            review_only=bool(session.settings.get("review_only", False)),
            review_wrong_questions_exact=bool(
                session.settings.get("review_wrong_questions_exact", session.settings.get("repeat_wrong_questions_in_review", False))
            ),
        )
    allow_passage_repeats = not (section == "PC" and not is_pc_drill_session(session))
    session_passage_ids = answered_passage_ids(db, session.id) if section == "PC" else set()
    session_question_type_counts = answered_question_type_counts(db, session.id) if section == "PC" else {}
    prefer_question_type_diversity = section == "PC" and not is_pc_drill_session(session)
    if is_score_simulator:
        statement = select(Question).where(Question.bank_role == BANK_ROLE_SCORE_SIMULATOR)
    else:
        statement = select(Question).where(
            Question.active.is_(True),
            Question.content_status.in_(("verified", "active")),
            Question.duplicate_of_question_id.is_(None),
        )
        statement = statement.where(
            Question.is_simulator.is_(False),
            Question.bank_role != BANK_ROLE_SCORE_SIMULATOR,
            Question.bank_role != BANK_ROLE_REVIEW_ARCHIVE,
        )
    if is_score_simulator:
        pass
    elif bool(session.settings.get("review_only", False)):
        statement = statement.where(Question.eligible_for_review.is_(True))
    elif session.mode in {"cat_simulation", "full_afqt_simulation"}:
        statement = statement.where(Question.eligible_for_cat.is_(True))
    else:
        statement = statement.where(Question.eligible_for_study.is_(True))
    if section:
        statement = statement.where(Question.section == section)
    if session.settings.get("skill_filters"):
        statement = statement.where(Question.skill_tag.in_(session.settings["skill_filters"]))
    if session.settings.get("difficulty_filters"):
        statement = statement.where(
            Question.difficulty_level.in_(session.settings["difficulty_filters"])
        )
    if answered_ids:
        statement = statement.where(Question.id.not_in(answered_ids))
    excluded_canonical_hashes = answered_canonical_hashes.union(excluded_seen_hashes)
    if excluded_canonical_hashes:
        statement = statement.where(
            (Question.canonical_hash.is_(None)) | (Question.canonical_hash.not_in(excluded_canonical_hashes))
        )
    if section == "PC" and session_passage_ids and not allow_passage_repeats:
        statement = statement.where(
            (Question.passage_id.is_(None)) | (Question.passage_id.not_in(session_passage_ids))
        )
    statement = statement.order_by(func.random())
    candidates = list(db.scalars(statement).all())
    if not candidates:
        if section == "PC" and session_passage_ids and not allow_passage_repeats:
            if is_score_simulator:
                statement = select(Question).where(Question.bank_role == BANK_ROLE_SCORE_SIMULATOR)
            else:
                statement = select(Question).where(
                    Question.active.is_(True),
                    Question.content_status.in_(("verified", "active")),
                    Question.duplicate_of_question_id.is_(None),
                )
                statement = statement.where(
                    Question.is_simulator.is_(False),
                    Question.bank_role != BANK_ROLE_SCORE_SIMULATOR,
                    Question.bank_role != BANK_ROLE_REVIEW_ARCHIVE,
                )
            if is_score_simulator:
                pass
            elif bool(session.settings.get("review_only", False)):
                statement = statement.where(Question.eligible_for_review.is_(True))
            elif session.mode in {"cat_simulation", "full_afqt_simulation"}:
                statement = statement.where(Question.eligible_for_cat.is_(True))
            else:
                statement = statement.where(Question.eligible_for_study.is_(True))
            if section:
                statement = statement.where(Question.section == section)
            if session.settings.get("skill_filters"):
                statement = statement.where(Question.skill_tag.in_(session.settings["skill_filters"]))
            if session.settings.get("difficulty_filters"):
                statement = statement.where(
                    Question.difficulty_level.in_(session.settings["difficulty_filters"])
                )
            if answered_ids:
                statement = statement.where(Question.id.not_in(answered_ids))
            if excluded_canonical_hashes:
                statement = statement.where(
                    (Question.canonical_hash.is_(None)) | (Question.canonical_hash.not_in(excluded_canonical_hashes))
                )
            statement = statement.order_by(func.random())
            candidates = list(db.scalars(statement).all())
        if preferred_review_hashes and bool(session.settings.get("review_only", False)):
            statement = select(Question).where(
                Question.active.is_(True),
                Question.content_status.in_(("verified", "active")),
                Question.duplicate_of_question_id.is_(None),
            )
            statement = statement.where(Question.eligible_for_review.is_(True))
            statement = statement.where(
                Question.is_simulator.is_(False),
                Question.bank_role != BANK_ROLE_SCORE_SIMULATOR,
                Question.bank_role != BANK_ROLE_REVIEW_ARCHIVE,
            )
            if section:
                statement = statement.where(Question.section == section)
            if session.settings.get("skill_filters"):
                statement = statement.where(Question.skill_tag.in_(session.settings["skill_filters"]))
            if answered_ids:
                statement = statement.where(Question.id.not_in(answered_ids))
            if answered_canonical_hashes:
                statement = statement.where(
                    (Question.canonical_hash.is_(None)) | (Question.canonical_hash.not_in(answered_canonical_hashes))
                )
            statement = statement.order_by(func.random())
            candidates = list(db.scalars(statement).all())
        if not candidates:
            return None

    candidates = dedupe_candidates_by_canonical_hash(candidates)
    profile_rows = recent_profile_rows(db, session.id, limit=3)
    recent_skills = [skill for skill, _, _, _ in profile_rows]
    recent_concepts = [concept for _, concept, _, _ in profile_rows]
    recent_templates = [template for _, _, template, _ in profile_rows]
    recent_question_types = [question_type for _, _, _, question_type in profile_rows]
    allow_concept_repeats = bool(
        session.settings.get("allow_concept_repeats")
        if session.settings.get("allow_concept_repeats") is not None
        else len(session.settings.get("skill_filters", [])) == 1
    )
    session_variants = answered_variant_signatures(db, session.id)
    user_variant_counts = get_user_variant_counts(db, session.user_id)
    preferred_review_concepts = (
        get_user_wrong_concepts(db, session.user_id)
        if bool(session.settings.get("review_only", False)) and bool(session.settings.get("review_wrong_questions_similar", True))
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
    preferred_candidate = next(
        (
            question
            for question in candidates
            if (question.canonical_hash or "") in preferred_review_hashes
        ),
        None,
    )
    if preferred_candidate is not None:
        return preferred_candidate
    return score_candidates(
        candidates,
        theta=0.0,
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
        session_seed=f"{session.id}:{section or 'all'}",
        preferred_review_hashes=preferred_review_hashes,
        preferred_review_concepts=preferred_review_concepts,
    )[0][0]


def get_next_question(db: Session, session_id: str) -> SessionQuestion | None:
    session = get_session_or_404(db, session_id)
    if session.status != "active":
        return None

    answered_count = _get_answered_count(db, session.id)
    if session.current_question_id:
        pending_question = db.get(Question, session.current_question_id)
        pending_answered = pending_question is not None and db.scalar(
            select(ResponseRecord.id).where(
                ResponseRecord.session_id == session.id,
                ResponseRecord.question_id == pending_question.id,
            )
        )
        if pending_question is not None and not pending_answered:
            section_target = _section_target_for(session, pending_question.section)
            return _build_session_question(
                session=session,
                question=pending_question,
                answered_count=answered_count,
                section_target=section_target,
            )
        session.current_question_id = None
        db.add(session)
        db.commit()

    if answered_count >= session.target_question_count:
        finish_session(db, session.id)
        return None

    section, section_target = _determine_next_section(session)
    if section is None:
        finish_session(db, session.id)
        return None

    if session.mode in ADAPTIVE_MODES:
        question = select_next_question(db, session, section)
    else:
        question = _pick_non_adaptive_question(db, session, section)

    if question is None:
        finish_session(db, session.id)
        return None

    session.current_section = section
    session.current_question_id = question.id
    db.add(session)
    db.commit()
    return _build_session_question(
        session=session,
        question=question,
        answered_count=answered_count,
        section_target=section_target,
    )


def _update_user_question_stat(db: Session, *, user_id: str, question: Question, is_correct: bool) -> None:
    stat = db.scalar(
        select(UserQuestionStat).where(
            UserQuestionStat.user_id == user_id,
            UserQuestionStat.question_id == question.id,
        )
    )
    if stat is None:
        stat = UserQuestionStat(
            id=_new_id("uqs"),
            user_id=user_id,
            question_id=question.id,
            times_seen=0,
            times_correct=0,
            times_wrong=0,
        )
    stat.times_seen += 1
    stat.times_correct += 1 if is_correct else 0
    stat.times_wrong += 0 if is_correct else 1
    stat.last_seen_at = datetime.now(timezone.utc)
    stat.mastery_score = round(stat.times_correct / max(stat.times_seen, 1), 4)
    stat.needs_review = stat.times_wrong >= stat.times_correct
    db.add(stat)


def _update_skill_stat(
    db: Session,
    *,
    user_id: str,
    question: Question,
    is_correct: bool,
    response_time_seconds: float,
) -> None:
    stat = db.scalar(
        select(SkillStat).where(
            SkillStat.user_id == user_id,
            SkillStat.section == question.section,
            SkillStat.skill_tag == question.skill_tag,
        )
    )
    if stat is None:
        stat = SkillStat(
            id=_new_id("sks"),
            user_id=user_id,
            section=question.section,
            skill_tag=question.skill_tag,
            attempts=0,
            correct=0,
            wrong=0,
            avg_response_time=0.0,
            mastery_score=0.0,
        )
    previous_attempts = stat.attempts
    stat.attempts += 1
    stat.correct += 1 if is_correct else 0
    stat.wrong += 0 if is_correct else 1
    stat.avg_response_time = round(
        ((stat.avg_response_time * previous_attempts) + response_time_seconds) / max(stat.attempts, 1),
        2,
    )
    stat.mastery_score = round(stat.correct / max(stat.attempts, 1), 4)
    db.add(stat)


def submit_answer(db: Session, session_id: str, submission: AnswerSubmission) -> AnswerFeedback:
    session = get_session_or_404(db, session_id)
    if session.status != "active":
        raise HTTPException(status_code=409, detail="Session is no longer active.")

    question = db.get(Question, submission.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")

    if session.current_question_id and session.current_question_id != question.id:
        raise HTTPException(status_code=409, detail="This is not the current pending question.")

    existing_response = db.scalar(
        select(ResponseRecord).where(
            ResponseRecord.session_id == session.id,
            ResponseRecord.question_id == question.id,
        )
    )
    if existing_response:
        raise HTTPException(status_code=409, detail="This question has already been answered in the session.")

    section_state = next((state for state in session.section_states if state.section == question.section), None)
    if section_state is None:
        raise HTTPException(status_code=400, detail="Question section is not part of this session.")

    is_correct = submission.selected_answer == question.correct_answer
    theta_before = section_state.theta_current
    effective_irt_b = effective_question_difficulty(question)
    effective_level = effective_question_difficulty_level(question)
    expected_probability = probability_correct(theta_before, question.irt_a, effective_irt_b, question.irt_c)
    learning_rate = 0.45 + _adaptive_pressure_for_section(session, question.section, section_state.questions_answered)
    theta_after = update_theta(theta_before, is_correct, question.irt_a, effective_irt_b, question.irt_c, learning_rate=learning_rate)

    response = ResponseRecord(
        id=_new_id("rsp"),
        session_id=session.id,
        question_id=question.id,
        user_id=session.user_id,
        section=question.section,
        selected_answer=submission.selected_answer,
        correct_answer=question.correct_answer,
        is_correct=is_correct,
        response_time_seconds=submission.response_time_seconds,
        theta_before=theta_before,
        theta_after=theta_after,
        expected_probability=expected_probability,
        difficulty_level=effective_level,
        irt_a=question.irt_a,
        irt_b=effective_irt_b,
        irt_c=question.irt_c,
    )
    db.add(response)

    section_state.theta_current = theta_after
    section_state.questions_answered += 1
    section_state.correct_count += 1 if is_correct else 0
    section_state.wrong_count += 0 if is_correct else 1
    section_state.standard_score_estimate = theta_to_standard_score(theta_after)
    section_state.percentile_estimate = round(normal_cdf((section_state.standard_score_estimate - 50.0) / 10.0) * 100.0, 2)
    db.add(section_state)

    shared_sections = _shared_theta_sections(session, question.section)
    if len(shared_sections) > 1:
        for shared_state in session.section_states:
            if shared_state.section == question.section:
                continue
            if shared_state.section not in shared_sections:
                continue
            shared_state.theta_current = theta_after
            shared_state.standard_score_estimate = section_state.standard_score_estimate
            shared_state.percentile_estimate = section_state.percentile_estimate
            db.add(shared_state)

    _update_user_question_stat(db, user_id=session.user_id, question=question, is_correct=is_correct)
    _update_skill_stat(
        db,
        user_id=session.user_id,
        question=question,
        is_correct=is_correct,
        response_time_seconds=submission.response_time_seconds,
    )
    record_user_seen_question(db, user_id=session.user_id, question=question, is_correct=is_correct)
    previous_seen = question.times_seen or 0
    question.times_seen = previous_seen + 1
    question.times_correct = (question.times_correct or 0) + (1 if is_correct else 0)
    previous_rate = question.observed_correct_rate if question.observed_correct_rate is not None else None
    if previous_rate is None:
        question.observed_correct_rate = 1.0 if is_correct else 0.0
    else:
        question.observed_correct_rate = round(
            ((previous_rate * previous_seen) + (1.0 if is_correct else 0.0)) / max(question.times_seen, 1),
            4,
        )
    question.empirical_accuracy = round((question.times_correct or 0) / max(question.times_seen, 1), 4)
    if question.average_response_time_seconds is None:
        question.average_response_time_seconds = float(submission.response_time_seconds)
    else:
        question.average_response_time_seconds = round(
            ((question.average_response_time_seconds * previous_seen) + float(submission.response_time_seconds))
            / max(question.times_seen, 1),
            2,
        )
    question.avg_time_sec = question.average_response_time_seconds
    question.calibrated_difficulty_num = float(question.calibrated_difficulty_level or question.difficulty_level)
    db.add(question)

    completed = _get_answered_count(db, session.id) + 1 >= session.target_question_count
    session.current_question_id = None
    if completed:
        session.status = "completed"
        session.finished_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()

    if completed:
        results = build_results_payload(db, session)
        session.final_report = results.model_dump(mode="json")
        db.add(session)
        db.commit()

    explanation = build_local_explanation(question, submission.selected_answer)
    show_explanation_now = (
        session.mode == "study"
        or bool(session.settings.get("show_explanations_immediately", False))
        or completed
    )

    return AnswerFeedback(
        question_id=question.id,
        selected_answer=submission.selected_answer,
        correct_answer=question.correct_answer,
        is_correct=is_correct,
        explanation=explanation["simple_explanation"] if show_explanation_now else None,
        quick_method=explanation["quick_method"] if show_explanation_now else None,
        wrong_answer_reason=explanation["wrong_answer_reasons"].get(submission.selected_answer) if show_explanation_now and not is_correct else None,
        theta_before=round(theta_before, 4),
        theta_after=round(theta_after, 4),
        expected_probability=round(expected_probability, 4),
        session_completed=completed,
        results_available=completed,
    )


def finish_session(db: Session, session_id: str) -> SessionResults:
    session = get_session_or_404(db, session_id)
    if session.status != "completed":
        session.status = "completed"
        session.finished_at = datetime.now(timezone.utc)
        session.current_question_id = None
        db.add(session)
        db.commit()

    results = build_results_payload(db, session)
    session.final_report = results.model_dump(mode="json")
    db.add(session)
    db.commit()
    return results


def get_results(db: Session, session_id: str) -> SessionResults:
    session = get_session_or_404(db, session_id)
    if session.final_report:
        return SessionResults(**session.final_report)
    return finish_session(db, session_id)

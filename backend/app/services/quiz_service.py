from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Question, ResponseRecord, SessionSectionState, TestSession, UserQuestionStat
from app.scoring.afqt_estimator import (
    calculate_afqt_confidence,
    calculate_afqt_raw,
    calculate_readiness_confidence,
    calculate_readiness_score,
    calculate_percentile_estimate,
    calculate_percentile_range,
    calculate_weighted_accuracy,
    calculate_standard_scores_from_theta,
    calculate_ve_estimate,
)
from app.scoring.irt import normal_cdf, theta_to_standard_score
from app.scoring.line_scores import calculate_gt_estimate
from app.schemas import (
    DifficultyPerformance,
    SectionPerformance,
    SessionResults,
    SkillPerformance,
)


SECTION_REPORT_ORDER = ["GS", "AR", "WK", "PC", "MK", "EI", "AI", "AS", "SI", "MC", "AO"]
AFQT_COVERED_SECTIONS = {"AR", "WK", "PC", "MK"}
SELECTABLE_CONTENT_STATUSES = {"verified", "active"}


def _round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _strict_sum(values: list[float | None]) -> float | None:
    if any(value is None for value in values):
        return None
    return round(sum(float(value) for value in values), 2)


def _session_section_state_map(session: TestSession) -> dict[str, SessionSectionState]:
    return {state.section: state for state in session.section_states}


def _blueprint_for_session(session: TestSession) -> list[dict]:
    blueprint = session.settings.get("blueprint")
    if isinstance(blueprint, list) and blueprint:
        return blueprint
    return [{"section": section, "count": 0} for section in SECTION_REPORT_ORDER]


def _section_target_map(session: TestSession) -> dict[str, int]:
    return {item.get("section"): int(item.get("count", 0)) for item in _blueprint_for_session(session)}


def _is_blueprint_complete(session: TestSession) -> bool:
    blueprint = _blueprint_for_session(session)
    if not blueprint:
        return False
    state_map = _session_section_state_map(session)
    for item in blueprint:
        section = item.get("section")
        target = int(item.get("count", 0))
        state = state_map.get(section)
        if state is None or state.questions_answered < target:
            return False
    return True


def _calculate_section_rows(session: TestSession) -> tuple[
    list[SectionPerformance],
    dict[str, float | None],
    dict[str, float | None],
    dict[str, float | None],
]:
    state_map = _session_section_state_map(session)
    theta_map: dict[str, float | None] = {}
    standard_score_estimates: dict[str, float | None] = {}
    standard_scores: dict[str, float | None] = {
        section: None for section in SECTION_REPORT_ORDER
    }
    section_rows: list[SectionPerformance] = []

    for section in SECTION_REPORT_ORDER:
        state = state_map.get(section)
        if state is None:
            section_rows.append(
                SectionPerformance(
                    section=section,
                    questions_answered=0,
                    correct_count=0,
                    wrong_count=0,
                    accuracy=0.0,
                    theta=None,
                    standard_score_estimate=None,
                    percentile_estimate=None,
                )
            )
            theta_map[section] = None
            standard_score_estimates[section] = None
            continue

        theta = _round_or_none(state.theta_current, 4)
        standard_score = _round_or_none(theta_to_standard_score(state.theta_current), 2)
        percentile = _round_or_none(normal_cdf((standard_score - 50.0) / 10.0) * 100.0 if standard_score is not None else None, 2)
        theta_map[section] = theta
        standard_score_estimates[section] = standard_score
        standard_scores[section] = standard_score
        section_rows.append(
            SectionPerformance(
                section=section,
                questions_answered=state.questions_answered,
                correct_count=state.correct_count,
                wrong_count=state.wrong_count,
                accuracy=round(state.correct_count / state.questions_answered, 4) if state.questions_answered else 0.0,
                theta=theta,
                standard_score_estimate=standard_score,
                percentile_estimate=percentile,
            )
        )

    return section_rows, theta_map, standard_score_estimates, standard_scores


def _calculate_skill_rows(db: Session, session: TestSession) -> list[SkillPerformance]:
    rows = db.execute(
        select(
            Question.section,
            Question.skill_tag,
            func.count(ResponseRecord.id),
            func.sum(case((ResponseRecord.is_correct.is_(True), 1), else_=0)),
        )
        .join(Question, Question.id == ResponseRecord.question_id)
        .where(ResponseRecord.session_id == session.id)
        .group_by(Question.section, Question.skill_tag)
        .order_by(Question.section, Question.skill_tag)
    ).all()

    results: list[SkillPerformance] = []
    for section, skill_tag, attempts, correct in rows:
        attempts_count = int(attempts or 0)
        correct_count = int(correct or 0)
        wrong_count = max(0, attempts_count - correct_count)
        accuracy = round(correct_count / attempts_count, 4) if attempts_count else 0.0
        results.append(
            SkillPerformance(
                section=section,
                skill_tag=skill_tag,
                attempts=attempts_count,
                correct=correct_count,
                wrong=wrong_count,
                accuracy=accuracy,
            )
        )
    results.sort(key=lambda item: (item.accuracy, -item.attempts, item.section, item.skill_tag))
    return results


def _calculate_difficulty_rows(db: Session, session: TestSession) -> list[DifficultyPerformance]:
    rows = db.execute(
        select(
            Question.difficulty_level,
            func.count(ResponseRecord.id),
            func.sum(case((ResponseRecord.is_correct.is_(True), 1), else_=0)),
        )
        .join(Question, Question.id == ResponseRecord.question_id)
        .where(ResponseRecord.session_id == session.id)
        .group_by(Question.difficulty_level)
        .order_by(Question.difficulty_level)
    ).all()

    results: list[DifficultyPerformance] = []
    for difficulty_level, attempts, correct in rows:
        attempts_count = int(attempts or 0)
        correct_count = int(correct or 0)
        wrong_count = max(0, attempts_count - correct_count)
        accuracy = round(correct_count / attempts_count, 4) if attempts_count else 0.0
        results.append(
            DifficultyPerformance(
                difficulty_level=int(difficulty_level),
                attempts=attempts_count,
                correct=correct_count,
                wrong=wrong_count,
                accuracy=accuracy,
            )
        )
    return results


def _completed_session_accuracy(db: Session, completed_session: TestSession) -> float | None:
    if completed_session.final_report and isinstance(completed_session.final_report, dict):
        report_accuracy = completed_session.final_report.get("accuracy")
        if report_accuracy is not None:
            try:
                return round(float(report_accuracy), 4)
            except (TypeError, ValueError):
                return None

    total = int(
        db.scalar(
            select(func.count()).select_from(ResponseRecord).where(ResponseRecord.session_id == completed_session.id)
        )
        or 0
    )
    if total <= 0:
        return None
    correct = int(
        db.scalar(
            select(func.count())
            .select_from(ResponseRecord)
            .where(ResponseRecord.session_id == completed_session.id, ResponseRecord.is_correct.is_(True))
        )
        or 0
    )
    return round(correct / total, 4)


def _calculate_readiness_metrics(
    db: Session,
    session: TestSession,
    response_rows: list[tuple[ResponseRecord, Question]],
    accuracy: float,
) -> tuple[float | None, str | None]:
    if not response_rows:
        return None, None

    answer_rows = [(response.difficulty_level, response.is_correct) for response, _ in response_rows]
    weighted_accuracy = calculate_weighted_accuracy(answer_rows)
    if weighted_accuracy is None:
        weighted_accuracy = accuracy

    afqt_rows = [(response, question) for response, question in response_rows if question.section in AFQT_COVERED_SECTIONS]
    afqt_section_coverage = len({question.section for _, question in afqt_rows}) / float(len(AFQT_COVERED_SECTIONS))
    afqt_question_coverage = min(1.0, len(afqt_rows) / 55.0)
    coverage_factor = round((afqt_section_coverage * 0.45) + (afqt_question_coverage * 0.55), 4)

    difficulty_levels = [response.difficulty_level for response, _ in response_rows if response.difficulty_level is not None]
    if difficulty_levels:
        avg_difficulty = sum(difficulty_levels) / len(difficulty_levels)
        difficulty_factor = max(0.85, min(1.05, 0.86 + ((avg_difficulty - 2.5) * 0.07)))
    else:
        difficulty_factor = 0.9

    prior_sessions = list(
        db.scalars(
            select(TestSession)
            .where(
                TestSession.user_id == session.user_id,
                TestSession.id != session.id,
                TestSession.status == "completed",
            )
            .order_by(TestSession.finished_at.desc().nullslast(), TestSession.started_at.desc())
            .limit(3)
        ).all()
    )
    prior_accuracies = [value for value in (_completed_session_accuracy(db, item) for item in prior_sessions) if value is not None]
    if prior_accuracies:
        avg_prior_accuracy = sum(prior_accuracies) / len(prior_accuracies)
        spread = max(prior_accuracies) - min(prior_accuracies) if len(prior_accuracies) > 1 else 0.0
        consistency_factor = max(0.85, min(1.05, 0.86 + (avg_prior_accuracy * 0.16) - (spread * 0.12)))
    else:
        consistency_factor = 0.9

    expected_ratio_rows: list[float] = []
    for response, question in response_rows:
        expected_time = question.expected_time_sec or max(20, question.difficulty_level * 35)
        if expected_time <= 0 or response.response_time_seconds <= 0:
            continue
        expected_ratio_rows.append(expected_time / max(response.response_time_seconds, 1.0))
    if expected_ratio_rows:
        avg_ratio = sum(expected_ratio_rows) / len(expected_ratio_rows)
        time_factor = max(0.85, min(1.05, 1.0 + ((avg_ratio - 1.0) * 0.12)))
    else:
        time_factor = 1.0

    readiness_score = calculate_readiness_score(
        weighted_accuracy=weighted_accuracy,
        coverage_factor=coverage_factor,
        difficulty_factor=difficulty_factor,
        consistency_factor=consistency_factor,
        time_factor=time_factor,
    )
    readiness_confidence = calculate_readiness_confidence(
        readiness_score=readiness_score,
        coverage_factor=coverage_factor,
        consistency_factor=consistency_factor,
        time_factor=time_factor,
    )
    return readiness_score, readiness_confidence


def _build_composite_rows(standard_scores: dict[str, float | None]) -> tuple[
    dict[str, dict[str, float | None]],
    dict[str, list[dict[str, float | int | str | None]]],
]:
    ve = standard_scores.get("VE")
    ar = standard_scores.get("AR")
    wk = standard_scores.get("WK")
    pc = standard_scores.get("PC")
    mk = standard_scores.get("MK")
    gs = standard_scores.get("GS")
    ei = standard_scores.get("EI")
    ai = standard_scores.get("AI")
    si = standard_scores.get("SI")
    mc = standard_scores.get("MC")
    ao = standard_scores.get("AO")
    as_score = standard_scores.get("AS") if standard_scores.get("AS") is not None else standard_scores.get("AS_COMPOSITE")

    army_rows = [
        {"label": "GT", "formula": "VE + AR", "score": _strict_sum([ve, ar])},
        {"label": "CL", "formula": "VE + AR + MK", "score": _strict_sum([ve, ar, mk])},
        {"label": "CO", "formula": "VE + AS + MC", "score": _strict_sum([ve, as_score, mc])},
        {"label": "EL", "formula": "GS + AR + MK + EI", "score": _strict_sum([gs, ar, mk, ei])},
        {"label": "FA", "formula": "AR + MK + MC", "score": _strict_sum([ar, mk, mc])},
        {"label": "GM", "formula": "GS + AS + MK + EI", "score": _strict_sum([gs, as_score, mk, ei])},
        {"label": "MM", "formula": "AS + MC + EI", "score": _strict_sum([as_score, mc, ei])},
        {"label": "OF", "formula": "VE + AS + MC", "score": _strict_sum([ve, as_score, mc])},
        {"label": "SC", "formula": "VE + AR + AS + MC", "score": _strict_sum([ve, ar, as_score, mc])},
        {"label": "ST", "formula": "GS + VE + MK + MC", "score": _strict_sum([gs, ve, mk, mc])},
    ]
    air_force_rows = [
        {"label": "M", "formula": "AR + AS + MC + VE", "score": _strict_sum([ar, as_score, mc, ve])},
        {"label": "A", "formula": "MK + VE", "score": _strict_sum([mk, ve])},
        {"label": "G", "formula": "AR + VE", "score": _strict_sum([ar, ve])},
        {"label": "E", "formula": "AR + EI + GS + MK", "score": _strict_sum([ar, ei, gs, mk])},
    ]
    navy_rows = [
        {"label": "GT", "formula": "VE + AR", "score": _strict_sum([ve, ar])},
        {"label": "EL", "formula": "GS + AR + MK + EI", "score": _strict_sum([gs, ar, mk, ei])},
        {"label": "BEE", "formula": "AR + GS + MK + MK", "score": _strict_sum([ar, gs, mk, mk])},
        {"label": "ENG", "formula": "AS + MK", "score": _strict_sum([as_score, mk])},
        {"label": "MEC", "formula": "AR + AS + MC", "score": _strict_sum([ar, as_score, mc])},
        {"label": "MEC2", "formula": "AO + AR + MC", "score": _strict_sum([ao, ar, mc])},
        {"label": "NUC", "formula": "AR + MC + MK + VE", "score": _strict_sum([ar, mc, mk, ve])},
        {"label": "OPS", "formula": "AR + MK + AO", "score": _strict_sum([ar, mk, ao])},
        {"label": "HM", "formula": "GS + MK + VE", "score": _strict_sum([gs, mk, ve])},
        {"label": "ADM", "formula": "MK + VE", "score": _strict_sum([mk, ve])},
    ]
    marine_rows = [
        {"label": "MM", "formula": "MC + EI + AS", "score": _strict_sum([mc, ei, as_score])},
        {"label": "GT", "formula": "VE + AR", "score": _strict_sum([ve, ar])},
        {"label": "EL", "formula": "GS + AR + MK + EI", "score": _strict_sum([gs, ar, mk, ei])},
        {"label": "CL", "formula": "VE + MK", "score": _strict_sum([ve, mk])},
    ]

    composite_scores = {
        "Army": {row["label"]: row["score"] for row in army_rows},
        "Air Force": {row["label"]: row["score"] for row in air_force_rows},
        "Navy": {row["label"]: row["score"] for row in navy_rows},
        "Marines": {row["label"]: row["score"] for row in marine_rows},
    }
    composite_rows = {
        "Army": army_rows,
        "Air Force": air_force_rows,
        "Navy": navy_rows,
        "Marines": marine_rows,
    }
    return composite_scores, composite_rows


def identify_weak_skills(db: Session, user_id: str) -> list[str]:
    stats = list(
        db.scalars(
            select(UserQuestionStat)
            .where(UserQuestionStat.user_id == user_id)
            .order_by(UserQuestionStat.mastery_score.asc(), UserQuestionStat.times_seen.desc())
            .limit(24)
        ).all()
    )
    if not stats:
        return []

    question_map = {
        question.id: question
        for question in db.scalars(select(Question).where(Question.id.in_([stat.question_id for stat in stats]))).all()
    }

    weak_skills: list[str] = []
    for stat in stats:
        question = question_map.get(stat.question_id)
        if question is None:
            continue
        if stat.mastery_score >= 0.8 and stat.times_seen >= 3:
            continue
        weak_skills.append(f"{question.section}: {question.skill_tag}")
    seen: set[str] = set()
    ordered = []
    for item in weak_skills:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered[:8]


def build_results_payload(db: Session, session: TestSession) -> SessionResults:
    response_rows = list(
        db.execute(
            select(ResponseRecord, Question)
            .join(Question, Question.id == ResponseRecord.question_id)
            .where(ResponseRecord.session_id == session.id)
            .order_by(ResponseRecord.created_at.asc())
        ).all()
    )

    total_answered = len(response_rows)
    correct_count = sum(1 for response, _ in response_rows if response.is_correct)
    wrong_count = total_answered - correct_count
    accuracy = round(correct_count / total_answered, 4) if total_answered else 0.0

    by_section, theta_map, standard_score_estimates, standard_scores = _calculate_section_rows(session)
    standard_score_updates = calculate_standard_scores_from_theta(
        {section: theta for section, theta in theta_map.items() if theta is not None}
    )
    standard_scores.update(standard_score_updates)

    ve_score = calculate_ve_estimate(standard_scores.get("WK"), standard_scores.get("PC"))
    if ve_score is not None:
        standard_scores["VE"] = ve_score
    as_score = standard_scores.get("AS")
    if as_score is None and standard_scores.get("AS_COMPOSITE") is not None:
        standard_scores["AS"] = standard_scores["AS_COMPOSITE"]
    elif as_score is None and standard_scores.get("AI") is not None and standard_scores.get("SI") is not None:
        standard_scores["AS"] = round((float(standard_scores["AI"]) + float(standard_scores["SI"])) / 2.0, 2)

    composite_scores, composite_rows = _build_composite_rows(standard_scores)

    estimated_gt_score = calculate_gt_estimate(standard_scores.get("AR"), standard_scores.get("WK"), standard_scores.get("PC"))
    afqt_raw = calculate_afqt_raw(standard_scores.get("AR"), standard_scores.get("MK"), ve_score)
    estimated_afqt_percentile = calculate_percentile_estimate(afqt_raw)
    estimated_afqt_range = calculate_percentile_range(estimated_afqt_percentile)

    session_blueprint_complete = _is_blueprint_complete(session)
    excluded_bad_questions = int(
        db.scalar(
            select(func.count()).select_from(Question).where(
                (Question.active.is_(False))
                | (Question.content_status.not_in(SELECTABLE_CONTENT_STATUSES))
                | (Question.duplicate_of_question_id.is_not(None))
            )
        )
        or 0
    )
    all_questions = max(1, int(db.scalar(select(func.count()).select_from(Question)) or 0))
    bad_ratio = excluded_bad_questions / all_questions
    branch_confidence = calculate_afqt_confidence(
        answered_sections=sum(1 for state in session.section_states if state.questions_answered > 0),
        scored_questions=total_answered,
        excluded_bad_questions=excluded_bad_questions,
        full_blueprint_complete=session_blueprint_complete,
    )

    branch_warnings: list[str] = []
    if not session_blueprint_complete:
        branch_warnings.append("The official blueprint was not fully completed in this run.")
    if excluded_bad_questions:
        branch_warnings.append(f"{excluded_bad_questions} low-trust questions were excluded from the active pool.")
    if bad_ratio > 0.1:
        branch_warnings.append("A large share of the bank is filtered out for quality reasons.")
    if any(standard_scores.get(section) is None for section in ["AR", "WK", "PC", "MK"]):
        branch_warnings.append("AFQT confidence is limited because one or more AFQT sections are missing.")
    if any(standard_scores.get(section) is None for section in ["GS", "EI", "AI", "AS", "SI", "MC", "AO"]):
        branch_warnings.append("Full ASVAB composites are partially estimated because some non-AFQT sections are missing.")
    if session.mode == "score_simulator":
        branch_warnings.append("Score simulator results use the dedicated simulator bank and are not official ASVAB scores.")

    readiness_score, readiness_confidence = _calculate_readiness_metrics(db, session, response_rows, accuracy)

    weak_skills = identify_weak_skills(db, session.user_id)
    recommended_next_practice = weak_skills[:5] if weak_skills else [
        "Rotate through mixed sections and keep drilling your missed concepts."
    ]
    wrong_question_ids = [question.id for response, question in response_rows if not response.is_correct]

    return SessionResults(
        session_id=session.id,
        mode=session.mode,
        total_answered=total_answered,
        question_count=session.target_question_count,
        correct_count=correct_count,
        wrong_count=wrong_count,
        accuracy=accuracy,
        by_section=by_section,
        by_skill=_calculate_skill_rows(db, session),
        by_difficulty=_calculate_difficulty_rows(db, session),
        theta_estimates=theta_map,
        standard_score_estimates=standard_score_estimates,
        standard_scores=standard_scores,
        composite_scores=composite_scores,
        composite_rows=composite_rows,
        readiness_score=readiness_score,
        readiness_confidence=readiness_confidence,
        estimated_afqt_range=estimated_afqt_range,
        estimated_afqt_percentile=estimated_afqt_percentile,
        afqt_confidence=branch_confidence,
        estimated_gt_score=estimated_gt_score,
        weak_skills=weak_skills,
        recommended_next_practice=recommended_next_practice,
        wrong_question_ids=wrong_question_ids,
        excluded_bad_questions=excluded_bad_questions,
        report_label="Score Simulator Report" if session.mode == "score_simulator" else "Estimated ASVAB-Style Score Report",
        report_date=datetime.utcnow(),
        warning_text=" ".join(branch_warnings) if branch_warnings else None,
        branch_confidence_warnings=branch_warnings,
    )

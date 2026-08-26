from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.database import get_db
from app.models import ResponseRecord, SkillStat, TestSession, UserQuestionStat
from app.schemas import MistakeReviewItem, ProgressPoint, SectionMemoryStat, SkillStatRead, StatsOverview
from app.services.explanation_service import build_local_explanation
from app.services.quiz_service import identify_weak_skills
from app.models import Question
from app.data_import.normalize_questions import SECTION_LABELS


router = APIRouter(prefix="/stats", tags=["stats"])


def _resolve_user_id(db: Session, user_id: str | None) -> str | None:
    if user_id:
        return user_id
    return db.scalar(select(TestSession.user_id).order_by(TestSession.started_at.desc()).limit(1))


@router.get("/overview", response_model=StatsOverview)
def overview(user_id: str | None = None, db: Session = Depends(get_db)) -> StatsOverview:
    resolved_user_id = _resolve_user_id(db, user_id)
    if resolved_user_id is None:
        return StatsOverview(total_sessions=0, questions_answered=0, accuracy=0.0, needs_review_count=0, weak_skills=[])

    total_sessions = int(
        db.scalar(select(func.count()).select_from(TestSession).where(TestSession.user_id == resolved_user_id)) or 0
    )
    responses = list(
        db.scalars(select(ResponseRecord).where(ResponseRecord.user_id == resolved_user_id)).all()
    )
    questions_answered = len(responses)
    correct = sum(1 for response in responses if response.is_correct)
    accuracy = round(correct / questions_answered, 4) if questions_answered else 0.0
    needs_review_count = int(
        db.scalar(
            select(func.count()).select_from(UserQuestionStat).where(
                UserQuestionStat.user_id == resolved_user_id,
                UserQuestionStat.needs_review.is_(True),
            )
        )
        or 0
    )
    return StatsOverview(
        total_sessions=total_sessions,
        questions_answered=questions_answered,
        accuracy=accuracy,
        needs_review_count=needs_review_count,
        weak_skills=identify_weak_skills(db, resolved_user_id),
    )


@router.get("/section-memory", response_model=list[SectionMemoryStat])
def section_memory(user_id: str | None = None, db: Session = Depends(get_db)) -> list[SectionMemoryStat]:
    resolved_user_id = _resolve_user_id(db, user_id)
    if resolved_user_id is None:
        return []

    rows = db.execute(
        select(
            ResponseRecord.section,
            func.count(ResponseRecord.id),
            func.sum(case((ResponseRecord.is_correct.is_(True), 1), else_=0)),
            func.max(ResponseRecord.created_at),
        )
        .where(ResponseRecord.user_id == resolved_user_id)
        .group_by(ResponseRecord.section)
    ).all()

    stats_by_section: dict[str, SectionMemoryStat] = {}
    for section, attempts, correct, last_answered_at in rows:
        attempts_count = int(attempts or 0)
        correct_count = int(correct or 0)
        wrong_count = max(0, attempts_count - correct_count)
        stats_by_section[section] = SectionMemoryStat(
            section=section,
            section_label=SECTION_LABELS.get(section, section),
            attempts=attempts_count,
            correct=correct_count,
            wrong=wrong_count,
            accuracy=round(correct_count / attempts_count, 4) if attempts_count else 0.0,
            last_answered_at=last_answered_at,
        )

    ordered_sections = list(SECTION_LABELS.keys())
    ordered_items = [stats_by_section[section] for section in ordered_sections if section in stats_by_section]
    remaining_sections = sorted(
        (section for section in stats_by_section.keys() if section not in SECTION_LABELS),
        key=lambda item: item,
    )
    ordered_items.extend(stats_by_section[section] for section in remaining_sections)
    return ordered_items


@router.get("/skills", response_model=list[SkillStatRead])
def skills(user_id: str | None = None, db: Session = Depends(get_db)) -> list[SkillStatRead]:
    resolved_user_id = _resolve_user_id(db, user_id)
    if resolved_user_id is None:
        return []
    stats = list(
        db.scalars(
            select(SkillStat).where(SkillStat.user_id == resolved_user_id).order_by(SkillStat.mastery_score.asc())
        ).all()
    )
    return [
        SkillStatRead(
            section=stat.section,
            skill_tag=stat.skill_tag,
            attempts=stat.attempts,
            correct=stat.correct,
            wrong=stat.wrong,
            avg_response_time=stat.avg_response_time,
            mastery_score=stat.mastery_score,
        )
        for stat in stats
    ]


@router.get("/mistakes", response_model=list[MistakeReviewItem])
def mistakes(user_id: str | None = None, db: Session = Depends(get_db)) -> list[MistakeReviewItem]:
    resolved_user_id = _resolve_user_id(db, user_id)
    if resolved_user_id is None:
        return []
    rows = db.execute(
        select(ResponseRecord, Question)
        .join(Question, Question.id == ResponseRecord.question_id)
        .where(ResponseRecord.user_id == resolved_user_id, ResponseRecord.is_correct.is_(False))
        .order_by(ResponseRecord.created_at.desc())
        .limit(100)
    ).all()
    items: list[MistakeReviewItem] = []
    for response, question in rows:
        explanation = build_local_explanation(question, response.selected_answer)
        items.append(
            MistakeReviewItem(
                question=question,
                selected_answer=response.selected_answer,
                correct_answer=response.correct_answer,
                explanation=explanation["simple_explanation"],
                quick_method=explanation["quick_method"],
            )
        )
    return items


@router.get("/progress", response_model=list[ProgressPoint])
def progress(user_id: str | None = None, db: Session = Depends(get_db)) -> list[ProgressPoint]:
    resolved_user_id = _resolve_user_id(db, user_id)
    if resolved_user_id is None:
        return []
    sessions = list(
        db.scalars(
            select(TestSession).where(TestSession.user_id == resolved_user_id).order_by(TestSession.started_at.desc()).limit(25)
        ).all()
    )
    items: list[ProgressPoint] = []
    for session in sessions:
        report = session.final_report or {}
        items.append(
            ProgressPoint(
                session_id=session.id,
                mode=session.mode,
                started_at=session.started_at,
                accuracy=float(report.get("accuracy", 0.0)),
            )
        )
    return items

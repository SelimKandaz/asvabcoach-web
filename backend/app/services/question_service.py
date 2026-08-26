from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Question
from app.schemas import QuestionUpdate
from app.services.bank_rules import (
    BANK_ROLE_PUBLIC_PC_IMPORT,
    BANK_ROLE_REVIEW_ARCHIVE,
    BANK_ROLE_SCORE_SIMULATOR,
    normalize_bank_role,
)


SELECTABLE_CONTENT_STATUSES = {"active", "verified"}


def list_questions(
    db: Session,
    *,
    section: str | None = None,
    skill: str | None = None,
    difficulty: int | None = None,
    bank_role: str | None = None,
    source_bank: str | None = None,
    needs_review: bool | None = None,
    simulator_only: bool = False,
    public_import_only: bool = False,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[Question]]:
    statement = select(Question)
    count_statement = select(func.count()).select_from(Question)
    normalized_bank_role = normalize_bank_role(bank_role) if bank_role else None
    include_inactive_simulator_pool = simulator_only or normalized_bank_role == BANK_ROLE_SCORE_SIMULATOR
    include_inactive_review_archive = normalized_bank_role == BANK_ROLE_REVIEW_ARCHIVE

    if section:
        statement = statement.where(Question.section == section)
        count_statement = count_statement.where(Question.section == section)
    if skill:
        statement = statement.where(Question.skill_tag == skill)
        count_statement = count_statement.where(Question.skill_tag == skill)
    if difficulty:
        statement = statement.where(Question.difficulty_level == difficulty)
        count_statement = count_statement.where(Question.difficulty_level == difficulty)
    if normalized_bank_role:
        statement = statement.where(Question.bank_role == normalized_bank_role)
        count_statement = count_statement.where(Question.bank_role == normalized_bank_role)
    if source_bank:
        statement = statement.where(Question.source_bank == source_bank)
        count_statement = count_statement.where(Question.source_bank == source_bank)
    if needs_review is not None:
        statement = statement.where(Question.needs_review.is_(needs_review))
        count_statement = count_statement.where(Question.needs_review.is_(needs_review))
    if simulator_only:
        statement = statement.where(
            (Question.bank_role == BANK_ROLE_SCORE_SIMULATOR) | Question.is_simulator.is_(True)
        )
        count_statement = count_statement.where(
            (Question.bank_role == BANK_ROLE_SCORE_SIMULATOR) | Question.is_simulator.is_(True)
        )
    elif public_import_only:
        statement = statement.where(
            (Question.bank_role == BANK_ROLE_PUBLIC_PC_IMPORT) | Question.is_public_import.is_(True)
        )
        count_statement = count_statement.where(
            (Question.bank_role == BANK_ROLE_PUBLIC_PC_IMPORT) | Question.is_public_import.is_(True)
        )
    if active_only and not include_inactive_simulator_pool and not include_inactive_review_archive:
        statement = statement.where(
            Question.active.is_(True),
            Question.content_status.in_(SELECTABLE_CONTENT_STATUSES),
            Question.duplicate_of_question_id.is_(None),
            Question.is_simulator.is_(False),
            Question.bank_role != BANK_ROLE_SCORE_SIMULATOR,
            Question.bank_role != BANK_ROLE_REVIEW_ARCHIVE,
        )
        count_statement = count_statement.where(
            Question.active.is_(True),
            Question.content_status.in_(SELECTABLE_CONTENT_STATUSES),
            Question.duplicate_of_question_id.is_(None),
            Question.is_simulator.is_(False),
            Question.bank_role != BANK_ROLE_SCORE_SIMULATOR,
            Question.bank_role != BANK_ROLE_REVIEW_ARCHIVE,
        )

    total = int(db.scalar(count_statement) or 0)
    items = list(
        db.scalars(statement.order_by(Question.section, Question.skill_tag).offset(offset).limit(limit)).all()
    )
    return total, items


def get_question_or_none(db: Session, question_id: str) -> Question | None:
    return db.get(Question, question_id)


def update_question(db: Session, question: Question, payload: QuestionUpdate) -> Question:
    for field_name, value in payload.model_dump(exclude_none=True).items():
        setattr(question, field_name, value)
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def deactivate_question(db: Session, question: Question) -> Question:
    question.active = False
    question.content_status = "bad"
    db.add(question)
    db.commit()
    db.refresh(question)
    return question

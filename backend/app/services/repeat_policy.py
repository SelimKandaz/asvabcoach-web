from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data_import.normalize_questions import canonical_hash_for_question
from app.models import Question, ResponseRecord, UserSeenQuestionHash


def get_user_seen_hash_records(db: Session, user_id: str) -> list[UserSeenQuestionHash]:
    return list(db.scalars(select(UserSeenQuestionHash).where(UserSeenQuestionHash.user_id == user_id)).all())


def get_user_answered_question_ids(db: Session, user_id: str) -> set[str]:
    return set(db.scalars(select(ResponseRecord.question_id).where(ResponseRecord.user_id == user_id)).all())


def build_repeat_policy(
    records: list[UserSeenQuestionHash],
    *,
    allow_exact_repeats: bool,
    review_only: bool,
    review_wrong_questions_exact: bool,
) -> tuple[set[str], set[str]]:
    all_seen = {record.canonical_hash for record in records if record.canonical_hash}
    correct_seen = {record.canonical_hash for record in records if record.canonical_hash and record.times_correct > record.times_wrong}
    wrong_seen = {record.canonical_hash for record in records if record.canonical_hash and record.times_wrong > 0}

    if allow_exact_repeats:
        if review_only and review_wrong_questions_exact:
            return set(), wrong_seen
        return set(), set()

    if review_only and review_wrong_questions_exact:
        return correct_seen, wrong_seen

    return all_seen, set()


def record_user_seen_question(
    db: Session,
    *,
    user_id: str,
    question: Question,
    is_correct: bool,
) -> UserSeenQuestionHash:
    canonical_hash = question.canonical_hash or canonical_hash_for_question(
        question.question_text,
        {
            "A": question.choice_a,
            "B": question.choice_b,
            "C": question.choice_c,
            "D": question.choice_d,
        },
    )
    record = db.scalar(
        select(UserSeenQuestionHash).where(
            UserSeenQuestionHash.user_id == user_id,
            UserSeenQuestionHash.canonical_hash == canonical_hash,
        )
    )
    now = datetime.now(timezone.utc)
    if record is None:
        record = UserSeenQuestionHash(
            id=f"usq_{question.id}_{user_id}".replace("-", "_")[:64],
            user_id=user_id,
            canonical_hash=canonical_hash,
            question_id=question.id,
            first_seen_at=now,
            last_seen_at=now,
            times_seen=0,
            times_correct=0,
            times_wrong=0,
        )
    record.question_id = question.id
    record.last_seen_at = now
    record.times_seen += 1
    if is_correct:
        record.times_correct += 1
    else:
        record.times_wrong += 1
    db.add(record)
    return record

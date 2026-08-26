from __future__ import annotations

from hashlib import sha1
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AIExplanationCache, Question
from app.services.openai_service import OpenAIService


def build_local_explanation(question: Question, selected_answer: str | None = None) -> dict:
    wrong_map = {
        "A": question.wrong_a_explanation,
        "B": question.wrong_b_explanation,
        "C": question.wrong_c_explanation,
        "D": question.wrong_d_explanation,
    }
    return {
        "simple_explanation": question.base_explanation or "Review the stem, eliminate weak distractors, and confirm the final choice.",
        "quick_method": question.quick_method or "Look for the strongest evidence before locking the answer.",
        "why_correct": question.base_explanation or f"The correct answer is {question.correct_answer}.",
        "wrong_answer_reasons": {
            key: value or "This option does not match the best-supported answer."
            for key, value in wrong_map.items()
        },
        "test_taking_tip": "Use elimination first, then confirm the best answer with the stem.",
        "selected_answer_reason": wrong_map.get(selected_answer or "", None),
    }


def get_or_create_ai_explanation(
    db: Session,
    *,
    question: Question,
    selected_answer: str | None,
    user_language: str,
) -> tuple[dict, bool]:
    cache_key = sha1(f"{question.id}:{selected_answer}:{user_language}".encode("utf-8")).hexdigest()
    cached = db.scalar(select(AIExplanationCache).where(AIExplanationCache.cache_key == cache_key))
    if cached:
        return cached.payload, True

    openai_service = OpenAIService()
    fallback = build_local_explanation(question, selected_answer)
    if not openai_service.enabled:
        return fallback, False

    payload = {
        "question_text": question.question_text,
        "choices": {
            "A": question.choice_a,
            "B": question.choice_b,
            "C": question.choice_c,
            "D": question.choice_d,
        },
        "correct_answer": question.correct_answer,
        "selected_answer": selected_answer,
        "base_explanation": question.base_explanation,
        "user_language": user_language,
    }
    ai_payload = openai_service.explain_question(payload) or fallback
    cache_entry = AIExplanationCache(
        id=f"aic_{uuid4().hex[:12]}",
        cache_key=cache_key,
        question_id=question.id,
        selected_answer=selected_answer,
        user_language=user_language,
        payload=ai_payload,
    )
    db.add(cache_entry)
    db.commit()
    return ai_payload, False


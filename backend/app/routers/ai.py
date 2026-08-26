from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Question
from app.schemas import (
    AIExplainRequest,
    AIExplainResponse,
    AIGenerateSimilarRequest,
    AIGenerateSimilarResponse,
    GeneratedQuestionCandidate,
    StudyReportRequest,
    StudyReportResponse,
)
from app.services.explanation_service import get_or_create_ai_explanation
from app.services.openai_service import OpenAIService
from app.services.session_service import get_session_or_404
from app.services.quiz_service import build_results_payload


router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/explain-question", response_model=AIExplainResponse)
def explain_question(payload: AIExplainRequest, db: Session = Depends(get_db)) -> AIExplainResponse:
    question = db.get(Question, payload.question_id) if payload.question_id else None
    if question is not None:
        explanation, cached = get_or_create_ai_explanation(
            db,
            question=question,
            selected_answer=payload.selected_answer,
            user_language=payload.user_language,
        )
    else:
        explanation = {
            "simple_explanation": payload.base_explanation or "Review the question carefully and eliminate weak distractors.",
            "quick_method": "Use elimination, then verify the strongest answer.",
            "why_correct": f"The best answer is {payload.correct_answer}.",
            "wrong_answer_reasons": {
                key: "This choice is less supported by the prompt." for key in payload.choices
            },
            "test_taking_tip": "Watch for wording traps before locking your answer.",
        }
        cached = False

    return AIExplainResponse(
        simple_explanation=explanation["simple_explanation"],
        quick_method=explanation.get("quick_method"),
        why_correct=explanation["why_correct"],
        wrong_answer_reasons=explanation["wrong_answer_reasons"],
        test_taking_tip=explanation["test_taking_tip"],
        cached=cached,
    )


@router.post("/generate-similar", response_model=AIGenerateSimilarResponse)
def generate_similar(payload: AIGenerateSimilarRequest) -> AIGenerateSimilarResponse:
    service = OpenAIService()
    generated = service.generate_similar_questions(payload.model_dump()) if service.enabled else None
    if generated is None:
        generated = [
            {
                "question_text": f"Practice variant: {payload.source_question_text}",
                "choices": payload.choices,
                "correct_answer": payload.correct_answer,
                "explanation": "Placeholder similar question. Enable OpenAI to generate fresh variants.",
                "skill_tag": payload.skill_tag,
                "difficulty_level": payload.difficulty_level,
                "needs_review": True,
            }
            for _ in range(payload.requested_count)
        ]
    return AIGenerateSimilarResponse(
        items=[GeneratedQuestionCandidate(**item) for item in generated[: payload.requested_count]],
        used_openai=service.enabled,
    )


@router.post("/study-report", response_model=StudyReportResponse)
def study_report(payload: StudyReportRequest, db: Session = Depends(get_db)) -> StudyReportResponse:
    session = get_session_or_404(db, payload.session_id)
    results = build_results_payload(db, session)
    service = OpenAIService()
    report = service.build_study_report(results.model_dump()) if service.enabled else None
    if report is None:
        report = (
            f"Accuracy: {round(results.accuracy * 100, 1)}%. "
            f"Weak skills: {', '.join(results.weak_skills) if results.weak_skills else 'none yet'}. "
            f"Next practice: {', '.join(results.recommended_next_practice) if results.recommended_next_practice else 'keep building reps across mixed sections'}."
        )
    return StudyReportResponse(report=report, used_openai=service.enabled)


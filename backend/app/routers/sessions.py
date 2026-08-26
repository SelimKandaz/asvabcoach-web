from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AnswerFeedback, AnswerSubmission, SessionQuestion, SessionRead, SessionResults, SessionStartRequest
from app.services.session_service import finish_session, get_next_question, get_results, get_session_or_404, start_session, submit_answer


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/start", response_model=SessionRead)
def start(request: SessionStartRequest, db: Session = Depends(get_db)) -> SessionRead:
    return start_session(db, request)


@router.get("/{session_id}", response_model=SessionRead)
def get_session(session_id: str, db: Session = Depends(get_db)) -> SessionRead:
    return SessionRead.model_validate(get_session_or_404(db, session_id))


@router.get("/{session_id}/next-question", response_model=SessionQuestion | None)
def next_question(session_id: str, db: Session = Depends(get_db)) -> SessionQuestion | None:
    return get_next_question(db, session_id)


@router.post("/{session_id}/answer", response_model=AnswerFeedback)
def answer(session_id: str, submission: AnswerSubmission, db: Session = Depends(get_db)) -> AnswerFeedback:
    return submit_answer(db, session_id, submission)


@router.post("/{session_id}/finish", response_model=SessionResults)
def finish(session_id: str, db: Session = Depends(get_db)) -> SessionResults:
    return finish_session(db, session_id)


@router.get("/{session_id}/results", response_model=SessionResults)
def results(session_id: str, db: Session = Depends(get_db)) -> SessionResults:
    return get_results(db, session_id)


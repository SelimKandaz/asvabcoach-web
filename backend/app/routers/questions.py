from __future__ import annotations

from pathlib import Path, PureWindowsPath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.data_import.import_questions import import_question_file
from app.schemas import ImportResult, QuestionListResponse, QuestionRead, QuestionUpdate
from app.services.question_service import deactivate_question, get_question_or_none, list_questions, update_question


router = APIRouter(prefix="/questions", tags=["questions"])
settings = get_settings()


def _resolve_import_source_path(source_path: str) -> Path:
    raw_path = source_path.strip()
    candidates = [Path(raw_path).expanduser()]

    if len(raw_path) >= 3 and raw_path[1] == ":" and raw_path[2] in {"\\", "/"}:
        windows_path = PureWindowsPath(raw_path)
        if len(windows_path.parts) >= 4 and str(windows_path.parts[1]).lower() == "users":
            mapped = Path("/host/userprofile", *windows_path.parts[3:])
            candidates.append(mapped)

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    attempted = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"File not found. Tried: {attempted}")


@router.get("", response_model=QuestionListResponse)
def get_questions(
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
    db: Session = Depends(get_db),
) -> QuestionListResponse:
    total, items = list_questions(
        db,
        section=section,
        skill=skill,
        difficulty=difficulty,
        bank_role=bank_role,
        source_bank=source_bank,
        needs_review=needs_review,
        simulator_only=simulator_only,
        public_import_only=public_import_only,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return QuestionListResponse(total=total, items=items)


@router.get("/{question_id}", response_model=QuestionRead)
def get_question(question_id: str, db: Session = Depends(get_db)) -> QuestionRead:
    question = get_question_or_none(db, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    return QuestionRead.model_validate(question)


@router.post("/import", response_model=ImportResult)
async def import_questions(
    source_path: str | None = Form(default=None),
    upload: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> ImportResult:
    if upload is None and not source_path:
        raise HTTPException(status_code=400, detail="Provide either an uploaded file or a source path.")

    if upload is not None:
        suffix = Path(upload.filename or "upload.xlsx").suffix
        temp_path = settings.upload_dir / f"{uuid4().hex}{suffix}"
        temp_path.write_bytes(await upload.read())
        file_path = temp_path.resolve()
    else:
        try:
            file_path = _resolve_import_source_path(source_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        log = import_question_file(file_path, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportResult(
        log_id=log.id,
        source_name=log.source_name,
        imported_count=log.imported_count,
        updated_count=log.updated_count,
        skipped_count=log.skipped_count,
        failed_count=log.failed_count,
        status=log.status,
        messages=log.details.get("messages", []),
    )


@router.patch("/{question_id}", response_model=QuestionRead)
def patch_question(question_id: str, payload: QuestionUpdate, db: Session = Depends(get_db)) -> QuestionRead:
    question = get_question_or_none(db, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    updated = update_question(db, question, payload)
    return QuestionRead.model_validate(updated)


@router.post("/{question_id}/deactivate", response_model=QuestionRead)
def post_deactivate_question(question_id: str, db: Session = Depends(get_db)) -> QuestionRead:
    question = get_question_or_none(db, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    updated = deactivate_question(db, question)
    return QuestionRead.model_validate(updated)

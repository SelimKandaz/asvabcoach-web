from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import admin, ai, answers, questions, sessions, stats


settings = get_settings()
settings.question_assets_dir.mkdir(parents=True, exist_ok=True)
app = FastAPI(title=settings.app_name, version="0.1.0")

app.mount(
    "/api/question-assets",
    StaticFiles(directory=settings.question_assets_dir),
    name="question-assets",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _wait_for_database() -> None:
    last_error: Exception | None = None
    for _ in range(15):
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2)
    if last_error:
        raise last_error


@app.on_event("startup")
def on_startup() -> None:
    _wait_for_database()
    init_db()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "ASVAB Coach API is running."}


app.include_router(questions.router, prefix=settings.api_prefix)
app.include_router(sessions.router, prefix=settings.api_prefix)
app.include_router(answers.router, prefix=settings.api_prefix)
app.include_router(stats.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(ai.router, prefix=settings.api_prefix)

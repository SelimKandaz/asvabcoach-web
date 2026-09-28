# ASVAB Coach

A web app for ASVAB-style studying and practice tests. Scoring is deterministic, practice sessions adapt to you, and results include estimated AFQT and GT-style scores. AI explanations are optional.

## Features

- Study, quiz, adaptive test, AFQT estimate, and review modes
- Admin tools and question bank import from XLSX, CSV, or JSON
- Optional AI provider (local or hosted) for richer explanations and similar questions, never used for scoring

## Run

```bash
cp .env.example .env
docker compose up --build
```

- App: http://localhost:5173
- API docs: http://localhost:8000/docs

Import the question bank:

```bash
docker compose exec backend python -m app.data_import.import_questions /app/app/data/asvab_style_question_database_v0_1.xlsx
```

Built with FastAPI, SQLAlchemy, PostgreSQL, React, Vite, and Docker Compose.

## Note

Scores are practice estimates, not official ASVAB scores.

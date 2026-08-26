# ASVAB Coach

ASVAB Coach is a browser-first ASVAB-style study and simulation platform with deterministic scoring, adaptive practice sessions, approximate AFQT and GT-style reporting, and optional AI-assisted learning support.

## What is included

- FastAPI backend with SQLAlchemy models and deterministic scoring
- React + Vite frontend with study, quiz, CAT, AFQT, review, and admin flows
- PostgreSQL and Docker Compose for local development and Linux deployment
- XLSX, CSV, and JSON import pipeline for the existing question bank
- Optional AI provider endpoints for richer explanations and similar practice questions

## Included data

This repo includes the safe, shareable question-bank data and assets that help the app run and be audited:

- `backend/app/data/asvab_style_question_database_v0_1.json`
- `backend/app/data/asvab_style_question_database_v0_1.xlsx`
- `backend/app/data/asvab_generated_10000_question_bank_v0_2.csv`
- `backend/app/data/replacement_banks/*.json`
- `backend/app/data/question_assets/**.svg`

It intentionally excludes environment files, runtime uploads, import logs, local backups, and other transient work outputs.

## Start locally

1. Copy [.env.example](.env.example) to `.env`.
2. Update database credentials if needed.
3. Run:

```bash
docker compose up --build
```

## Import the question database

### Option 1: copy into the app data directory

Copy the file into:

`backend/app/data/asvab_style_question_database_v0_1.xlsx`

Then run:

```bash
docker compose exec backend python -m app.data_import.import_questions /app/app/data/asvab_style_question_database_v0_1.xlsx
```

### Option 2: mount Windows Downloads into Docker

Add a volume to the `backend` service in [docker-compose.yml](docker-compose.yml):

```yaml
volumes:
  - ./backend/app/data:/app/app/data
  - C:/Users/selim/Downloads:/host-downloads:ro
```

Then run:

```bash
docker compose exec backend python -m app.data_import.import_questions /host-downloads/asvab_style_question_database_v0_1.xlsx
```

## Optional AI provider

The app works with its built-in explanations by default. For richer explanations, similar questions, and study reports, you can connect a local AI server or a hosted provider with a compatible chat endpoint. Put the provider settings in `.env`:

```env
AI_ENABLED=true
AI_API_KEY=your_api_key_here
AI_BASE_URL=http://host.docker.internal:1234/v1
AI_MODEL=local-model
```

For a local provider that does not require a key, leave `AI_API_KEY` empty. For a hosted provider, set its API key and base URL there. Then restart the backend:

```bash
docker compose up -d --build backend
```

The app still runs without an external provider. AI endpoints return graceful fallback content when the feature is disabled or unavailable.

## Access the app

- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Adminer: [http://localhost:8080](http://localhost:8080)

## Deploy to an R520 Linux server

1. Install Docker Engine and Docker Compose plugin.
2. Copy the whole project folder to the server.
3. Copy `.env` and the question data file.
4. Run:

```bash
docker compose up -d --build
```

5. Keep the `postgres_data` volume persistent.
6. Back up PostgreSQL regularly:

```bash
docker run --rm \
  --volumes-from $(docker compose ps -q postgres) \
  -v $(pwd):/backup \
  alpine \
  tar czf /backup/postgres_data_backup.tar.gz /var/lib/postgresql/data
```

## Notes

- The app does not claim official ASVAB scores.
- Results are labeled as estimated practice metrics.
- Scoring is deterministic and owned by the backend.
- External AI assistance is optional and never used for grading or official score claims.

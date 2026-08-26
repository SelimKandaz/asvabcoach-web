from __future__ import annotations

import json

from app.database import SessionLocal, init_db
from app.services.quality_service import dedupe_questions


def main() -> None:
    init_db()
    with SessionLocal() as db:
        result = dedupe_questions(db)
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

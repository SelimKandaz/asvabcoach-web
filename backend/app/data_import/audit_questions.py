from __future__ import annotations

import json

from app.database import SessionLocal, init_db
from app.services.quality_service import audit_questions


def main() -> None:
    init_db()
    with SessionLocal() as db:
        issues = audit_questions(db)
        print(json.dumps([issue.model_dump() for issue in issues], indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json

from app.database import SessionLocal, init_db
from app.services.quality_service import rebalance_question_bank as rebalance_question_bank_in_db


def main() -> None:
    init_db()
    with SessionLocal() as db:
        result = rebalance_question_bank_in_db(db)
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

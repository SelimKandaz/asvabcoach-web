from __future__ import annotations

import json

from app.database import SessionLocal, init_db
from app.services.research_service import match_observations


def main() -> None:
    init_db()
    with SessionLocal() as db:
        result = match_observations(db)
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

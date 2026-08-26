from __future__ import annotations

import json

from app.database import SessionLocal, init_db
from app.services.research_service import recalibrate_from_external_observations


def main() -> None:
    init_db()
    with SessionLocal() as db:
        result = recalibrate_from_external_observations(db)
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

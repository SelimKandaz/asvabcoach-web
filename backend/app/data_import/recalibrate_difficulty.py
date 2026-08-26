from __future__ import annotations

import json

from app.database import SessionLocal, init_db
from app.services.quality_service import recalibrate_difficulties


def main() -> None:
    init_db()
    with SessionLocal() as db:
        result = recalibrate_difficulties(db)
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

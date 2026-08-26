from __future__ import annotations

import argparse
import json

from app.database import SessionLocal, init_db
from app.services.research_service import harvest_source


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest external observations for a research source.")
    parser.add_argument("--source", required=True, help="Source id or name.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum observations to harvest.")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        result = harvest_source(db, source_key=args.source, limit=args.limit)
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

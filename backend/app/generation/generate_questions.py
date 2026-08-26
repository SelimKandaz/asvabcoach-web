from __future__ import annotations

import argparse
import json

from app.database import SessionLocal, init_db
from app.services.quality_service import generate_questions as generate_questions_in_db
from app.schemas import AdminGenerateRequest


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic ASVAB-style questions.")
    parser.add_argument("--section", action="append", dest="sections", default=[], help="Section to generate.")
    parser.add_argument("--skill", action="append", dest="skills", default=[], help="Skill tag to prioritize.")
    parser.add_argument("--difficulty", action="append", dest="difficulty_levels", type=int, default=[], help="Difficulty level.")
    parser.add_argument("--count", type=int, default=4, help="Questions per section.")
    parser.add_argument("--activate", default="true", help="Whether generated questions should be active.")
    args = parser.parse_args()

    init_db()
    request = AdminGenerateRequest(
        sections=args.sections or ["AR", "MK", "WK", "PC", "MC", "EI", "GS", "AI", "SI", "AO"],
        skill_tags=args.skills,
        questions_per_section=args.count,
        difficulty_levels=args.difficulty_levels or [1, 2, 3, 4, 5],
        active=_parse_bool(args.activate),
    )
    with SessionLocal() as db:
        result = generate_questions_in_db(db, request)
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

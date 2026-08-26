import sys
from pathlib import Path

from app.data_import.import_questions import import_question_file
from app.database import SessionLocal, init_db


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m app.seed_import <path-to-file>")
    file_path = Path(sys.argv[1]).expanduser().resolve()
    init_db()
    with SessionLocal() as db:
        import_question_file(file_path, db)


if __name__ == "__main__":
    main()


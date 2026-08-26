from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from app.database import SessionLocal, init_db
from app.data_import.bank_package_import import _collect_package_qa_issues, _resolve_package_source_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QA checks against an import package before import.")
    parser.add_argument("file_path", help="Path to a JSON/CSV/SQLite/ZIP package.")
    args = parser.parse_args()

    file_path = Path(args.file_path).expanduser().resolve()
    init_db()

    source_files, extracted_root = _resolve_package_source_files(file_path)
    try:
        with SessionLocal() as db:
            issues = _collect_package_qa_issues(source_files, db)
        print(
            json.dumps(
                {
                    "file_path": str(file_path),
                    "source_files": [str(path) for path in source_files],
                    "issue_count": len(issues),
                    "passed": len(issues) == 0,
                    "issues": issues[:200],
                },
                indent=2,
            )
        )
    finally:
        if extracted_root and extracted_root.exists():
            shutil.rmtree(extracted_root, ignore_errors=True)


if __name__ == "__main__":
    main()

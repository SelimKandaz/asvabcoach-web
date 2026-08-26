from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _compose_env() -> dict[str, str]:
    env = _load_env_file(REPO_ROOT / ".env")
    for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "DATABASE_URL"):
        if key in env and env[key]:
            continue
        value = subprocess.run(
            ["docker", "compose", "exec", "-T", "backend", "sh", "-lc", f"printf '%s' ${key}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if value:
            env[key] = value
    return env


def _backup_database() -> Path:
    env = _compose_env()
    backup_dir = REPO_ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"pre_elite_original_import_{stamp}.sql"

    database_url = env.get("DATABASE_URL", "")
    if database_url.startswith("sqlite"):
        raise RuntimeError("SQLite backups are not supported by this importer wrapper.")

    username = env.get("POSTGRES_USER", "")
    password = env.get("POSTGRES_PASSWORD", "")
    database = env.get("POSTGRES_DB", "")
    if not (username and password and database):
        raise RuntimeError("Missing POSTGRES_USER, POSTGRES_PASSWORD, or POSTGRES_DB in .env.")

    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "postgres",
        "sh",
        "-lc",
        f"PGPASSWORD={shlex.quote(password)} pg_dump -U {shlex.quote(username)} -d {shlex.quote(database)}",
    ]
    with backup_path.open("wb") as handle:
        subprocess.run(command, cwd=REPO_ROOT, check=True, stdout=handle)
    return backup_path


def _copy_zip_to_backend(zip_path: Path) -> str:
    backend_cid = subprocess.check_output(
        ["docker", "compose", "ps", "-q", "backend"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    if not backend_cid:
        raise RuntimeError("Backend container is not running.")
    container_path = f"/tmp/{zip_path.name}"
    subprocess.run(["docker", "cp", str(zip_path), f"{backend_cid}:{container_path}"], cwd=REPO_ROOT, check=True)
    return container_path


def _run_backend_import(container_zip_path: str) -> dict[str, object]:
    payload = f"""
import json
from pathlib import Path

from app.database import SessionLocal, init_db
from app.data_import.import_questions import import_question_file

init_db()
with SessionLocal() as db:
    log = import_question_file(Path({container_zip_path!r}), db)
    print(
        json.dumps(
            {{
                "log_id": log.id,
                "source_name": log.source_name,
                "imported_count": log.imported_count,
                "updated_count": log.updated_count,
                "skipped_count": log.skipped_count,
                "failed_count": log.failed_count,
                "status": log.status,
                "messages": log.details.get("messages", []),
            }},
            indent=2,
        )
    )
"""
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "python", "-"],
        cwd=REPO_ROOT,
        input=payload,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the ASVAB v6 elite original practice bank.")
    parser.add_argument("--zip", dest="zip_path", required=True, help="Path to asvab_v6_elite_original_package.zip")
    parser.add_argument(
        "--bank-role",
        dest="bank_role",
        default="elite_original_practice",
        help="Expected bank role for this import.",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip the automatic database backup step. Use only after taking a manual backup.",
    )
    args = parser.parse_args()

    if args.bank_role != "elite_original_practice":
        raise ValueError("This importer is only intended for elite_original_practice.")

    file_path = Path(args.zip_path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    backup_path = None if args.skip_backup else _backup_database()
    container_zip_path = _copy_zip_to_backend(file_path)
    result = _run_backend_import(container_zip_path)
    result["backup_path"] = str(backup_path) if backup_path is not None else None
    result["container_zip_path"] = container_zip_path
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

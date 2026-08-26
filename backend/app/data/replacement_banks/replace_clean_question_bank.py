from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4
from collections import Counter

from sqlalchemy import text

from app.database import SessionLocal, init_db
from app.models import ImportLog, Question


BANK_FILES = [
    "asvab_remaining_sections_replacement_bank_v2.json",
    "asvab_wk_wordnet_style_question_bank_v1.json",
    "asvab_pc_paragraph_comprehension_question_bank_v1.json",
]


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text_value = str(value).strip().lower()
    if not text_value:
        return default
    return text_value in {"1", "true", "yes", "y", "on"}


def _as_int(value: object, default: int | None = None) -> int | None:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: object, default: float | None = None) -> float | None:
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_json_list(value: object) -> list | None:
    if value is None or value == "":
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    text_value = str(value).strip()
    if not text_value:
        return None
    if text_value.startswith("["):
        try:
            payload = json.loads(text_value)
            return payload if isinstance(payload, list) else None
        except json.JSONDecodeError:
            return None
    return [item.strip() for item in text_value.replace(";", ",").split(",") if item.strip()] or None


def _load_bank(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("questions", "items", "rows", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError(f"Unsupported JSON bank structure: {path}")


def _question_payload(row: dict) -> dict:
    question_id = str(row.get("question_id") or row.get("id") or "").strip()
    if not question_id:
        raise ValueError("Missing question_id")

    section = str(row.get("section") or "").strip().upper()
    if not section:
        raise ValueError(f"{question_id}: missing section")

    choices = {
        "A": str(row.get("choice_a") or "").strip(),
        "B": str(row.get("choice_b") or "").strip(),
        "C": str(row.get("choice_c") or "").strip(),
        "D": str(row.get("choice_d") or "").strip(),
    }
    if not all(choices.values()):
        raise ValueError(f"{question_id}: one or more choices are empty")

    correct_answer = str(row.get("correct_answer") or "").strip().upper()
    if correct_answer not in {"A", "B", "C", "D"}:
        raise ValueError(f"{question_id}: invalid correct_answer={correct_answer!r}")

    question_text = str(row.get("question_text") or "").strip()
    if not question_text:
        raise ValueError(f"{question_id}: missing question_text")

    has_figure = _as_bool(row.get("has_figure"), False)
    requires_figure = _as_bool(row.get("requires_figure"), has_figure)
    figure_svg = str(row.get("figure_svg") or "").strip() or None

    active = _as_bool(row.get("active"), True)
    eligible_for_study = _as_bool(row.get("eligible_for_study"), True)
    eligible_for_cat = _as_bool(row.get("eligible_for_cat"), True)
    eligible_for_review = _as_bool(row.get("eligible_for_review"), True)
    content_status = str(row.get("content_status") or "verified").strip().lower()
    validation_status = str(row.get("validation_status") or "passed").strip().lower()

    if active and has_figure and not figure_svg:
        raise ValueError(f"{question_id}: active figure question missing figure_svg")

    # Keep this import strict. Bad rows should not silently enter the bank.
    if content_status != "verified" or validation_status != "passed" or not active or not eligible_for_study:
        raise ValueError(
            f"{question_id}: row is not verified/active/study-ready "
            f"(content_status={content_status}, validation_status={validation_status}, active={active}, eligible_for_study={eligible_for_study})"
        )

    difficulty_level = _as_int(row.get("difficulty_level"), 3) or 3
    difficulty_level = max(1, min(5, difficulty_level))

    payload = {
        "id": question_id,
        "source_question_id": row.get("source_question_id") or None,
        "canonical_hash": row.get("canonical_hash") or None,
        "duplicate_of_question_id": None,
        "section": section,
        "skill_tag": row.get("skill_tag") or "general",
        "concept_tag": row.get("concept_tag") or "general",
        "question_type": row.get("question_type") or None,
        "template_family": row.get("template_family") or "conceptual_definition",
        "variant_signature": row.get("variant_signature") or f"{section}:unknown:{question_id}",
        "reasoning_steps": _as_int(row.get("reasoning_steps"), 1) or 1,
        "formula_stack": _as_json_list(row.get("formula_stack")),
        "concept_stack": _as_json_list(row.get("concept_stack")),
        "trap_type": row.get("trap_type") or None,
        "difficulty_level": difficulty_level,
        "difficulty_label": row.get("difficulty_label") or None,
        "calibrated_difficulty_level": _as_int(row.get("calibrated_difficulty_level"), difficulty_level) or difficulty_level,
        "calibrated_irt_b": _as_float(row.get("calibrated_irt_b"), _as_float(row.get("irt_b"), 0.0)),
        "irt_a": _as_float(row.get("irt_a"), 1.0) or 1.0,
        "irt_b": _as_float(row.get("irt_b"), 0.0) or 0.0,
        "irt_c": _as_float(row.get("irt_c"), 0.25) or 0.25,
        "passage_id": row.get("passage_id") or None,
        "passage_topic": row.get("passage_topic") or None,
        "passage_text": row.get("passage_text") or None,
        "passage_word_count": _as_int(row.get("passage_word_count"), None),
        "vocab_word": row.get("vocab_word") or None,
        "part_of_speech": row.get("part_of_speech") or None,
        "question_text": question_text,
        "question_stem": row.get("question_stem") or None,
        "choice_a": choices["A"],
        "choice_b": choices["B"],
        "choice_c": choices["C"],
        "choice_d": choices["D"],
        "correct_answer": correct_answer,
        "correct_value": row.get("correct_value") or choices[correct_answer],
        "definition": row.get("definition") or None,
        "has_figure": has_figure,
        "requires_figure": requires_figure,
        "figure_type": row.get("figure_type") or None,
        "figure_data": row.get("figure_data") if isinstance(row.get("figure_data"), dict) else None,
        "figure_svg": figure_svg,
        "figure_alt_text": row.get("figure_alt_text") or None,
        "figure_quality_status": row.get("figure_quality_status") or ("generated_svg" if has_figure else "no_figure_needed"),
        "base_explanation": row.get("base_explanation") or row.get("explanation") or None,
        "wrong_a_explanation": row.get("wrong_a_explanation") or None,
        "wrong_b_explanation": row.get("wrong_b_explanation") or None,
        "wrong_c_explanation": row.get("wrong_c_explanation") or None,
        "wrong_d_explanation": row.get("wrong_d_explanation") or None,
        "wrong_answer_explanation": row.get("wrong_answer_explanation") or None,
        "quick_method": row.get("quick_method") or None,
        "source_name": row.get("source_name") or row.get("source_profile") or "clean_replacement_bank",
        "source_alignment": row.get("source_alignment") or None,
        "source_url": row.get("source_url") or None,
        "source_confidence": row.get("source_confidence") or None,
        "source_profile": row.get("source_profile") or None,
        "reading_source_profile": row.get("reading_source_profile") or None,
        "lexical_source_profile": row.get("lexical_source_profile") or None,
        "frequency_source_profile": row.get("frequency_source_profile") or None,
        "confidence": row.get("confidence") or "estimated",
        "copyright_status": row.get("copyright_status") or "original_generated",
        "license_status": row.get("license_status") or "internal_original_generated",
        "content_status": content_status,
        "issue_notes": row.get("issue_notes") or None,
        "complexity_score": _as_int(row.get("complexity_score"), None),
        "generation_method": row.get("generation_method") or "clean_replacement_import",
        "validator_name": row.get("validator_name") or "replace_clean_bank_script",
        "validation_status": validation_status,
        "times_seen": _as_int(row.get("times_seen"), 0) or 0,
        "sample_size_estimate": _as_int(row.get("sample_size_estimate"), 0),
        "observed_correct_rate": _as_float(row.get("observed_correct_rate") or row.get("observed_correct_rate_estimate"), None),
        "average_response_time_seconds": _as_float(row.get("average_response_time_seconds"), None),
        "active": True,
        "eligible_for_study": True,
        "eligible_for_cat": eligible_for_cat,
        "eligible_for_review": eligible_for_review,
    }

    # Keep only columns that exist in the installed Question model.
    valid_columns = set(Question.__table__.columns.keys())
    return {key: value for key, value in payload.items() if key in valid_columns}


def _hard_reset_question_data(db) -> None:
    # Preserve users/career requirements/source metadata, but clear old test history and old questions.
    # This avoids broken foreign keys after deleting the old bank.
    statements = [
        "UPDATE external_question_observations SET matched_internal_question_id = NULL WHERE matched_internal_question_id IS NOT NULL",
        "UPDATE ai_explanation_cache SET question_id = NULL WHERE question_id IS NOT NULL",
        "UPDATE test_sessions SET current_question_id = NULL WHERE current_question_id IS NOT NULL",
        "DELETE FROM user_seen_question_hashes",
        "DELETE FROM user_question_stats",
        "DELETE FROM responses",
        "DELETE FROM session_section_state",
        "DELETE FROM test_sessions",
        "DELETE FROM skill_stats",
        "UPDATE questions SET duplicate_of_question_id = NULL WHERE duplicate_of_question_id IS NOT NULL",
        "DELETE FROM questions",
    ]
    for statement in statements:
        db.execute(text(statement))


def replace_question_bank(bank_dir: Path, *, dry_run: bool = False) -> dict:
    init_db()

    all_rows: list[dict] = []
    file_counts: dict[str, int] = {}

    for file_name in BANK_FILES:
        path = bank_dir / file_name
        if not path.exists():
            raise FileNotFoundError(f"Missing bank file: {path}")
        rows = _load_bank(path)
        file_counts[file_name] = len(rows)
        all_rows.extend(rows)

    payloads = [_question_payload(row) for row in all_rows]

    ids = [payload["id"] for payload in payloads]
    duplicate_ids = [item for item, count in Counter(ids).items() if count > 1]
    if duplicate_ids:
        raise ValueError(f"Duplicate question IDs in replacement bank: {duplicate_ids[:20]}")

    active_hashes = [payload.get("canonical_hash") for payload in payloads if payload.get("canonical_hash")]
    duplicate_hashes = [item for item, count in Counter(active_hashes).items() if count > 1]
    if duplicate_hashes:
        raise ValueError(f"Duplicate canonical_hash values in replacement bank: {duplicate_hashes[:20]}")

    section_counts = Counter(payload["section"] for payload in payloads)
    difficulty_counts = Counter(int(payload["difficulty_level"]) for payload in payloads)
    figure_missing = [
        payload["id"]
        for payload in payloads
        if payload.get("active") and payload.get("has_figure") and not payload.get("figure_svg")
    ]
    if figure_missing:
        raise ValueError(f"Active figure questions missing SVG: {figure_missing[:20]}")

    if dry_run:
        return {
            "dry_run": True,
            "bank_dir": str(bank_dir),
            "file_counts": file_counts,
            "total_payloads": len(payloads),
            "section_counts": dict(sorted(section_counts.items())),
            "difficulty_counts": dict(sorted(difficulty_counts.items())),
            "figure_questions": sum(1 for payload in payloads if payload.get("has_figure")),
        }

    with SessionLocal() as db:
        _hard_reset_question_data(db)

        for payload in payloads:
            db.add(Question(**payload))

        log = ImportLog(
            id=f"imp_clean_replace_{uuid4().hex[:8]}",
            source_name="clean_replacement_bank_set",
            file_path=str(bank_dir),
            imported_count=len(payloads),
            updated_count=0,
            skipped_count=0,
            failed_count=0,
            status="completed",
            details={
                "file_counts": file_counts,
                "section_counts": dict(sorted(section_counts.items())),
                "difficulty_counts": dict(sorted(difficulty_counts.items())),
                "figure_questions": sum(1 for payload in payloads if payload.get("has_figure")),
                "note": "Hard reset: old sessions/stats/questions were cleared before importing clean replacement bank.",
            },
        )
        db.add(log)
        db.commit()

        verification = {
            "dry_run": False,
            "import_log_id": log.id,
            "imported_count": len(payloads),
            "section_counts": dict(
                db.execute(
                    text("SELECT section, count(*) FROM questions WHERE active=true GROUP BY section ORDER BY section")
                ).all()
            ),
            "difficulty_counts": dict(
                db.execute(
                    text("SELECT difficulty_level, count(*) FROM questions WHERE active=true GROUP BY difficulty_level ORDER BY difficulty_level")
                ).all()
            ),
            "figure_missing_svg": db.execute(
                text("SELECT count(*) FROM questions WHERE active=true AND has_figure=true AND (figure_svg IS NULL OR figure_svg='')")
            ).scalar(),
            "duplicate_hash_count": db.execute(
                text("SELECT count(*) FROM (SELECT canonical_hash FROM questions WHERE active=true GROUP BY canonical_hash HAVING count(*) > 1) d")
            ).scalar(),
            "total_active": db.execute(text("SELECT count(*) FROM questions WHERE active=true")).scalar(),
        }
        return verification


def main() -> None:
    parser = argparse.ArgumentParser(description="Hard replace old ASVAB question bank with clean curated replacement banks.")
    parser.add_argument("--bank-dir", default="/app/app/data/replacement_banks", help="Directory containing the three replacement JSON files.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print counts without changing the database.")
    args = parser.parse_args()

    result = replace_question_bank(Path(args.bank_dir), dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

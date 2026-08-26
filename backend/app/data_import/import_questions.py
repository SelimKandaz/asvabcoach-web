from __future__ import annotations

import argparse
import json
import sqlite3
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
import zipfile

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import ImportLog, Question
from app.data_import.normalize_questions import (
    canonical_hash_for_question,
    build_header_map,
    default_irt_values,
    generate_stable_question_id,
    normalize_choice_text,
    normalize_correct_answer,
    normalize_difficulty,
    normalize_section_name,
    normalize_skill_tag,
)
from app.data_import.bank_package_import import import_bank_package_file
from app.services.difficulty_service import difficulty_irt_b, infer_difficulty_level
from app.services.figure_service import build_question_figure_svg
from app.services.question_profile_service import derive_question_profile


SQLITE_EXTENSIONS = {".sqlite", ".sqlite3", ".db"}


@dataclass(slots=True)
class ImportPolicy:
    required_section: str | None = None
    allowed_sections: set[str] | None = None
    require_verified_study_ready: bool = False


def _looks_like_bank_package(file_path: Path) -> bool:
    name = file_path.name.lower()
    return any(
        token in name
        for token in (
            "v6_elite_original",
            "elite_original_practice",
            "asvab_v6_elite_original",
            "v5_1",
            "open_pc50",
            "quality_patch",
            "score_simulator",
        )
    )


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _row_value(row: pd.Series, header_map: dict[str, str], key: str, default: object = "") -> object:
    column_name = header_map.get(key)
    if not column_name:
        return default
    return row.get(column_name, default)


def _optional_text(row: pd.Series, header_map: dict[str, str], key: str) -> str | None:
    value = _row_value(row, header_map, key, "")
    text = str(value).strip() if value is not None else ""
    return text or None


def _optional_tag(row: pd.Series, header_map: dict[str, str], key: str) -> str | None:
    value = _optional_text(row, header_map, key)
    return normalize_skill_tag(value) if value else None


def _optional_int(row: pd.Series, header_map: dict[str, str], key: str) -> int | None:
    value = _row_value(row, header_map, key, "")
    if value is None or str(value).strip() == "":
        return None
    return int(float(value))


def _optional_float(row: pd.Series, header_map: dict[str, str], key: str) -> float | None:
    value = _row_value(row, header_map, key, "")
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def _row_bool(row: pd.Series, header_map: dict[str, str], key: str, *, default: bool) -> bool:
    column_name = header_map.get(key)
    if not column_name:
        return default
    return _as_bool(row.get(column_name, ""))


def _parse_jsonish_value(value: object) -> object:
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _load_json_dataframe(file_path: Path) -> pd.DataFrame:
    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        return pd.DataFrame(payload)

    if isinstance(payload, dict):
        for key in ("questions", "items", "rows", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return pd.DataFrame(value)

        manifest_files = payload.get("files")
        if isinstance(manifest_files, list):
            companion_path = _find_companion_question_bank_file(
                parent_dir=file_path.parent,
                candidates=[str(item) for item in manifest_files],
            )
            if companion_path is None:
                raise ValueError(f"No importable question bank file found next to manifest: {file_path.name}")
            return load_dataframe(companion_path)

        if payload and all(isinstance(value, list) for value in payload.values()):
            return pd.DataFrame(payload)

    raise ValueError(f"Unsupported JSON structure in {file_path.name}")


def _load_sqlite_dataframe(file_path: Path) -> pd.DataFrame:
    with sqlite3.connect(file_path) as connection:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        if not tables:
            raise ValueError(f"No tables found in SQLite package: {file_path.name}")
        table_name = "questions" if "questions" in tables else tables[0]
        return pd.read_sql_query(f'SELECT * FROM "{table_name}"', connection)


def _question_bank_sort_key(path: Path) -> tuple[int, int, str]:
    name = path.name.lower()
    is_bank = 0 if "question_bank" in name else 1
    preferred_ext = 0 if path.suffix.lower() == ".csv" else 1 if path.suffix.lower() == ".json" else 2
    return (is_bank, preferred_ext, name)


def _filter_question_bank_candidates(candidates: list[str]) -> list[Path]:
    candidate_paths: list[Path] = []
    for item in candidates:
        candidate = Path(item).name
        candidate_path = Path(candidate)
        name = candidate_path.name.lower()
        if candidate_path.suffix.lower() not in {".csv", ".json", ".xlsx", ".xls", ".sqlite", ".sqlite3", ".db"}:
            continue
        if "anchor" in name or "manifest" in name:
            continue
        candidate_paths.append(candidate_path)
    return sorted(candidate_paths, key=_question_bank_sort_key)


def _find_companion_question_bank_file(parent_dir: Path, candidates: list[str]) -> Path | None:
    for candidate in _filter_question_bank_candidates(candidates):
        resolved_candidate = parent_dir / candidate.name
        if resolved_candidate.exists():
            return resolved_candidate
    return None


def _select_question_bank_member(candidates: list[str]) -> str | None:
    filtered_candidates = _filter_question_bank_candidates(candidates)
    if not filtered_candidates:
        return None
    selected_name = filtered_candidates[0].name
    matching_members = [
        item for item in candidates
        if Path(item).name == selected_name
    ]
    if not matching_members:
        return None
    return sorted(matching_members)[0]


def _extract_question_bank_from_zip(file_path: Path) -> Path:
    settings = get_settings()
    with zipfile.ZipFile(file_path) as archive:
        member_names = [name for name in archive.namelist() if not name.endswith("/")]
        selected_member = _select_question_bank_member(member_names)
        if selected_member is None:
            raise ValueError(f"No importable question bank file found in archive: {file_path.name}")
        extract_root = settings.upload_dir / f"{file_path.stem}_{uuid4().hex}"
        extract_root.mkdir(parents=True, exist_ok=True)
        archive.extractall(extract_root)
        return (extract_root / selected_member).resolve()


def load_dataframe(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        workbook = pd.ExcelFile(file_path)
        preferred_sheets = ["QuestionBank", "Questions", "questionbank", "question_bank"]
        for sheet_name in preferred_sheets + workbook.sheet_names:
            if sheet_name not in workbook.sheet_names:
                continue
            data_frame = workbook.parse(sheet_name=sheet_name)
            header_map = build_header_map(list(data_frame.columns))
            if "question_text" in header_map and "correct_answer" in header_map:
                return data_frame
        return workbook.parse(workbook.sheet_names[0])
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix == ".json":
        return _load_json_dataframe(file_path)
    if suffix in SQLITE_EXTENSIONS:
        return _load_sqlite_dataframe(file_path)
    if suffix == ".zip":
        extracted_path = _extract_question_bank_from_zip(file_path)
        return load_dataframe(extracted_path)
    raise ValueError(f"Unsupported file type: {suffix}")


def import_question_file(file_path: Path, db: Session, *, policy: ImportPolicy | None = None) -> ImportLog:
    if _looks_like_bank_package(file_path):
        return import_bank_package_file(file_path, db)
    policy = policy or ImportPolicy()
    settings = get_settings()
    data_frame = load_dataframe(file_path)
    header_map = build_header_map(list(data_frame.columns))

    imported_count = 0
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    failures: list[str] = []

    existing_questions = {
        question.id: question for question in db.scalars(select(Question)).all()
    }
    existing_canonical_index = {
        question.canonical_hash: question.id
        for question in existing_questions.values()
        if (
            question.canonical_hash
            and question.active
            and question.content_status in {"verified", "active"}
            and question.duplicate_of_question_id is None
        )
    }

    for row_index, row in data_frame.fillna("").iterrows():
        try:
            section = normalize_section_name(_row_value(row, header_map, "section", ""))
            validation_status = (_optional_text(row, header_map, "validation_status") or "passed").lower()
            content_status = (_optional_text(row, header_map, "content_status") or "verified").lower()
            active_flag = _row_bool(row, header_map, "active", default=content_status in {"verified", "active"})
            eligible_for_study = _row_bool(row, header_map, "eligible_for_study", default=True)
            eligible_for_cat = _row_bool(row, header_map, "eligible_for_cat", default=True)
            eligible_for_review = _row_bool(row, header_map, "eligible_for_review", default=True)

            if policy.required_section and section != policy.required_section:
                skipped_count += 1
                continue
            if policy.allowed_sections and section not in policy.allowed_sections:
                skipped_count += 1
                continue
            if policy.require_verified_study_ready and not (
                section == (policy.required_section or section)
                and content_status == "verified"
                and validation_status == "passed"
                and active_flag
                and eligible_for_study
            ):
                skipped_count += 1
                continue

            question_text = str(_row_value(row, header_map, "question_text", "")).strip()
            if not question_text:
                skipped_count += 1
                failures.append(f"Row {row_index + 2}: question text is empty.")
                continue

            choices = {
                "A": normalize_choice_text(_row_value(row, header_map, "choice_a", "")),
                "B": normalize_choice_text(_row_value(row, header_map, "choice_b", "")),
                "C": normalize_choice_text(_row_value(row, header_map, "choice_c", "")),
                "D": normalize_choice_text(_row_value(row, header_map, "choice_d", "")),
            }
            if not all(choices.values()):
                skipped_count += 1
                failures.append(f"Row {row_index + 2}: one or more answer choices are empty.")
                continue

            source_question_id = _optional_text(row, header_map, "source_question_id")
            question_id = str(_row_value(row, header_map, "id", "")).strip() or generate_stable_question_id(
                source_question_id,
                section,
                question_text,
                choices,
            )
            correct_answer = normalize_correct_answer(_row_value(row, header_map, "correct_answer", ""), choices)
            if not correct_answer:
                skipped_count += 1
                failures.append(f"Row {row_index + 2}: correct answer is missing or invalid.")
                continue

            explicit_difficulty_level = (
                normalize_difficulty(_row_value(row, header_map, "difficulty_level", 3))
                if header_map.get("difficulty_level")
                else None
            )
            canonical_hash = _optional_text(row, header_map, "canonical_hash") or canonical_hash_for_question(question_text, choices)
            default_a, _, default_c = default_irt_values(explicit_difficulty_level or 3)
            source_confidence = _optional_text(row, header_map, "source_confidence")
            dataset_confidence = _optional_text(row, header_map, "confidence")
            observed_correct_rate_value = _optional_float(row, header_map, "observed_correct_rate")
            average_response_time_value = _optional_float(row, header_map, "average_response_time_seconds")
            times_seen_value = _optional_int(row, header_map, "times_seen") or 0
            sample_size_estimate_value = _optional_int(row, header_map, "sample_size_estimate")
            issue_notes = _optional_text(row, header_map, "issue_notes")
            source_name = _optional_text(row, header_map, "source_name") or file_path.stem
            explicit_calibrated_level_raw = _row_value(row, header_map, "calibrated_difficulty_level", "")
            calibrated_irt_b = _row_value(row, header_map, "calibrated_irt_b", "")
            complexity_score = _row_value(row, header_map, "complexity_score", "")
            generation_method = _optional_text(row, header_map, "generation_method") or "seed_import"
            validator_name = _optional_text(row, header_map, "validator_name") or "import_pipeline"
            skill_tag = normalize_skill_tag(_row_value(row, header_map, "skill_tag", ""))
            has_figure = _row_bool(row, header_map, "has_figure", default=False)
            figure_type = _optional_text(row, header_map, "figure_type")
            figure_data_raw = _row_value(row, header_map, "figure_data", "")
            figure_svg = str(row.get(header_map.get("figure_svg", ""), "")).strip() or None
            figure_alt_text = _optional_text(row, header_map, "figure_alt_text")
            figure_data = None
            if isinstance(figure_data_raw, str) and figure_data_raw.strip():
                try:
                    figure_data = json.loads(figure_data_raw)
                except json.JSONDecodeError:
                    figure_data = {"raw": figure_data_raw}
            elif isinstance(figure_data_raw, dict):
                figure_data = figure_data_raw
            if has_figure and not figure_svg:
                figure_svg = build_question_figure_svg(
                    figure_type=figure_type,
                    question_text=question_text,
                    figure_alt_text=figure_alt_text,
                    figure_data=figure_data,
                )
            wrong_explanations = {
                "wrong_a_explanation": _optional_text(row, header_map, "wrong_a_explanation"),
                "wrong_b_explanation": _optional_text(row, header_map, "wrong_b_explanation"),
                "wrong_c_explanation": _optional_text(row, header_map, "wrong_c_explanation"),
                "wrong_d_explanation": _optional_text(row, header_map, "wrong_d_explanation"),
            }
            complexity_score_value = int(complexity_score) if str(complexity_score).strip() else None
            explicit_calibrated_level = (
                normalize_difficulty(explicit_calibrated_level_raw)
                if str(explicit_calibrated_level_raw).strip()
                else None
            )
            profile = derive_question_profile(
                section=section,
                skill_tag=skill_tag,
                question_text=question_text,
                has_figure=has_figure,
                figure_type=figure_type,
                figure_svg=figure_svg,
                generation_method=generation_method,
                source_name=source_name,
                copyright_status=_optional_text(row, header_map, "copyright_status"),
                concept_tag=_row_value(row, header_map, "concept_tag", ""),
                template_family=_row_value(row, header_map, "template_family", ""),
                variant_signature=_row_value(row, header_map, "variant_signature", ""),
                reasoning_steps=_row_value(row, header_map, "reasoning_steps", ""),
                formula_stack=_parse_jsonish_value(_row_value(row, header_map, "formula_stack", "")),
                concept_stack=_parse_jsonish_value(_row_value(row, header_map, "concept_stack", "")),
                trap_type=_row_value(row, header_map, "trap_type", ""),
                requires_figure=(
                    _row_bool(row, header_map, "requires_figure", default=False)
                    if header_map.get("requires_figure")
                    else None
                ),
                figure_quality_status=_row_value(row, header_map, "figure_quality_status", ""),
                license_status=_row_value(row, header_map, "license_status", ""),
                source_profile=_row_value(row, header_map, "source_profile", ""),
                difficulty_num=_row_value(row, header_map, "difficulty_num", ""),
            )
            resolved_complexity_score = complexity_score_value or profile.derived_complexity_score
            resolved_difficulty_level, _ = infer_difficulty_level(
                base_level=explicit_difficulty_level or profile.recommended_difficulty_level,
                observed_correct_rate=observed_correct_rate_value,
                observed_sample_size=sample_size_estimate_value or times_seen_value,
                complexity_score=resolved_complexity_score,
                prior_level=explicit_calibrated_level or explicit_difficulty_level or profile.recommended_difficulty_level,
            )
            resolved_irt_b = float(calibrated_irt_b) if str(calibrated_irt_b).strip() else difficulty_irt_b(resolved_difficulty_level)
            payload = {
                "id": question_id,
                "source_question_id": source_question_id,
                "canonical_hash": canonical_hash,
                "section": section,
                "skill_tag": skill_tag,
                "concept_tag": profile.concept_tag,
                "question_type": _optional_tag(row, header_map, "question_type"),
                "template_family": profile.template_family,
                "variant_signature": profile.variant_signature,
                "reasoning_steps": profile.reasoning_steps,
                "formula_stack": profile.formula_stack,
                "concept_stack": profile.concept_stack,
                "trap_type": profile.trap_type,
                "difficulty_level": resolved_difficulty_level,
                "difficulty_label": _optional_text(row, header_map, "difficulty_label"),
                "irt_a": float(row.get(header_map.get("irt_a", ""), "") or default_a),
                "irt_b": difficulty_irt_b(resolved_difficulty_level),
                "irt_c": float(row.get(header_map.get("irt_c", ""), "") or default_c),
                "calibrated_difficulty_level": resolved_difficulty_level,
                "calibrated_irt_b": resolved_irt_b,
                "passage_id": _optional_text(row, header_map, "passage_id"),
                "passage_topic": _optional_text(row, header_map, "passage_topic"),
                "passage_text": _optional_text(row, header_map, "passage_text"),
                "passage_word_count": _optional_int(row, header_map, "passage_word_count"),
                "vocab_word": _optional_text(row, header_map, "vocab_word"),
                "part_of_speech": _optional_text(row, header_map, "part_of_speech"),
                "question_text": question_text,
                "question_stem": _optional_text(row, header_map, "question_stem"),
                "choice_a": choices["A"],
                "choice_b": choices["B"],
                "choice_c": choices["C"],
                "choice_d": choices["D"],
                "correct_answer": correct_answer,
                "correct_value": _optional_text(row, header_map, "correct_value"),
                "definition": _optional_text(row, header_map, "definition"),
                "has_figure": has_figure,
                "requires_figure": profile.requires_figure,
                "figure_type": figure_type,
                "figure_data": figure_data,
                "figure_svg": figure_svg,
                "figure_alt_text": figure_alt_text,
                "figure_quality_status": profile.figure_quality_status,
                "base_explanation": _optional_text(row, header_map, "base_explanation"),
                **wrong_explanations,
                "wrong_answer_explanation": _optional_text(row, header_map, "wrong_answer_explanation"),
                "quick_method": _optional_text(row, header_map, "quick_method"),
                "source_name": source_name,
                "source_alignment": _optional_text(row, header_map, "source_alignment"),
                "source_url": _optional_text(row, header_map, "source_url"),
                "source_confidence": source_confidence,
                "source_profile": profile.source_profile,
                "reading_source_profile": _optional_text(row, header_map, "reading_source_profile"),
                "lexical_source_profile": _optional_text(row, header_map, "lexical_source_profile"),
                "frequency_source_profile": _optional_text(row, header_map, "frequency_source_profile"),
                "confidence": dataset_confidence,
                "copyright_status": _optional_text(row, header_map, "copyright_status"),
                "license_status": profile.license_status,
                "content_status": content_status,
                "issue_notes": issue_notes,
                "complexity_score": resolved_complexity_score,
                "generation_method": generation_method,
                "validator_name": validator_name,
                "validation_status": validation_status,
                "times_seen": times_seen_value,
                "sample_size_estimate": sample_size_estimate_value,
                "observed_correct_rate": observed_correct_rate_value,
                "average_response_time_seconds": average_response_time_value,
                "active": active_flag and content_status in {"verified", "active"} and validation_status == "passed",
                "eligible_for_study": eligible_for_study,
                "eligible_for_cat": eligible_for_cat,
                "eligible_for_review": eligible_for_review,
            }

            if profile.figure_quality_status == "missing":
                payload["content_status"] = "needs_review"
                payload["validation_status"] = "needs_review"
                payload["active"] = False
                payload["eligible_for_study"] = False
                payload["eligible_for_cat"] = False
                payload["eligible_for_review"] = False
                payload["issue_notes"] = (
                    (payload["issue_notes"] + " | " if payload["issue_notes"] else "")
                    + "Figure question missing SVG rendering."
                )

            duplicate_rep_id = existing_canonical_index.get(canonical_hash)
            if duplicate_rep_id == question_id:
                duplicate_rep_id = None
            if duplicate_rep_id is None:
                duplicate_rep = db.scalar(
                    select(Question).where(
                        Question.canonical_hash == canonical_hash,
                        Question.id != question_id,
                        Question.active.is_(True),
                        Question.content_status.in_(("verified", "active")),
                        Question.duplicate_of_question_id.is_(None),
                    )
                )
                duplicate_rep_id = duplicate_rep.id if duplicate_rep is not None else None
            if duplicate_rep_id is not None:
                payload["duplicate_of_question_id"] = duplicate_rep_id
                payload["content_status"] = "duplicate"
                payload["validation_status"] = "passed"
                payload["active"] = False
                payload["eligible_for_study"] = False
                payload["eligible_for_cat"] = False
                payload["eligible_for_review"] = False
                payload["issue_notes"] = (
                    (payload["issue_notes"] + " | " if payload["issue_notes"] else "")
                    + f"Duplicate of {duplicate_rep_id} by canonical hash."
                )
            else:
                payload["duplicate_of_question_id"] = None

            existing = existing_questions.get(question_id)
            if existing:
                previous_hash = existing.canonical_hash
                previous_active_hash = (
                    previous_hash
                    if previous_hash
                    and existing.active
                    and existing.content_status in {"verified", "active"}
                    and existing.duplicate_of_question_id is None
                    else None
                )
                changed = False
                for field_name, field_value in payload.items():
                    if getattr(existing, field_name) != field_value:
                        setattr(existing, field_name, field_value)
                        changed = True
                if changed:
                    updated_count += 1
                else:
                    skipped_count += 1
                if previous_active_hash and previous_active_hash in existing_canonical_index and existing_canonical_index[previous_active_hash] == question_id:
                    existing_canonical_index.pop(previous_active_hash, None)
                if (
                    payload["active"]
                    and payload["content_status"] in {"verified", "active"}
                    and payload.get("duplicate_of_question_id") is None
                ):
                    existing_canonical_index[canonical_hash] = question_id
            else:
                question = Question(**payload)
                db.add(question)
                existing_questions[question_id] = question
                if (
                    payload["active"]
                    and payload["content_status"] in {"verified", "active"}
                    and payload.get("duplicate_of_question_id") is None
                ):
                    existing_canonical_index[canonical_hash] = question_id
                imported_count += 1
        except Exception as exc:  # noqa: BLE001
            failed_count += 1
            failures.append(f"Row {row_index + 2}: {exc}")

    log = ImportLog(
        id=f"imp_{uuid4().hex[:12]}",
        source_name=file_path.name,
        file_path=str(file_path),
        imported_count=imported_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        status="completed" if failed_count == 0 else "completed_with_errors",
        details={"messages": failures[:100]},
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    log_path = settings.import_log_dir / f"{log.id}.json"
    log_path.write_text(
        json.dumps(
            {
                "log_id": log.id,
                "source_name": log.source_name,
                "file_path": log.file_path,
                "imported_count": imported_count,
                "updated_count": updated_count,
                "skipped_count": skipped_count,
                "failed_count": failed_count,
                "messages": failures[:100],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return log


def main() -> None:
    parser = argparse.ArgumentParser(description="Import ASVAB question data into the database.")
    parser.add_argument("file_path", help="Path to an XLSX, CSV, or JSON file.")
    args = parser.parse_args()
    file_path = Path(args.file_path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    init_db()
    with SessionLocal() as db:
        log = import_question_file(file_path, db)
        print(
            json.dumps(
                {
                    "log_id": log.id,
                    "source_name": log.source_name,
                    "imported_count": log.imported_count,
                    "updated_count": log.updated_count,
                    "skipped_count": log.skipped_count,
                    "failed_count": log.failed_count,
                    "status": log.status,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

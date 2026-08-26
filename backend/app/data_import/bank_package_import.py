from __future__ import annotations

import csv
import io
import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data_import.normalize_questions import (
    canonical_hash_for_question,
    default_irt_values,
    generate_stable_question_id,
    normalize_choice_text,
    normalize_correct_answer,
    normalize_difficulty,
    normalize_section_name,
    normalize_skill_tag,
)
from app.models import ImportLog, Question
from app.services.bank_rules import (
    BANK_ROLE_LEGACY,
    BANK_ROLE_ELITE_ORIGINAL_PRACTICE,
    BANK_ROLE_MAIN_PRACTICE,
    BANK_ROLE_PUBLIC_PC_IMPORT,
    BANK_ROLE_QUALITY_PATCH,
    BANK_ROLE_REVIEW_ARCHIVE,
    BANK_ROLE_SCORE_SIMULATOR,
    is_elite_original_practice_source,
    normalize_bank_role,
)
from app.services.difficulty_service import difficulty_irt_b
from app.services.figure_service import build_question_figure_svg


DATA_EXTENSIONS = {".json", ".csv", ".xlsx", ".xls", ".sqlite", ".sqlite3", ".db"}
SQLITE_EXTENSIONS = {".sqlite", ".sqlite3", ".db"}
SKIP_NAME_PARTS = {"manifest", "qa_summary", "readme", "notes", "summary"}


@dataclass(slots=True)
class BankImportSpec:
    bank_role: str
    source_bank: str
    active: bool
    eligible_for_study: bool
    eligible_for_cat: bool
    eligible_for_review: bool
    is_simulator: bool = False
    is_public_import: bool = False
    allow_duplicate_canonical: bool = False
    require_verified_study_ready: bool = False
    force_needs_review: bool = False


def _as_bool(value: object, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "y", "on"}


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _optional_float(value: object) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _optional_int(value: object) -> int | None:
    text = _text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_jsonish(value: object) -> object:
    if isinstance(value, (dict, list)):
        return value
    text = _text(value)
    if not text:
        return None
    if text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _normalize_choices(raw_choices: object) -> list[str]:
    if isinstance(raw_choices, list):
        return [normalize_choice_text(item) for item in raw_choices]
    if isinstance(raw_choices, tuple):
        return [normalize_choice_text(item) for item in raw_choices]
    if isinstance(raw_choices, str):
        text = raw_choices.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [normalize_choice_text(item) for item in parsed]
        return [normalize_choice_text(part) for part in re.split(r"\s*\|\s*", text) if part.strip()]
    return []


def _choice_map(raw_choices: object) -> dict[str, str]:
    choices = _normalize_choices(raw_choices)
    if len(choices) < 4:
        return {}
    return {
        "A": choices[0],
        "B": choices[1],
        "C": choices[2],
        "D": choices[3],
    }


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
    raise ValueError(f"Unsupported JSON structure in {file_path.name}")


def _load_sqlite_dataframe(file_path: Path) -> pd.DataFrame:
    with sqlite3.connect(file_path) as connection:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        if not tables:
            raise ValueError(f"No tables found in SQLite package: {file_path.name}")
        table_name = "questions" if "questions" in tables else tables[0]
        return pd.read_sql_query(f'SELECT * FROM "{table_name}"', connection)


def _load_dataframe(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == ".json":
        return _load_json_dataframe(file_path)
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".xlsx", ".xls"}:
        workbook = pd.ExcelFile(file_path)
        preferred_sheets = ["QuestionBank", "Questions", "questionbank", "question_bank"]
        for sheet_name in preferred_sheets + workbook.sheet_names:
            if sheet_name not in workbook.sheet_names:
                continue
            data_frame = workbook.parse(sheet_name=sheet_name)
            if not data_frame.empty:
                return data_frame
        return workbook.parse(workbook.sheet_names[0])
    if suffix in SQLITE_EXTENSIONS:
        return _load_sqlite_dataframe(file_path)
    raise ValueError(f"Unsupported file type: {suffix}")


def _looks_like_package_file(path: Path) -> bool:
    name = path.name.lower()
    return any(
        token in name
        for token in (
            "replacement_bank",
            "wordnet_style_question_bank",
            "paragraph_comprehension_question_bank",
            "v5_1",
            "open_pc50",
            "quality_patch",
            "score_simulator",
        )
    )


def _resolve_bank_spec(source_name: str) -> BankImportSpec:
    normalized = source_name.lower()
    if is_elite_original_practice_source(normalized) or "v6_elite_original" in normalized or "elite_original_practice" in normalized:
        return BankImportSpec(
            bank_role=BANK_ROLE_ELITE_ORIGINAL_PRACTICE,
            source_bank=Path(source_name).stem,
            active=True,
            eligible_for_study=True,
            eligible_for_cat=True,
            eligible_for_review=True,
            allow_duplicate_canonical=True,
        )
    if "score_simulator" in normalized:
        return BankImportSpec(
            bank_role=BANK_ROLE_SCORE_SIMULATOR,
            source_bank=Path(source_name).stem,
            active=False,
            eligible_for_study=False,
            eligible_for_cat=False,
            eligible_for_review=False,
            is_simulator=True,
            allow_duplicate_canonical=True,
        )
    if "quality_patch" in normalized:
        return BankImportSpec(
            bank_role=BANK_ROLE_QUALITY_PATCH,
            source_bank=Path(source_name).stem,
            active=True,
            eligible_for_study=True,
            eligible_for_cat=True,
            eligible_for_review=True,
        )
    if "production_ready_47" in normalized:
        return BankImportSpec(
            bank_role=BANK_ROLE_PUBLIC_PC_IMPORT,
            source_bank=Path(source_name).stem,
            active=True,
            eligible_for_study=True,
            eligible_for_cat=True,
            eligible_for_review=True,
            is_public_import=True,
        )
    if "exact_import_all_50" in normalized or "exact_all_50" in normalized:
        return BankImportSpec(
            bank_role=BANK_ROLE_REVIEW_ARCHIVE,
            source_bank=Path(source_name).stem,
            active=False,
            eligible_for_study=False,
            eligible_for_cat=False,
            eligible_for_review=False,
            allow_duplicate_canonical=True,
            force_needs_review=True,
        )
    return BankImportSpec(
        bank_role=BANK_ROLE_MAIN_PRACTICE,
        source_bank=Path(source_name).stem,
        active=True,
        eligible_for_study=True,
        eligible_for_cat=True,
        eligible_for_review=True,
    )


def _iter_package_sources(file_path: Path) -> list[tuple[Path, pd.DataFrame]]:
    if file_path.suffix.lower() != ".zip":
        return [(file_path, _load_dataframe(file_path))]

    settings = get_settings()
    extract_root = settings.upload_dir / f"{file_path.stem}_{uuid4().hex}"
    extract_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(file_path) as archive:
        archive.extractall(extract_root)

    sources: list[tuple[Path, pd.DataFrame]] = []
    preferred_filenames = {
        "asvab_v5_1_quality_patch_5000.json",
        "asvab_score_simulator_bank_v1_800_clean.json",
        "open_pc50_production_ready_47.json",
        "open_pc50_exact_import_all_50_with_flags.json",
    }
    preferred_candidates: list[Path] = []
    for candidate in sorted(extract_root.rglob("*")):
        if not candidate.is_file() or candidate.suffix.lower() not in DATA_EXTENSIONS:
            continue
        lowered = candidate.name.lower()
        if any(part in lowered for part in SKIP_NAME_PARTS):
            continue
        if candidate.name.lower() in preferred_filenames:
            preferred_candidates.append(candidate)
        try:
            sources.append((candidate, _load_dataframe(candidate)))
        except Exception:
            continue
    if preferred_candidates:
        sources = []
        for candidate in sorted(preferred_candidates):
            try:
                sources.append((candidate, _load_dataframe(candidate)))
            except Exception:
                continue
    return sources


def _load_asset_svg(source_path: Path, asset_path: str | None) -> str | None:
    if not asset_path:
        return None
    candidate = (source_path.parent / asset_path).resolve()
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    if source_path.suffix.lower() == ".zip":
        return None
    return None


def _store_asset_svg(source_path: Path, asset_path: str | None, source_bank: str) -> str | None:
    if not asset_path:
        return None
    candidate = (source_path.parent / asset_path).resolve()
    if not candidate.exists():
        return None
    settings = get_settings()
    stored_path = (Path(source_bank) / Path(asset_path)).as_posix()
    destination = settings.question_assets_dir / stored_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(candidate, destination)
    return stored_path


def _normalize_skill_tags(raw_value: object) -> list[str] | None:
    if isinstance(raw_value, list):
        cleaned = [normalize_skill_tag(item) for item in raw_value if str(item).strip()]
        return cleaned or None
    if isinstance(raw_value, tuple):
        cleaned = [normalize_skill_tag(item) for item in raw_value if str(item).strip()]
        return cleaned or None
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            cleaned = [normalize_skill_tag(item) for item in parsed if str(item).strip()]
            return cleaned or None
        cleaned = [normalize_skill_tag(part) for part in re.split(r"[|,;/]+", text) if part.strip()]
        return cleaned or None
    return None


def _is_placeholder_text(value: str) -> bool:
    lowered = value.lower()
    return any(
        token in lowered
        for token in (
            "(1)",
            "lorem ipsum",
            "placeholder",
            "todo",
            "answer here",
            "insert",
            "sample text",
        )
    )


def _validate_record(record: dict[str, object], *, strict: bool) -> list[str]:
    errors: list[str] = []
    choices = _normalize_choices(record.get("choices"))
    if len(choices) != 4:
        errors.append("choices must contain exactly four options.")
    if len({choice.strip().lower() for choice in choices}) < 4:
        errors.append("duplicate choice text detected.")
    question_text = _text(record.get("question"))
    if not question_text:
        errors.append("question text is empty.")
    if _is_placeholder_text(question_text):
        errors.append("question text contains placeholder residue.")
    for choice in choices:
        if _is_placeholder_text(choice):
            errors.append("choice text contains placeholder residue.")
            break
    answer_index = record.get("answer_index")
    try:
        answer_index_int = int(answer_index)
    except (TypeError, ValueError):
        answer_index_int = -1
    if answer_index_int < 0 or answer_index_int >= len(choices):
        errors.append("answer_index is out of range.")
    answer_text = _text(record.get("answer_text"))
    if answer_index_int >= 0 and answer_index_int < len(choices):
        if answer_text and normalize_choice_text(answer_text) != normalize_choice_text(choices[answer_index_int]):
            errors.append("answer_text does not match answer_index.")
    if strict and record.get("choices") is not None and len(choices) == 4:
        if len({normalize_choice_text(choice) for choice in choices}) < 4:
            errors.append("duplicate choices are not allowed in active imports.")
    return errors


def _derived_skill_tag(record: dict[str, object]) -> str:
    skill_tags = record.get("skill_tags")
    if isinstance(skill_tags, list) and skill_tags:
        return normalize_skill_tag(skill_tags[0])
    if isinstance(skill_tags, str) and skill_tags.strip():
        parsed = _parse_jsonish(skill_tags)
        if isinstance(parsed, list) and parsed:
            return normalize_skill_tag(parsed[0])
    subtype = _text(record.get("subtype"))
    if subtype:
        return normalize_skill_tag(subtype)
    return normalize_skill_tag(record.get("grade_anchor") or record.get("section") or "general")


def _build_payload(
    *,
    source_path: Path,
    record: dict[str, object],
    spec: BankImportSpec,
    existing_question: Question | None,
) -> dict[str, object]:
    question_text = _text(record.get("question"))
    choices = _choice_map(record.get("choices"))
    section = normalize_section_name(_text(record.get("section")))
    qid = _text(record.get("qid") or record.get("question_id") or record.get("id")) or None
    answer_index = _optional_int(record.get("answer_index"))
    if answer_index is None:
        raise ValueError("answer_index is missing or invalid.")
    correct_answer = "ABCD"[answer_index]
    difficulty_level = normalize_difficulty(record.get("difficulty_num") or record.get("difficulty"))
    difficulty_label = _text(record.get("difficulty")) or None
    elite_mode = spec.bank_role == BANK_ROLE_ELITE_ORIGINAL_PRACTICE
    source_bank = _text(record.get("source_bank")) or spec.source_bank
    source_id = _text(record.get("source_id")) or None
    skill_tags = _normalize_skill_tags(record.get("skill_tags"))
    skill_tag = skill_tags[0] if skill_tags else _derived_skill_tag(record)
    subtype = _text(record.get("subtype")) or None
    concept_tag = _text(record.get("concept_tag")) or subtype or skill_tag
    question_type = _text(record.get("question_type")) or None
    template_family = _text(record.get("template_family")) or subtype or concept_tag
    variant_signature = _text(record.get("variant_signature")) or f"{section}:{template_family}:{qid or sha1(question_text.encode('utf-8')).hexdigest()[:12]}"
    source_alignment = _text(record.get("grade_anchor") or record.get("source_style") or record.get("composite_relevance")) or None
    source_profile = _text(record.get("source_style") or record.get("composite_relevance")) or None
    expected_time_sec = record.get("expected_time_sec")
    expected_time_sec_int = _optional_int(expected_time_sec)
    paper_helpful = _as_bool(record.get("paper_helpful"), default=False)
    passage_text = _text(record.get("passage_text") or record.get("passage")) or None
    passage_word_count = (
        _optional_int(record.get("passage_word_count"))
        if _text(record.get("passage_word_count"))
        else (len([part for part in passage_text.split() if part.strip()]) if passage_text else None)
    )
    has_figure = bool(record.get("asset_path")) or bool(record.get("figure_svg"))
    figure_svg = _text(record.get("figure_svg")) or None
    asset_path = _text(record.get("asset_path")) or None
    stored_asset_path = _store_asset_svg(source_path, asset_path, source_bank) if asset_path else None
    if has_figure and not figure_svg and asset_path:
        figure_svg = _load_asset_svg(source_path, asset_path)
    figure_alt_text = _text(record.get("figure_alt_text")) or None
    if has_figure and not figure_alt_text:
        figure_alt_text = f"{section} {template_family}".strip()
    figure_type = _text(record.get("figure_type")) or ("svg" if has_figure else None)
    figure_quality_status = _text(record.get("figure_quality_status")) or ("generated_svg" if figure_svg else "no_figure_needed")
    explanation = _text(record.get("explanation")) or None
    quick_method = _text(record.get("quick_method")) or None
    wrong_answer_explanation = _text(record.get("wrong_answer_explanation")) or None
    observed_rate = record.get("observed_correct_rate_estimate") or record.get("empirical_accuracy")
    sample_size = record.get("sample_size_estimate")
    if sample_size is None or _text(sample_size) == "":
        sample_size = record.get("times_seen")
    confidence = _text(record.get("confidence")) or None
    copyright_status = _text(record.get("copyright_status")) or None
    license_status = _text(record.get("license_status")) or None
    content_status = _text(record.get("content_status")) or ("verified" if spec.active else "archived")
    validation_status = _text(record.get("validation_status")) or ("passed" if spec.active else "passed")
    needs_review = _as_bool(record.get("needs_review"), default=spec.force_needs_review or False)
    if spec.force_needs_review:
        needs_review = True
    times_seen_value = _optional_int(record.get("times_seen")) or 0
    times_correct_value = _optional_int(record.get("times_correct")) or 0
    average_response_time_value = _optional_float(record.get("avg_time_sec")) or _optional_float(record.get("average_response_time_seconds"))
    difficulty_num_value = _optional_int(record.get("difficulty_num")) or difficulty_level
    calibrated_difficulty_num_value = (
        float(record.get("calibrated_difficulty_num"))
        if _text(record.get("calibrated_difficulty_num"))
        else float(difficulty_num_value)
    )
    bank_role = normalize_bank_role(_text(record.get("bank_role")) or spec.bank_role) or spec.bank_role
    is_simulator = _as_bool(record.get("is_simulator"), default=spec.is_simulator)
    is_public_import = _as_bool(record.get("is_public_import"), default=spec.is_public_import)
    active_flag = _as_bool(record.get("active"), default=_as_bool(record.get("is_active"), default=spec.active))
    eligible_for_study_flag = _as_bool(record.get("eligible_for_study"), default=spec.eligible_for_study)
    eligible_for_cat_flag = _as_bool(record.get("eligible_for_cat"), default=spec.eligible_for_cat)
    eligible_for_review_flag = _as_bool(record.get("eligible_for_review"), default=spec.eligible_for_review)
    content_origin = _text(record.get("content_origin")) or None
    if elite_mode and not (
        content_status == "verified"
        and validation_status == "passed"
        and active_flag
        and eligible_for_study_flag
        and not needs_review
    ):
        raise ValueError("elite original practice row does not meet import conditions.")
    if elite_mode:
        active_flag = True
    payload = {
        "id": (
            existing_question.id
            if existing_question
            else (
                f"pkg_{source_path.stem}_{qid}"
                if qid
                else f"pkg_{source_path.stem}_{generate_stable_question_id(qid, section, question_text, choices)}"
            )
        ),
        "source_question_id": qid,
        "source_id": source_id,
        "canonical_hash": canonical_hash_for_question(question_text, choices),
        "section": section,
        "skill_tag": skill_tag,
        "skill_tags": skill_tags,
        "concept_tag": concept_tag,
        "question_type": question_type,
        "subtype": subtype,
        "template_family": template_family,
        "variant_signature": variant_signature,
        "reasoning_steps": 1 if difficulty_level <= 2 else 2 if difficulty_level == 3 else 3 if difficulty_level == 4 else 4,
        "formula_stack": _parse_jsonish(record.get("formula_stack")) if elite_mode else None,
        "concept_stack": [concept_tag, skill_tag, template_family],
        "trap_type": _text(record.get("trap_type")) or None,
        "difficulty_level": difficulty_level,
        "difficulty_label": difficulty_label,
        "calibrated_difficulty_level": difficulty_level,
        "difficulty_num": difficulty_num_value,
        "calibrated_difficulty_num": calibrated_difficulty_num_value,
        "irt_a": float(record.get("irt_a") or default_irt_values(difficulty_level)[0]),
        "irt_b": float(record.get("irt_b") or difficulty_irt_b(difficulty_level)),
        "irt_c": float(record.get("irt_c") or default_irt_values(difficulty_level)[2]),
        "expected_time_sec": expected_time_sec_int,
        "paper_helpful": paper_helpful,
        "passage_id": _text(record.get("passage_id")) or None,
        "passage_topic": _text(record.get("passage_topic")) or None,
        "passage_text": passage_text,
        "passage_word_count": passage_word_count,
        "question_stem": _text(record.get("question_stem")) or None,
        "vocab_word": _text(record.get("vocab_word")) or None,
        "part_of_speech": _text(record.get("part_of_speech")) or None,
        "question_text": question_text,
        "choice_a": choices["A"],
        "choice_b": choices["B"],
        "choice_c": choices["C"],
        "choice_d": choices["D"],
        "correct_answer": correct_answer,
        "correct_value": _text(record.get("answer_text")) or choices[correct_answer],
        "definition": _text(record.get("definition")) or None,
        "has_figure": has_figure,
        "requires_figure": has_figure,
        "figure_type": figure_type,
        "figure_svg": figure_svg,
        "figure_alt_text": figure_alt_text,
        "figure_quality_status": figure_quality_status,
        "base_explanation": explanation,
        "wrong_answer_explanation": wrong_answer_explanation,
        "quick_method": quick_method,
        "source_name": source_path.stem,
        "source_bank": source_bank,
        "bank_role": bank_role,
        "source_alignment": source_alignment,
        "source_url": _text(record.get("source_url")) or None,
        "source_confidence": "estimated",
        "source_profile": source_profile,
        "content_origin": content_origin,
        "reading_source_profile": _text(record.get("reading_source_profile")) or None,
        "lexical_source_profile": _text(record.get("lexical_source_profile")) or None,
        "frequency_source_profile": _text(record.get("frequency_source_profile")) or None,
        "confidence": confidence,
        "copyright_status": copyright_status or ("open_share" if spec.is_public_import else "original"),
        "license_status": license_status or ("open_share" if spec.is_public_import else "original_generated"),
        "content_status": content_status,
        "needs_review": needs_review,
        "issue_notes": _text(record.get("issue_notes")) or None,
        "complexity_score": int(record.get("complexity_score")) if _text(record.get("complexity_score")) else None,
        "generation_method": "clean_package_import",
        "validator_name": "bank_package_import",
        "validation_status": validation_status,
        "times_seen": times_seen_value,
        "times_correct": times_correct_value,
        "sample_size_estimate": int(sample_size) if _text(sample_size) else None,
        "observed_correct_rate": float(observed_rate) if _text(observed_rate) else None,
        "empirical_accuracy": None,
        "average_response_time_seconds": average_response_time_value,
        "avg_time_sec": average_response_time_value,
        "flagged_ambiguous_count": 0,
        "active": active_flag,
        "is_simulator": is_simulator,
        "is_public_import": is_public_import,
        "eligible_for_study": eligible_for_study_flag,
        "eligible_for_cat": eligible_for_cat_flag,
        "eligible_for_review": eligible_for_review_flag,
        "asset_path": stored_asset_path,
    }
    if spec.active and content_status == "verified" and validation_status == "passed" and not needs_review:
        payload["active"] = True
    else:
        payload["active"] = False if spec.is_simulator or spec.bank_role == BANK_ROLE_REVIEW_ARCHIVE else spec.active
    if payload["has_figure"] and not payload["figure_svg"] and not payload["asset_path"]:
        payload["needs_review"] = True
        payload["active"] = False
        payload["eligible_for_study"] = False
        payload["eligible_for_cat"] = False
    return payload


def _maybe_update_existing_active_question(db: Session, payload: dict[str, object]) -> Question | None:
    canonical_hash = payload["canonical_hash"]
    existing = db.scalar(
        select(Question).where(
            Question.canonical_hash == canonical_hash,
            Question.bank_role != BANK_ROLE_SCORE_SIMULATOR,
        )
    )
    if existing is None:
        return None
    for key, value in payload.items():
        setattr(existing, key, value)
    return existing


def _collect_package_qa_issues(source_files: list[Path], db: Session) -> list[str]:
    issues: list[str] = []
    seen_by_source_role: dict[str, set[str]] = defaultdict(set)
    hash_counts_by_source_role: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    simulator_hashes: set[str] = set()

    existing_bank_hashes: dict[str, set[str]] = {}
    for bank_role in (BANK_ROLE_QUALITY_PATCH, BANK_ROLE_PUBLIC_PC_IMPORT, BANK_ROLE_ELITE_ORIGINAL_PRACTICE):
        hashes = set(
            db.scalars(
                select(Question.canonical_hash).where(
                    Question.bank_role == bank_role,
                    Question.active.is_(True),
                    Question.content_status.in_({"verified", "active"}),
                    Question.duplicate_of_question_id.is_(None),
                    Question.canonical_hash.is_not(None),
                )
            ).all()
        )
        existing_bank_hashes[bank_role] = {item for item in hashes if item}

    for source_file in source_files:
        dataframe = _load_dataframe(source_file)
        spec = _resolve_bank_spec(source_file.name)
        rows = dataframe.fillna("").to_dict(orient="records")
        for row_index, record in enumerate(rows, start=2):
            row_errors = _validate_record(record, strict=spec.active and spec.bank_role != BANK_ROLE_REVIEW_ARCHIVE)
            for message in row_errors:
                issues.append(f"{source_file.name} row {row_index}: {message}")
            choices = _choice_map(record.get("choices"))
            if not choices:
                continue
            canonical_hash = canonical_hash_for_question(_text(record.get("question")), choices)
            seen_by_source_role[spec.bank_role].add(canonical_hash)
            hash_counts_by_source_role[spec.bank_role][canonical_hash] += 1
            asset_path = _text(record.get("asset_path"))
            has_figure = bool(asset_path) or bool(_text(record.get("figure_svg")))
            if has_figure and not asset_path and not _text(record.get("figure_svg")):
                issues.append(f"{source_file.name} row {row_index}: figure item is missing SVG asset reference.")
            if asset_path:
                candidate = (source_file.parent / asset_path).resolve()
                if not candidate.exists():
                    issues.append(f"{source_file.name} row {row_index}: missing figure asset '{asset_path}'.")
        if spec.is_simulator:
            simulator_hashes |= seen_by_source_role[spec.bank_role]

    for bank_role, counts in hash_counts_by_source_role.items():
        if bank_role in {BANK_ROLE_SCORE_SIMULATOR, BANK_ROLE_REVIEW_ARCHIVE}:
            continue
        for canonical_hash, count in counts.items():
            if count > 1 and bank_role == BANK_ROLE_ELITE_ORIGINAL_PRACTICE:
                issues.append(
                    f"{bank_role}: duplicate canonical hash {canonical_hash[:12]} appears {count} times in source package."
                )

    for canonical_hash in sorted(simulator_hashes):
        if canonical_hash in seen_by_source_role[BANK_ROLE_QUALITY_PATCH]:
            issues.append(
                f"simulator overlap: canonical hash {canonical_hash[:12]} already exists in quality_patch package rows."
            )
        if canonical_hash in seen_by_source_role[BANK_ROLE_PUBLIC_PC_IMPORT]:
            issues.append(
                f"simulator overlap: canonical hash {canonical_hash[:12]} already exists in public_pc_import package rows."
            )
        if canonical_hash in existing_bank_hashes[BANK_ROLE_QUALITY_PATCH]:
            issues.append(
                f"simulator overlap: canonical hash {canonical_hash[:12]} already exists in quality_patch active bank."
            )
        if canonical_hash in existing_bank_hashes[BANK_ROLE_PUBLIC_PC_IMPORT]:
            issues.append(
                f"simulator overlap: canonical hash {canonical_hash[:12]} already exists in public_pc_import active bank."
            )

    return issues


def _resolve_package_source_files(file_path: Path) -> tuple[list[Path], Path | None]:
    settings = get_settings()
    if file_path.suffix.lower() != ".zip":
        return [file_path], None

    extracted_root = settings.upload_dir / f"{file_path.stem}_{uuid4().hex}"
    extracted_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(file_path) as archive:
        archive.extractall(extracted_root)
    source_files = [
        path
        for path in sorted(extracted_root.rglob("*"))
        if path.is_file() and path.suffix.lower() in DATA_EXTENSIONS and not any(part in path.name.lower() for part in SKIP_NAME_PARTS)
    ]
    preferred_filenames = {
        "asvab_v5_1_quality_patch_5000.json",
        "asvab_score_simulator_bank_v1_800_clean.json",
        "open_pc50_production_ready_47.json",
        "open_pc50_exact_import_all_50_with_flags.json",
    }
    preferred_source_files = [
        path
        for path in source_files
        if path.suffix.lower() == ".json" and path.name.lower() in preferred_filenames
    ]
    if preferred_source_files:
        source_files = preferred_source_files
    else:
        json_source_files = [path for path in source_files if path.suffix.lower() == ".json"]
        if json_source_files:
            source_files = json_source_files
    return source_files, extracted_root


def import_bank_package_file(file_path: Path, db: Session) -> ImportLog:
    settings = get_settings()
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    failures: list[str] = []

    source_files, extracted_root = _resolve_package_source_files(file_path)

    qa_issues = _collect_package_qa_issues(source_files, db)
    if qa_issues:
        if extracted_root and extracted_root.exists():
            shutil.rmtree(extracted_root, ignore_errors=True)
        raise ValueError(
            "Package QA failed.\n" + json.dumps({"issues": qa_issues[:200], "issue_count": len(qa_issues)}, indent=2)
        )

    existing_questions = {question.id: question for question in db.scalars(select(Question)).all()}
    existing_canonical_index = {
        question.canonical_hash: question.id
        for question in existing_questions.values()
        if question.canonical_hash and question.active and question.content_status in {"verified", "active"} and question.duplicate_of_question_id is None
    }

    for source_file in source_files:
        try:
            dataframe = _load_dataframe(source_file)
        except Exception as exc:  # noqa: BLE001
            failed_count += 1
            failures.append(f"{source_file.name}: {exc}")
            continue

        spec = _resolve_bank_spec(source_file.name)
        rows = dataframe.fillna("").to_dict(orient="records")

        strict_validation = spec.active and spec.bank_role != BANK_ROLE_REVIEW_ARCHIVE
        validation_errors: list[str] = []
        for row_index, record in enumerate(rows, start=2):
            row_errors = _validate_record(record, strict=strict_validation)
            validation_errors.extend(f"{source_file.name} row {row_index}: {message}" for message in row_errors)
        if strict_validation and validation_errors:
            failed_count += len(validation_errors)
            failures.extend(validation_errors[:100])

        for row_index, record in enumerate(rows, start=2):
            try:
                question_text = _text(record.get("question"))
                choices = _choice_map(record.get("choices"))
                if len(choices) != 4:
                    raise ValueError("row does not contain four choices.")
                canonical_hash = canonical_hash_for_question(question_text, choices)
                existing_question = None
                if spec.active:
                    duplicate_question_id = existing_canonical_index.get(canonical_hash)
                    if duplicate_question_id:
                        if spec.allow_duplicate_canonical:
                            skipped_count += 1
                            continue
                        existing_question = existing_questions.get(duplicate_question_id)
                else:
                    qid = _text(record.get("qid") or record.get("question_id") or record.get("id")) or None
                    if qid:
                        existing_question = db.scalar(
                            select(Question).where(
                                Question.source_question_id == qid,
                                Question.bank_role == spec.bank_role,
                            )
                        )
                payload = _build_payload(
                    source_path=source_file,
                    record=record,
                    spec=spec,
                    existing_question=existing_question,
                )
                if not spec.active and existing_question is None and payload["bank_role"] == BANK_ROLE_REVIEW_ARCHIVE:
                    payload["active"] = False
                if existing_question is not None:
                    changed = False
                    for key, value in payload.items():
                        if getattr(existing_question, key) != value:
                            setattr(existing_question, key, value)
                            changed = True
                    if changed:
                        updated_count += 1
                    else:
                        skipped_count += 1
                    existing_questions[existing_question.id] = existing_question
                else:
                    question = Question(**payload)
                    db.add(question)
                    existing_questions[question.id] = question
                    if spec.active:
                        existing_canonical_index[canonical_hash] = question.id
                        imported_count += 1
                    else:
                        imported_count += 1
            except Exception as exc:  # noqa: BLE001
                failed_count += 1
                failures.append(f"{source_file.name} row {row_index}: {exc}")

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
                "imported_count": log.imported_count,
                "updated_count": log.updated_count,
                "skipped_count": log.skipped_count,
                "failed_count": log.failed_count,
                "messages": failures[:100],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if extracted_root and extracted_root.exists():
        shutil.rmtree(extracted_root, ignore_errors=True)
    return log

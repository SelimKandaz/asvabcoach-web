from __future__ import annotations

from app.models import Question


BANK_ROLE_MAIN_PRACTICE = "main_practice"
BANK_ROLE_QUALITY_PATCH = "quality_patch"
BANK_ROLE_ELITE_ORIGINAL_PRACTICE = "elite_original_practice"
BANK_ROLE_SCORE_SIMULATOR = "score_simulator"
BANK_ROLE_PUBLIC_PC_IMPORT = "public_pc_import"
BANK_ROLE_REVIEW_ARCHIVE = "review_archive"
BANK_ROLE_LEGACY = "legacy_seed"

REPLACEMENT_BANK_SOURCES = {
    "asvab_remaining_sections_replacement_bank_v2",
    "asvab_wk_wordnet_style_question_bank_v1",
    "asvab_pc_paragraph_comprehension_question_bank_v1",
}

ELITE_ORIGINAL_BANK_SOURCES = {
    "asvab_v6_elite_original",
}

SELECTABLE_CONTENT_STATUSES = {"verified", "active"}

BANK_ROLE_LABELS = {
    BANK_ROLE_MAIN_PRACTICE: "Main Practice",
    BANK_ROLE_QUALITY_PATCH: "Quality Patch",
    BANK_ROLE_ELITE_ORIGINAL_PRACTICE: "Elite Original Practice",
    BANK_ROLE_SCORE_SIMULATOR: "Score Simulator",
    BANK_ROLE_PUBLIC_PC_IMPORT: "Public PC Import",
    BANK_ROLE_REVIEW_ARCHIVE: "Review Archive",
    BANK_ROLE_LEGACY: "Legacy Seed",
}


def normalize_bank_role(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return text or None


def is_replacement_bank_source(source_name: str | None) -> bool:
    normalized = (source_name or "").strip().lower()
    return normalized in REPLACEMENT_BANK_SOURCES


def is_elite_original_practice_source(source_name: str | None) -> bool:
    normalized = (source_name or "").strip().lower()
    return normalized in ELITE_ORIGINAL_BANK_SOURCES


def bank_role_label(value: str | None) -> str:
    normalized = normalize_bank_role(value)
    if normalized is None:
        return BANK_ROLE_LABELS[BANK_ROLE_MAIN_PRACTICE]
    return BANK_ROLE_LABELS.get(normalized, normalized.replace("_", " ").title())


def is_simulator_question(question: Question) -> bool:
    return bool(question.is_simulator or normalize_bank_role(question.bank_role) == BANK_ROLE_SCORE_SIMULATOR)


def is_review_archive_question(question: Question) -> bool:
    return normalize_bank_role(question.bank_role) == BANK_ROLE_REVIEW_ARCHIVE


def is_public_import_question(question: Question) -> bool:
    return bool(question.is_public_import or normalize_bank_role(question.bank_role) == BANK_ROLE_PUBLIC_PC_IMPORT)


def is_practice_selectable_question(question: Question) -> bool:
    if not question.active:
        return False
    if question.content_status not in SELECTABLE_CONTENT_STATUSES:
        return False
    if question.duplicate_of_question_id is not None:
        return False
    if is_simulator_question(question):
        return False
    if is_review_archive_question(question):
        return False
    return True


def is_score_simulator_question(question: Question) -> bool:
    return is_simulator_question(question)


def is_hard_elite_practice_question(question: Question) -> bool:
    bank_role = normalize_bank_role(question.bank_role)
    return (
        bank_role in {BANK_ROLE_QUALITY_PATCH, BANK_ROLE_ELITE_ORIGINAL_PRACTICE}
        and not is_simulator_question(question)
        and not is_review_archive_question(question)
    )


def bank_role_default_for_mode(mode: str) -> str | None:
    if mode == BANK_ROLE_SCORE_SIMULATOR:
        return BANK_ROLE_SCORE_SIMULATOR
    return None

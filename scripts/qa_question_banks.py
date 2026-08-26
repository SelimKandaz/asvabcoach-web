from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_backend_qa(bank_role: str) -> dict[str, object]:
    payload = """
import json
from collections import Counter, defaultdict

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Question
from app.services.bank_rules import normalize_bank_role

BANK_ROLE = __BANK_ROLE__
SELECTABLE_STATUSES = {'verified', 'active'}

init_db()
normalized_bank_role = normalize_bank_role(BANK_ROLE) if BANK_ROLE != 'all' else None
with SessionLocal() as db:
    statement = select(Question)
    if normalized_bank_role:
        statement = statement.where(Question.bank_role == normalized_bank_role)
    questions = list(db.scalars(statement).all())

active_questions = [
    question
    for question in questions
    if question.active and question.content_status in SELECTABLE_STATUSES and not question.duplicate_of_question_id
]
by_section = Counter(question.section for question in active_questions)
by_difficulty = Counter(question.difficulty_level for question in active_questions)
by_template_family = Counter(question.template_family for question in active_questions)
by_variant_signature = Counter((question.section, question.variant_signature) for question in active_questions)

canonical_groups = defaultdict(list)
for question in active_questions:
    if question.canonical_hash:
        canonical_groups[question.canonical_hash].append(question.id)
duplicate_groups = [
    {'canonical_hash': canonical_hash, 'count': len(question_ids), 'question_ids': question_ids[:10]}
    for canonical_hash, question_ids in sorted(canonical_groups.items())
    if len(question_ids) > 1
]

output = {
    'bank_role': BANK_ROLE,
    'normalized_bank_role': normalized_bank_role,
    'total_questions': len(questions),
    'active_questions': len(active_questions),
    'is_simulator_questions': sum(1 for question in questions if question.is_simulator),
    'by_section': dict(sorted(by_section.items())),
    'by_difficulty': {str(level): count for level, count in sorted(by_difficulty.items())},
    'by_template_family': dict(sorted(by_template_family.items())),
    'by_variant_signature': {f'{section}:{variant}': count for (section, variant), count in sorted(by_variant_signature.items())},
    'duplicate_canonical_hash_count': len(duplicate_groups),
    'duplicate_canonical_hashes': duplicate_groups[:20],
    'missing_figure_svg_count': sum(1 for question in active_questions if question.has_figure and not question.figure_svg),
    'missing_asset_path_count': sum(1 for question in active_questions if question.has_figure and not question.asset_path),
}
print(json.dumps(output, indent=2))
"""
    payload = payload.replace("__BANK_ROLE__", repr(bank_role))
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
    parser = argparse.ArgumentParser(description="QA a bank role in the active question database.")
    parser.add_argument("--bank-role", required=True, help="Bank role to inspect, or 'all'.")
    args = parser.parse_args()
    print(json.dumps(_run_backend_qa(args.bank_role), indent=2))


if __name__ == "__main__":
    main()

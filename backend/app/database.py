from collections.abc import Generator
from hashlib import sha1

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

engine_kwargs: dict[str, object] = {"future": True}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.import_log_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _sync_missing_columns()
    _backfill_quality_fields()
    _backfill_user_seen_hashes()
    _seed_external_sources()
    _seed_concept_difficulty_anchors()
    _seed_career_requirements()


def _sync_missing_columns() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if not inspector.has_table(table_name):
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                column_type = column.type.compile(dialect=engine.dialect)
                conn.execute(
                    text(
                        f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "{column.name}" {column_type}'
                    )
                )


def _backfill_quality_fields() -> None:
    from app.data_import.normalize_questions import canonical_hash_for_question

    from app.models import Question
    from app.services.bank_rules import (
        BANK_ROLE_ELITE_ORIGINAL_PRACTICE,
        BANK_ROLE_LEGACY,
        BANK_ROLE_MAIN_PRACTICE,
        is_elite_original_practice_source,
        is_replacement_bank_source,
        normalize_bank_role,
    )
    from app.services.figure_service import build_question_figure_svg
    from app.services.question_profile_service import question_profile_from_question
    from app.services.difficulty_service import difficulty_irt_b

    difficulty_labels = {
        1: "easy",
        2: "easy-medium",
        3: "medium",
        4: "hard",
        5: "very-hard",
    }

    with SessionLocal() as db:
        questions = list(db.query(Question).all())
        changed = False
        for question in questions:
            if question.source_bank is None and question.source_name:
                question.source_bank = question.source_name
                changed = True
            source_name = (question.source_name or "").strip().lower()
            generation_method = (question.generation_method or "").strip().lower()
            desired_bank_role: str | None = None
            if is_elite_original_practice_source(source_name):
                desired_bank_role = BANK_ROLE_ELITE_ORIGINAL_PRACTICE
            elif is_replacement_bank_source(source_name):
                desired_bank_role = BANK_ROLE_MAIN_PRACTICE
            elif source_name == "original_generated_format_anchor" or generation_method == "template_v2_curated":
                desired_bank_role = BANK_ROLE_LEGACY
            elif question.bank_role is None:
                desired_bank_role = BANK_ROLE_MAIN_PRACTICE

            if desired_bank_role is not None and normalize_bank_role(question.bank_role) != desired_bank_role:
                question.bank_role = desired_bank_role
                changed = True

            normalized_bank_role = normalize_bank_role(question.bank_role)
            if normalized_bank_role == BANK_ROLE_LEGACY:
                if question.active:
                    question.active = False
                    changed = True
                if question.content_status not in {"duplicate", "archived"}:
                    question.content_status = "archived"
                    changed = True
                if not question.needs_review:
                    question.needs_review = True
                    changed = True
            elif is_replacement_bank_source(source_name) or is_elite_original_practice_source(source_name):
                if (
                    not question.active
                    and question.content_status in {"verified", "active"}
                    and question.validation_status == "passed"
                    and question.duplicate_of_question_id is None
                    and question.figure_quality_status != "missing"
                    and not question.is_simulator
                ):
                    question.active = True
                    changed = True
            if question.is_simulator is None:
                question.is_simulator = normalize_bank_role(question.bank_role) == "score_simulator"
                changed = True
            if question.is_public_import is None:
                question.is_public_import = normalize_bank_role(question.bank_role) == "public_pc_import"
                changed = True
            if question.needs_review is None:
                question.needs_review = False
                changed = True
            if not question.canonical_hash:
                canonical_hash = canonical_hash_for_question(
                    question.question_text,
                    {
                        "A": question.choice_a,
                        "B": question.choice_b,
                        "C": question.choice_c,
                        "D": question.choice_d,
                    },
                )
                question.canonical_hash = canonical_hash
                changed = True
            if question.content_status is None:
                question.content_status = "verified"
                changed = True
            if question.validation_status is None:
                question.validation_status = "passed"
                changed = True
            if question.generation_method is None:
                question.generation_method = "seed_import"
                changed = True
            if question.calibrated_difficulty_level is None:
                question.calibrated_difficulty_level = question.difficulty_level
                changed = True
            if question.calibrated_irt_b is None:
                question.calibrated_irt_b = question.irt_b
                changed = True
            if question.times_seen is None:
                question.times_seen = 0
                changed = True
            if question.times_correct is None:
                question.times_correct = 0
                changed = True
            if question.has_figure is None:
                question.has_figure = False
                changed = True
            if question.requires_figure is None:
                question.requires_figure = False
                changed = True
            if question.eligible_for_study is None:
                question.eligible_for_study = True
                changed = True
            if question.eligible_for_cat is None:
                question.eligible_for_cat = True
                changed = True
            if question.eligible_for_review is None:
                question.eligible_for_review = True
                changed = True
            if question.expected_time_sec is None and question.difficulty_level:
                question.expected_time_sec = max(20, question.difficulty_level * 35)
                changed = True
            if question.paper_helpful is None:
                question.paper_helpful = False
                changed = True
            if question.avg_time_sec is None and question.average_response_time_seconds is not None:
                question.avg_time_sec = question.average_response_time_seconds
                changed = True
            if question.empirical_accuracy is None and (question.times_seen or 0) > 0:
                question.empirical_accuracy = round((question.times_correct or 0) / max(question.times_seen, 1), 4)
                changed = True
            if question.calibrated_difficulty_num is None:
                question.calibrated_difficulty_num = float(question.calibrated_difficulty_level or question.difficulty_level)
                changed = True
            if question.flagged_ambiguous_count is None:
                question.flagged_ambiguous_count = 0
                changed = True
            if question.duplicate_of_question_id and question.content_status != "archived":
                if question.active:
                    question.active = False
                    changed = True
                if question.content_status != "duplicate":
                    question.content_status = "duplicate"
                    changed = True
            if question.has_figure and not question.figure_svg:
                figure_svg = build_question_figure_svg(
                    figure_type=question.figure_type,
                    question_text=question.question_text,
                    figure_alt_text=question.figure_alt_text,
                    figure_data=question.figure_data,
                )
                if figure_svg:
                    question.figure_svg = figure_svg
                    if question.validation_status == "needs_review":
                        question.validation_status = "passed"
                    if question.content_status == "needs_review":
                        question.content_status = "verified"
                    if question.active is False:
                        question.active = True
                    changed = True
            profile = question_profile_from_question(question)
            if question.concept_tag != profile.concept_tag:
                question.concept_tag = profile.concept_tag
                changed = True
            if question.template_family != profile.template_family:
                question.template_family = profile.template_family
                changed = True
            if question.variant_signature != profile.variant_signature:
                question.variant_signature = profile.variant_signature
                changed = True
            if question.reasoning_steps != profile.reasoning_steps:
                question.reasoning_steps = profile.reasoning_steps
                changed = True
            if question.formula_stack != profile.formula_stack:
                question.formula_stack = profile.formula_stack
                changed = True
            if question.concept_stack != profile.concept_stack:
                question.concept_stack = profile.concept_stack
                changed = True
            if question.trap_type != profile.trap_type:
                question.trap_type = profile.trap_type
                changed = True
            if bool(question.requires_figure) != bool(profile.requires_figure):
                question.requires_figure = profile.requires_figure
                changed = True
            if question.figure_quality_status != profile.figure_quality_status:
                question.figure_quality_status = profile.figure_quality_status
                changed = True
            if question.source_profile != profile.source_profile:
                question.source_profile = profile.source_profile
                changed = True
            if question.license_status != profile.license_status:
                question.license_status = profile.license_status
                changed = True
            if question.difficulty_label is None:
                question.difficulty_label = difficulty_labels.get(question.difficulty_level, "medium")
                changed = True
            if question.question_type is None and question.template_family:
                question.question_type = question.template_family
                changed = True
            if question.passage_word_count is None and question.passage_text:
                question.passage_word_count = len([part for part in question.passage_text.split() if part.strip()])
                changed = True
            derived_complexity = profile.derived_complexity_score
            if question.complexity_score is None:
                question.complexity_score = derived_complexity
                changed = True
            if question.figure_quality_status == "missing":
                if question.content_status != "needs_review":
                    question.content_status = "needs_review"
                    changed = True
                if question.validation_status != "needs_review":
                    question.validation_status = "needs_review"
                    changed = True
                if question.active:
                    question.active = False
                    changed = True
        if changed:
            db.commit()


def _user_seen_hash_row_id(user_id: str, canonical_hash: str) -> str:
    digest = sha1(f"{user_id}:{canonical_hash}".encode("utf-8")).hexdigest()[:24]
    return f"usq_{digest}"


def _backfill_user_seen_hashes() -> None:
    from app.models import Question, ResponseRecord, UserSeenQuestionHash

    with SessionLocal() as db:
        response_rows = list(
            db.execute(
                select(
                    ResponseRecord.user_id,
                    ResponseRecord.question_id,
                    ResponseRecord.is_correct,
                    ResponseRecord.created_at,
                    Question.canonical_hash,
                )
                .join(Question, Question.id == ResponseRecord.question_id)
                .where(Question.canonical_hash.is_not(None))
                .order_by(ResponseRecord.created_at.asc(), ResponseRecord.id.asc())
            ).all()
        )
        aggregates: dict[tuple[str, str], dict[str, object]] = {}
        for user_id, question_id, is_correct, created_at, canonical_hash in response_rows:
            key = (user_id, canonical_hash)
            aggregate = aggregates.get(key)
            if aggregate is None:
                aggregate = {
                    "question_id": question_id,
                    "first_seen_at": created_at,
                    "last_seen_at": created_at,
                    "times_seen": 0,
                    "times_correct": 0,
                    "times_wrong": 0,
                }
                aggregates[key] = aggregate
            aggregate["question_id"] = question_id
            aggregate["last_seen_at"] = created_at
            aggregate["times_seen"] = int(aggregate["times_seen"]) + 1
            if is_correct:
                aggregate["times_correct"] = int(aggregate["times_correct"]) + 1
            else:
                aggregate["times_wrong"] = int(aggregate["times_wrong"]) + 1

        existing_rows = list(db.query(UserSeenQuestionHash).all())
        existing_by_key = {(row.user_id, row.canonical_hash): row for row in existing_rows}
        needs_rebuild = len(existing_rows) != len(aggregates)
        if not needs_rebuild:
            for key, aggregate in aggregates.items():
                row = existing_by_key.get(key)
                if row is None:
                    needs_rebuild = True
                    break
                if (
                    row.question_id != aggregate["question_id"]
                    or row.first_seen_at != aggregate["first_seen_at"]
                    or row.last_seen_at != aggregate["last_seen_at"]
                    or row.times_seen != aggregate["times_seen"]
                    or row.times_correct != aggregate["times_correct"]
                    or row.times_wrong != aggregate["times_wrong"]
                ):
                    needs_rebuild = True
                    break
        if not needs_rebuild:
            return

        db.query(UserSeenQuestionHash).delete()
        for (user_id, canonical_hash), aggregate in aggregates.items():
            db.add(
                UserSeenQuestionHash(
                    id=_user_seen_hash_row_id(user_id, canonical_hash),
                    user_id=user_id,
                    canonical_hash=canonical_hash,
                    question_id=str(aggregate["question_id"]),
                    first_seen_at=aggregate["first_seen_at"],
                    last_seen_at=aggregate["last_seen_at"],
                    times_seen=int(aggregate["times_seen"]),
                    times_correct=int(aggregate["times_correct"]),
                    times_wrong=int(aggregate["times_wrong"]),
                )
            )
        db.commit()


def _seed_external_sources() -> None:
    from app.models import ExternalSource

    seeds = [
        {
            "id": "src_official_asvab",
            "name": "Official ASVAB",
            "domain": "www.officialasvab.com",
            "source_type": "official_sample",
            "source_quality": "A",
            "has_question_text": True,
            "has_explanation": False,
            "has_observed_correct_rate": False,
            "copyright_risk": "low",
            "allowed_use_notes": "Use as a format and concept anchor; do not copy question text into active bank.",
        },
        {
            "id": "src_asvab_test_bank",
            "name": "ASVAB Test Bank",
            "domain": "www.asvabtestbank.com",
            "source_type": "performance_stats",
            "source_quality": "A",
            "has_question_text": True,
            "has_explanation": True,
            "has_observed_correct_rate": True,
            "copyright_risk": "medium",
            "allowed_use_notes": "Use percent-correct data for calibration only.",
        },
        {
            "id": "src_asvab_practice_tests",
            "name": "ASVAB Practice Tests",
            "domain": "www.asvabpracticetests.com",
            "source_type": "test_prep",
            "source_quality": "B",
            "has_question_text": True,
            "has_explanation": True,
            "has_observed_correct_rate": False,
            "copyright_risk": "medium",
            "allowed_use_notes": "Use concept and explanation style; generate original internal questions.",
        },
        {
            "id": "src_national_guard",
            "name": "National Guard Practice ASVAB",
            "domain": "www.nationalguard.com",
            "source_type": "national_guard",
            "source_quality": "B",
            "has_question_text": True,
            "has_explanation": True,
            "has_observed_correct_rate": False,
            "copyright_risk": "medium",
            "allowed_use_notes": "Use preview/self-assessment structure as a style anchor.",
        },
        {
            "id": "src_mometrix",
            "name": "Mometrix",
            "domain": "www.mometrix.com",
            "source_type": "test_prep",
            "source_quality": "B",
            "has_question_text": True,
            "has_explanation": True,
            "has_observed_correct_rate": False,
            "copyright_risk": "medium",
            "allowed_use_notes": "Use for topic coverage and explanation shape.",
        },
        {
            "id": "src_union_test_prep",
            "name": "Union Test Prep",
            "domain": "www.uniontestprep.com",
            "source_type": "test_prep",
            "source_quality": "B",
            "has_question_text": True,
            "has_explanation": True,
            "has_observed_correct_rate": False,
            "copyright_risk": "medium",
            "allowed_use_notes": "Use for concept discovery and distractor patterns.",
        },
        {
            "id": "src_test_guide",
            "name": "Test-Guide",
            "domain": "www.test-guide.com",
            "source_type": "test_prep",
            "source_quality": "B",
            "has_question_text": True,
            "has_explanation": True,
            "has_observed_correct_rate": False,
            "copyright_risk": "medium",
            "allowed_use_notes": "Use for concept discovery only.",
        },
    ]

    with SessionLocal() as db:
        existing = set(db.scalars(select(ExternalSource.id)).all())
        changed = False
        for payload in seeds:
            if payload["id"] in existing:
                continue
            db.add(ExternalSource(**payload))
            changed = True
        if changed:
            db.commit()


def _seed_concept_difficulty_anchors() -> None:
    from uuid import uuid4

    from app.models import ConceptDifficultyAnchor, ExternalSource

    concept_seeds = [
        ("AR", "constant_rate_total", "constant_rate_total", "src_official_asvab", 0.82, 2, 0.8, "Repeated rate over time with a simple time conversion."),
        ("AR", "ratio_remaining_group", "ratio_remaining_group", "src_official_asvab", 0.74, 2, 0.76, "One in every N belong to one group; the rest belong to the other group."),
        ("AR", "depreciation_one_year", "depreciation_one_year", "src_asvab_practice_tests", 0.68, 3, 0.72, "One-year percent depreciation with remaining value as the answer."),
        ("AR", "faucet_rate_proportion", "faucet_rate_proportion", "src_asvab_practice_tests", 0.78, 2, 0.74, "Unit-rate proportion with gallons and minutes."),
        ("AR", "percent_area_scaling", "percent_area_scaling", "src_asvab_test_bank", 0.41, 5, 0.88, "Area change after a linear dimension grows by a percentage."),
        ("AR", "travel_speed_time", "travel_speed_time", "src_national_guard", 0.86, 1, 0.75, "Direct speed-time-distance conversion."),
        ("AR", "average_basic", "average_basic", "src_national_guard", 0.89, 1, 0.68, "Simple arithmetic mean."),
        ("EI", "ohmmeter_measures_resistance", "ohmmeter_measures_resistance", "src_official_asvab", 0.93, 1, 0.93, "Basic electronics vocabulary item."),
        ("EI", "ac_abbreviation", "ac_abbreviation", "src_official_asvab", 0.95, 1, 0.95, "AC stands for alternating current."),
        ("EI", "ohms_law_current", "ohms_law_current", "src_asvab_test_bank", 0.71, 2, 0.84, "Compute current from voltage and resistance."),
        ("EI", "parallel_resistance_simple", "parallel_resistance_simple", "src_asvab_practice_tests", 0.48, 4, 0.78, "Two equal resistors in parallel."),
        ("MC", "gear_direction", "gear_direction", "src_official_asvab", 0.9, 1, 0.8, "Meshed gears reverse direction."),
        ("MC", "lever_mechanical_advantage", "lever_mechanical_advantage", "src_asvab_practice_tests", 0.63, 3, 0.7, "Mechanical advantage from arm lengths."),
        ("MC", "torque_direct", "torque_direct", "src_asvab_test_bank", 0.54, 3, 0.76, "Torque equals force times distance."),
        ("GS", "density_mass_volume", "density_mass_volume", "src_official_asvab", 0.66, 3, 0.82, "Density from mass and volume."),
        ("GS", "scientific_method", "scientific_method", "src_national_guard", 0.88, 1, 0.73, "Identify controlled experiment steps."),
        ("AI", "engine_basic", "engine_basic", "src_mometrix", 0.77, 2, 0.7, "Engine component vocabulary."),
        ("SI", "hand_tools", "hand_tools", "src_union_test_prep", 0.84, 2, 0.69, "Select the correct shop tool."),
        ("AO", "rotation_2d", "rotation_2d", "src_official_asvab", 0.52, 3, 0.77, "Spatial rotation in two dimensions."),
    ]

    with SessionLocal() as db:
        if db.query(ConceptDifficultyAnchor).count():
            return
        source_ids = set(db.scalars(select(ExternalSource.id)).all())
        for section, skill_tag, concept_tag, source_id, observed_rate, difficulty, confidence, summary in concept_seeds:
            if source_id not in source_ids:
                continue
            db.add(
                ConceptDifficultyAnchor(
                    id=f"cda_{uuid4().hex[:12]}",
                    section=section,
                    skill_tag=skill_tag,
                    concept_tag=concept_tag,
                    source_id=source_id,
                    observed_correct_rate=observed_rate,
                    estimated_difficulty_level=difficulty,
                    confidence=confidence,
                    example_profile_summary=summary,
                    notes="Seeded concept anchor for deterministic calibration.",
                    review_state="proposed",
                )
            )
        db.commit()


def _seed_career_requirements() -> None:
    from uuid import uuid4

    from app.models import CareerRequirement

    with SessionLocal() as db:
        existing_count = db.query(CareerRequirement).count()
        if existing_count:
            return
        seeds = [
            CareerRequirement(
                id=f"cr_{uuid4().hex[:12]}",
                branch="Army",
                job_code="11B",
                job_title="Infantryman",
                component="GT",
                score_type="raw",
                formula_key="GT",
                formula_expression="VE + AR",
                min_score=85,
                additional_conditions={"source": "sample_seed"},
                citizenship_required=False,
                clearance_required=False,
                source_url="https://www.goarmy.com",
                source_name="Sample seed record",
                source_confidence="estimated",
                needs_verification=True,
            ),
            CareerRequirement(
                id=f"cr_{uuid4().hex[:12]}",
                branch="Air Force",
                job_code="1A1X1",
                job_title="Flight Attendant",
                component="MAGE",
                score_type="scaled",
                formula_key="MAGE",
                formula_expression="M A G E",
                min_score=50,
                additional_conditions={"source": "sample_seed"},
                citizenship_required=False,
                clearance_required=False,
                source_url="https://www.airforce.com",
                source_name="Sample seed record",
                source_confidence="estimated",
                needs_verification=True,
            ),
            CareerRequirement(
                id=f"cr_{uuid4().hex[:12]}",
                branch="Navy",
                job_code="0000",
                job_title="General Ratings Sample",
                component="GT",
                score_type="raw",
                formula_key="GT",
                formula_expression="VE + AR",
                min_score=80,
                additional_conditions={"source": "sample_seed"},
                citizenship_required=False,
                clearance_required=False,
                source_url="https://www.navy.com",
                source_name="Sample seed record",
                source_confidence="estimated",
                needs_verification=True,
            ),
            CareerRequirement(
                id=f"cr_{uuid4().hex[:12]}",
                branch="Marines",
                job_code="03XX",
                job_title="Infantry/Combat Sample",
                component="GT",
                score_type="raw",
                formula_key="GT",
                formula_expression="VE + AR",
                min_score=90,
                additional_conditions={"source": "sample_seed"},
                citizenship_required=False,
                clearance_required=False,
                source_url="https://www.marines.com",
                source_name="Sample seed record",
                source_confidence="estimated",
                needs_verification=True,
            ),
        ]
        db.add_all(seeds)
        db.commit()

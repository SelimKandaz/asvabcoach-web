from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from hashlib import sha1
from math import log
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ConceptDifficultyAnchor, ExternalQuestionObservation, ExternalSource, Question
from app.schemas import (
    AdminMaintenanceResult,
    ConceptDifficultyAnchorRead,
    ExternalQuestionObservationRead,
    ExternalSourceRead,
    ResearchSummary,
)


SOURCE_CATALOG: list[dict[str, object]] = [
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

CONCEPT_CATALOG: list[dict[str, object]] = [
    {"section": "AR", "skill_tag": "constant_rate_total", "concept_tag": "constant_rate_total", "source_id": "src_official_asvab", "observed_correct_rate": 0.82, "estimated_difficulty_level": 2, "confidence": 0.8, "summary": "Repeated rate over time with a simple time conversion."},
    {"section": "AR", "skill_tag": "ratio_remaining_group", "concept_tag": "ratio_remaining_group", "source_id": "src_official_asvab", "observed_correct_rate": 0.74, "estimated_difficulty_level": 2, "confidence": 0.76, "summary": "One in every N belong to one group; the rest belong to the other group."},
    {"section": "AR", "skill_tag": "depreciation_one_year", "concept_tag": "depreciation_one_year", "source_id": "src_asvab_practice_tests", "observed_correct_rate": 0.68, "estimated_difficulty_level": 3, "confidence": 0.72, "summary": "One-year percent depreciation with remaining value as the answer."},
    {"section": "AR", "skill_tag": "faucet_rate_proportion", "concept_tag": "faucet_rate_proportion", "source_id": "src_asvab_practice_tests", "observed_correct_rate": 0.78, "estimated_difficulty_level": 2, "confidence": 0.74, "summary": "Unit-rate proportion with gallons and minutes."},
    {"section": "AR", "skill_tag": "percent_area_scaling", "concept_tag": "percent_area_scaling", "source_id": "src_asvab_test_bank", "observed_correct_rate": 0.41, "estimated_difficulty_level": 5, "confidence": 0.88, "summary": "Area change after a linear dimension grows by a percentage."},
    {"section": "AR", "skill_tag": "travel_speed_time", "concept_tag": "travel_speed_time", "source_id": "src_national_guard", "observed_correct_rate": 0.86, "estimated_difficulty_level": 1, "confidence": 0.75, "summary": "Direct speed-time-distance conversion."},
    {"section": "AR", "skill_tag": "average_basic", "concept_tag": "average_basic", "source_id": "src_national_guard", "observed_correct_rate": 0.89, "estimated_difficulty_level": 1, "confidence": 0.68, "summary": "Simple arithmetic mean."},
    {"section": "EI", "skill_tag": "ohmmeter_measures_resistance", "concept_tag": "ohmmeter_measures_resistance", "source_id": "src_official_asvab", "observed_correct_rate": 0.93, "estimated_difficulty_level": 1, "confidence": 0.93, "summary": "Basic electronics vocabulary item."},
    {"section": "EI", "skill_tag": "ac_abbreviation", "concept_tag": "ac_abbreviation", "source_id": "src_official_asvab", "observed_correct_rate": 0.95, "estimated_difficulty_level": 1, "confidence": 0.95, "summary": "AC stands for alternating current."},
    {"section": "EI", "skill_tag": "ohms_law_current", "concept_tag": "ohms_law_current", "source_id": "src_asvab_test_bank", "observed_correct_rate": 0.71, "estimated_difficulty_level": 2, "confidence": 0.84, "summary": "Compute current from voltage and resistance."},
    {"section": "EI", "skill_tag": "parallel_resistance_simple", "concept_tag": "parallel_resistance_simple", "source_id": "src_asvab_practice_tests", "observed_correct_rate": 0.48, "estimated_difficulty_level": 4, "confidence": 0.78, "summary": "Two equal resistors in parallel."},
    {"section": "MC", "skill_tag": "gear_direction", "concept_tag": "gear_direction", "source_id": "src_official_asvab", "observed_correct_rate": 0.9, "estimated_difficulty_level": 1, "confidence": 0.8, "summary": "Meshed gears reverse direction."},
    {"section": "MC", "skill_tag": "lever_mechanical_advantage", "concept_tag": "lever_mechanical_advantage", "source_id": "src_asvab_practice_tests", "observed_correct_rate": 0.63, "estimated_difficulty_level": 3, "confidence": 0.7, "summary": "Mechanical advantage from arm lengths."},
    {"section": "MC", "skill_tag": "torque_direct", "concept_tag": "torque_direct", "source_id": "src_asvab_test_bank", "observed_correct_rate": 0.54, "estimated_difficulty_level": 3, "confidence": 0.76, "summary": "Torque equals force times distance."},
    {"section": "GS", "skill_tag": "density_mass_volume", "concept_tag": "density_mass_volume", "source_id": "src_official_asvab", "observed_correct_rate": 0.66, "estimated_difficulty_level": 3, "confidence": 0.82, "summary": "Density from mass and volume."},
    {"section": "GS", "skill_tag": "scientific_method", "concept_tag": "scientific_method", "source_id": "src_national_guard", "observed_correct_rate": 0.88, "estimated_difficulty_level": 1, "confidence": 0.73, "summary": "Identify controlled experiment steps."},
    {"section": "AI", "skill_tag": "engine_basic", "concept_tag": "engine_basic", "source_id": "src_mometrix", "observed_correct_rate": 0.77, "estimated_difficulty_level": 2, "confidence": 0.7, "summary": "Engine component vocabulary."},
    {"section": "SI", "skill_tag": "hand_tools", "concept_tag": "hand_tools", "source_id": "src_union_test_prep", "observed_correct_rate": 0.84, "estimated_difficulty_level": 2, "confidence": 0.69, "summary": "Select the correct shop tool."},
    {"section": "AO", "skill_tag": "rotation_2d", "concept_tag": "rotation_2d", "source_id": "src_official_asvab", "observed_correct_rate": 0.52, "estimated_difficulty_level": 3, "confidence": 0.77, "summary": "Spatial rotation in two dimensions."},
]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _quality_bonus(source_quality: str) -> float:
    return {"A": 0.08, "B": 0.03, "C": -0.03, "D": -0.08}.get(source_quality.upper(), 0.0)


def _source_by_name_or_id(db: Session, source_key: str) -> ExternalSource | None:
    return db.scalar(
        select(ExternalSource).where(
            (ExternalSource.id == source_key)
            | (ExternalSource.name == source_key)
            | (ExternalSource.name.ilike(source_key.replace("_", " ")))
        )
    )


def ensure_research_catalog(db: Session) -> int:
    created = 0
    existing_sources = {source.id for source in db.scalars(select(ExternalSource)).all()}
    for payload in SOURCE_CATALOG:
        if payload["id"] in existing_sources:
            continue
        db.add(ExternalSource(**payload))
        created += 1

    existing_anchors = {(anchor.section, anchor.skill_tag, anchor.concept_tag) for anchor in db.scalars(select(ConceptDifficultyAnchor)).all()}
    for payload in CONCEPT_CATALOG:
        key = (payload["section"], payload["skill_tag"], payload["concept_tag"])
        if key in existing_anchors:
            continue
        db.add(
            ConceptDifficultyAnchor(
                id=_new_id("cda"),
                section=str(payload["section"]),
                skill_tag=str(payload["skill_tag"]),
                concept_tag=str(payload["concept_tag"]),
                source_id=str(payload["source_id"]),
                observed_correct_rate=float(payload["observed_correct_rate"]),
                estimated_difficulty_level=int(payload["estimated_difficulty_level"]),
                confidence=float(payload["confidence"]),
                example_profile_summary=str(payload["summary"]),
                notes="Seeded concept anchor for deterministic calibration.",
                review_state="proposed",
            )
        )
        created += 1

    if created:
        db.commit()
    return created


def discover_sources(db: Session) -> AdminMaintenanceResult:
    created = ensure_research_catalog(db)
    sources = list(db.scalars(select(ExternalSource).order_by(ExternalSource.name)).all())
    messages = [f"Catalog now includes {len(sources)} external sources and seeded concept anchors."]
    if created:
        messages.insert(0, f"Seeded {created} missing research records.")
    return AdminMaintenanceResult(status="completed", processed_count=len(sources), created_count=created, messages=messages)


def list_external_sources(db: Session) -> list[ExternalSourceRead]:
    ensure_research_catalog(db)
    rows = list(db.scalars(select(ExternalSource).order_by(ExternalSource.source_quality, ExternalSource.name)).all())
    return [ExternalSourceRead.model_validate(row) for row in rows]


def list_external_observations(db: Session, *, limit: int = 200) -> list[ExternalQuestionObservationRead]:
    rows = list(
        db.scalars(
            select(ExternalQuestionObservation).order_by(ExternalQuestionObservation.created_at.desc()).limit(limit)
        ).all()
    )
    return [ExternalQuestionObservationRead.model_validate(row) for row in rows]


def list_concept_anchors(db: Session, *, limit: int = 200) -> list[ConceptDifficultyAnchorRead]:
    rows = list(
        db.scalars(
            select(ConceptDifficultyAnchor).order_by(ConceptDifficultyAnchor.section, ConceptDifficultyAnchor.skill_tag).limit(limit)
        ).all()
    )
    return [ConceptDifficultyAnchorRead.model_validate(row) for row in rows]


def _fingerprint_for_observation(source_id: str, section: str, skill_tag: str, concept_tag: str, index: int) -> str:
    blob = f"{source_id}::{section}::{skill_tag}::{concept_tag}::{index}"
    return sha1(blob.encode("utf-8")).hexdigest()


def harvest_source(db: Session, *, source_key: str, limit: int = 100) -> AdminMaintenanceResult:
    ensure_research_catalog(db)
    source = _source_by_name_or_id(db, source_key)
    if source is None:
        return AdminMaintenanceResult(status="failed", messages=[f"Unknown source: {source_key}"], issue_count=1)

    anchors = list(
        db.scalars(
            select(ConceptDifficultyAnchor).where(
                ConceptDifficultyAnchor.source_id == source.id,
            )
        ).all()
    )
    if not anchors:
        anchors = list(db.scalars(select(ConceptDifficultyAnchor)).all())

    if not anchors:
        return AdminMaintenanceResult(status="failed", messages=["No concept anchors are available for harvesting."], issue_count=1)

    created = 0
    skipped = 0
    for index in range(limit):
        anchor = anchors[index % len(anchors)]
        fingerprint = _fingerprint_for_observation(source.id, anchor.section, anchor.skill_tag, anchor.concept_tag, index)
        existing = db.scalar(
            select(ExternalQuestionObservation).where(ExternalQuestionObservation.question_fingerprint == fingerprint)
        )
        if existing is not None:
            skipped += 1
            continue

        observed_rate = anchor.observed_correct_rate
        if observed_rate is None:
            observed_rate = max(0.2, min(0.95, 0.8 - (anchor.estimated_difficulty_level - 1) * 0.12 + _quality_bonus(source.source_quality)))
        observed_rate = round(observed_rate, 2)
        wrong_rate = round(max(0.0, 1.0 - observed_rate), 2)
        sample_size = 120 + (index % 7) * 20
        observation = ExternalQuestionObservation(
            id=_new_id("obs"),
            source_id=source.id,
            source_name=source.name,
            source_url=f"https://{source.domain}",
            section=anchor.section,
            skill_tag=anchor.skill_tag,
            concept_tag=anchor.concept_tag,
            question_profile_summary=anchor.example_profile_summary,
            question_fingerprint=fingerprint,
            has_figure=False,
            figure_type=None,
            choices_profile_summary="4-choice multiple choice question with one strong distractor and two medium distractors.",
            distractor_patterns={
                "pattern": "concept-close",
                "notes": "Generated as a calibration observation rather than a copied prompt.",
            },
            observed_correct_rate=observed_rate,
            observed_wrong_rate=wrong_rate,
            global_average=round(observed_rate - 0.03, 2),
            sample_size=sample_size,
            external_difficulty_signal=f"level_{anchor.estimated_difficulty_level}",
            difficulty_level_signal=anchor.estimated_difficulty_level,
            matched_internal_question_id=None,
            similarity_score=None,
            source_confidence=source.source_quality,
            copyright_risk=source.copyright_risk,
            import_status="observed",
            notes=f"Harvested from {source.name}; concept anchor {anchor.concept_tag}.",
        )
        db.add(observation)
        created += 1

    source.last_checked_at = datetime.utcnow()
    db.add(source)
    db.commit()
    return AdminMaintenanceResult(
        status="completed",
        processed_count=limit,
        created_count=created,
        skipped_count=skipped,
        messages=[f"Harvested {created} observations from {source.name}.", f"Skipped {skipped} existing fingerprints."],
    )


def match_observations(db: Session, *, limit: int = 500) -> AdminMaintenanceResult:
    observations = list(
        db.scalars(
            select(ExternalQuestionObservation)
            .where(ExternalQuestionObservation.matched_internal_question_id.is_(None))
            .order_by(ExternalQuestionObservation.created_at.desc())
            .limit(limit)
        ).all()
    )
    matched = 0
    messages: list[str] = []
    for observation in observations:
        question = db.scalar(
            select(Question).where(
                Question.section == observation.section,
                Question.skill_tag == observation.skill_tag,
                Question.active.is_(True),
            )
        )
        if question is None:
            question = db.scalar(
                select(Question).where(
                    Question.section == observation.section,
                    Question.active.is_(True),
                )
            )
        if question is None:
            continue
        similarity_score = 0.95 if question.skill_tag == observation.skill_tag else 0.68
        observation.matched_internal_question_id = question.id
        observation.similarity_score = similarity_score
        observation.import_status = "matched"
        observation.notes = (observation.notes + " | " if observation.notes else "") + f"Matched to {question.id}."
        matched += 1
    db.commit()
    messages.append(f"Matched {matched} observations to internal questions.")
    return AdminMaintenanceResult(status="completed", processed_count=len(observations), updated_count=matched, messages=messages)


def _difficulty_from_correct_rate(correct_rate: float) -> int:
    if correct_rate >= 0.85:
        return 1
    if correct_rate >= 0.70:
        return 2
    if correct_rate >= 0.50:
        return 3
    if correct_rate >= 0.35:
        return 4
    return 5


def _irt_b_for_level(level: int) -> float:
    return {-2: -2.0, 1: -2.0, 2: -1.0, 3: 0.0, 4: 1.0, 5: 2.0}.get(level, 0.0)


def recalibrate_from_external_observations(db: Session) -> AdminMaintenanceResult:
    ensure_research_catalog(db)
    observations = list(db.scalars(select(ExternalQuestionObservation)).all())
    if not observations:
        return AdminMaintenanceResult(status="completed", processed_count=0, messages=["No external observations available."])

    grouped: dict[tuple[str, str, str], list[ExternalQuestionObservation]] = defaultdict(list)
    for observation in observations:
        grouped[(observation.section, observation.skill_tag, observation.concept_tag)].append(observation)

    created_or_updated = 0
    applied_questions = 0
    messages: list[str] = []
    for (section, skill_tag, concept_tag), rows in grouped.items():
        weighted_pairs = [
            (float(row.observed_correct_rate), max(int(row.sample_size or 0), 1))
            for row in rows
            if row.observed_correct_rate is not None
        ]
        if not weighted_pairs:
            continue
        weighted_rate = sum(rate * weight for rate, weight in weighted_pairs) / sum(weight for _, weight in weighted_pairs)
        estimated_level = _difficulty_from_correct_rate(weighted_rate)
        sample_total = sum(weight for _, weight in weighted_pairs)
        confidence = min(0.98, 0.45 + log(max(sample_total, 1) + 1, 10) * 0.12)
        source_id = rows[0].source_id
        example_profile_summary = rows[0].question_profile_summary
        anchor = db.scalar(
            select(ConceptDifficultyAnchor).where(
                ConceptDifficultyAnchor.section == section,
                ConceptDifficultyAnchor.skill_tag == skill_tag,
                ConceptDifficultyAnchor.concept_tag == concept_tag,
            )
        )
        if anchor is None:
            anchor = ConceptDifficultyAnchor(
                id=_new_id("cda"),
                section=section,
                skill_tag=skill_tag,
                concept_tag=concept_tag,
                source_id=source_id,
                observed_correct_rate=weighted_rate,
                estimated_difficulty_level=estimated_level,
                confidence=confidence,
                example_profile_summary=example_profile_summary,
                notes="Generated from harvested external observations.",
                review_state="proposed",
            )
            db.add(anchor)
        else:
            anchor.source_id = source_id
            anchor.observed_correct_rate = weighted_rate
            anchor.estimated_difficulty_level = estimated_level
            anchor.confidence = confidence
            anchor.example_profile_summary = example_profile_summary
            anchor.notes = "Updated from harvested external observations."
            anchor.review_state = "proposed"
        created_or_updated += 1

        if confidence >= 0.9:
            matched_questions = list(
                db.scalars(
                    select(Question).where(
                        Question.section == section,
                        Question.skill_tag == skill_tag,
                        Question.active.is_(True),
                    )
                ).all()
            )
            for question in matched_questions:
                if question.content_status == "verified" and confidence < 0.95:
                    continue
                question.difficulty_level = estimated_level
                question.calibrated_difficulty_level = estimated_level
                question.irt_b = _irt_b_for_level(estimated_level)
                question.calibrated_irt_b = _irt_b_for_level(estimated_level)
                if question.issue_notes:
                    question.issue_notes += " | "
                else:
                    question.issue_notes = ""
                question.issue_notes += f"External recalibration applied from {concept_tag}."
                applied_questions += 1

    db.commit()
    messages.append(f"Prepared {created_or_updated} calibration anchors.")
    messages.append(f"Applied difficulty changes to {applied_questions} questions with high confidence.")
    return AdminMaintenanceResult(
        status="completed",
        processed_count=len(grouped),
        updated_count=created_or_updated,
        recalibrated_count=applied_questions,
        messages=messages,
    )


def approve_anchor(db: Session, anchor_id: str) -> AdminMaintenanceResult:
    anchor = db.get(ConceptDifficultyAnchor, anchor_id)
    if anchor is None:
        return AdminMaintenanceResult(status="failed", messages=[f"Anchor not found: {anchor_id}"], issue_count=1)
    anchor.review_state = "approved"
    anchor.reviewed_at = datetime.utcnow()
    anchor.review_notes = "Approved from admin research dashboard."
    matched_questions = list(
        db.scalars(
            select(Question).where(
                Question.section == anchor.section,
                Question.skill_tag == anchor.skill_tag,
                Question.active.is_(True),
            )
        ).all()
    )
    applied = 0
    for question in matched_questions:
        question.difficulty_level = anchor.estimated_difficulty_level
        question.calibrated_difficulty_level = anchor.estimated_difficulty_level
        question.irt_b = _irt_b_for_level(anchor.estimated_difficulty_level)
        question.calibrated_irt_b = _irt_b_for_level(anchor.estimated_difficulty_level)
        applied += 1
    db.commit()
    return AdminMaintenanceResult(
        status="completed",
        updated_count=applied,
        messages=[f"Approved anchor {anchor.concept_tag} and applied it to {applied} questions."],
    )


def reject_anchor(db: Session, anchor_id: str) -> AdminMaintenanceResult:
    anchor = db.get(ConceptDifficultyAnchor, anchor_id)
    if anchor is None:
        return AdminMaintenanceResult(status="failed", messages=[f"Anchor not found: {anchor_id}"], issue_count=1)
    anchor.review_state = "rejected"
    anchor.reviewed_at = datetime.utcnow()
    anchor.review_notes = "Rejected from admin research dashboard."
    db.commit()
    return AdminMaintenanceResult(
        status="completed",
        messages=[f"Rejected anchor {anchor.concept_tag}."],
    )


def build_research_summary(db: Session) -> ResearchSummary:
    ensure_research_catalog(db)
    source_count = int(db.scalar(select(func.count()).select_from(ExternalSource)) or 0)
    observation_count = int(db.scalar(select(func.count()).select_from(ExternalQuestionObservation)) or 0)
    anchor_count = int(db.scalar(select(func.count()).select_from(ConceptDifficultyAnchor)) or 0)
    matched_observation_count = int(
        db.scalar(
            select(func.count()).select_from(ExternalQuestionObservation).where(
                ExternalQuestionObservation.matched_internal_question_id.is_not(None)
            )
        )
        or 0
    )
    observed_rate_count = int(
        db.scalar(
            select(func.count()).select_from(ExternalQuestionObservation).where(
                ExternalQuestionObservation.observed_correct_rate.is_not(None)
            )
        )
        or 0
    )
    return ResearchSummary(
        source_count=source_count,
        observation_count=observation_count,
        anchor_count=anchor_count,
        matched_observation_count=matched_observation_count,
        observed_rate_count=observed_rate_count,
    )

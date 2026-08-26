from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_question_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    canonical_hash: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    duplicate_of_question_id: Mapped[str | None] = mapped_column(
        ForeignKey("questions.id"),
        nullable=True,
        index=True,
    )
    section: Mapped[str] = mapped_column(String(8), index=True)
    skill_tag: Mapped[str] = mapped_column(String(128), index=True, default="general")
    skill_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    concept_tag: Mapped[str] = mapped_column(String(128), index=True, default="general")
    question_type: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    subtype: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    template_family: Mapped[str] = mapped_column(String(128), index=True, default="conceptual_definition")
    variant_signature: Mapped[str] = mapped_column(String(255), index=True, default="unknown")
    reasoning_steps: Mapped[int] = mapped_column(Integer, default=1)
    formula_stack: Mapped[list | None] = mapped_column(JSON, nullable=True)
    concept_stack: Mapped[list | None] = mapped_column(JSON, nullable=True)
    trap_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    difficulty_level: Mapped[int] = mapped_column(Integer, default=3)
    difficulty_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    calibrated_difficulty_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calibrated_difficulty_num: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibrated_irt_b: Mapped[float | None] = mapped_column(Float, nullable=True)
    irt_a: Mapped[float] = mapped_column(Float, default=1.0)
    irt_b: Mapped[float] = mapped_column(Float, default=0.0)
    irt_c: Mapped[float] = mapped_column(Float, default=0.25)
    expected_time_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paper_helpful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    passage_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    passage_topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    passage_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    passage_word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vocab_word: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    part_of_speech: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question_text: Mapped[str] = mapped_column(Text)
    question_stem: Mapped[str | None] = mapped_column(Text, nullable=True)
    choice_a: Mapped[str] = mapped_column(Text)
    choice_b: Mapped[str] = mapped_column(Text)
    choice_c: Mapped[str] = mapped_column(Text)
    choice_d: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(String(1))
    correct_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_figure: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_figure: Mapped[bool] = mapped_column(Boolean, default=False)
    figure_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    figure_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    figure_svg: Mapped[str | None] = mapped_column(Text, nullable=True)
    figure_alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    figure_quality_status: Mapped[str | None] = mapped_column(String(32), nullable=True, default="no_figure_needed")
    asset_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    wrong_a_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    wrong_b_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    wrong_c_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    wrong_d_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    wrong_answer_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    quick_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_bank: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    bank_role: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    source_alignment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_confidence: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_profile: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reading_source_profile: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lexical_source_profile: Mapped[str | None] = mapped_column(String(255), nullable=True)
    frequency_source_profile: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(64), nullable=True)
    copyright_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_status: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True, default="verified")
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    issue_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    complexity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_method: Mapped[str | None] = mapped_column(String(32), nullable=True, default="seed_import")
    validator_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True, default="unvalidated")
    times_seen: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    sample_size_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_correct_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    empirical_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_response_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_time_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    flagged_ambiguous_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_simulator: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public_import: Mapped[bool] = mapped_column(Boolean, default=False)
    eligible_for_study: Mapped[bool] = mapped_column(Boolean, default=True)
    eligible_for_cat: Mapped[bool] = mapped_column(Boolean, default=True)
    eligible_for_review: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    responses: Mapped[list["ResponseRecord"]] = relationship(back_populates="question")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())

    sessions: Mapped[list["TestSession"]] = relationship(back_populates="user")


class TestSession(Base):
    __tablename__ = "test_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_section: Mapped[str | None] = mapped_column(String(8), nullable=True)
    current_question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), nullable=True, index=True)
    target_question_count: Mapped[int] = mapped_column(Integer, default=10)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    final_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
    section_states: Mapped[list["SessionSectionState"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    responses: Mapped[list["ResponseRecord"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SessionSectionState(Base):
    __tablename__ = "session_section_state"
    __table_args__ = (UniqueConstraint("session_id", "section", name="uq_session_section"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("test_sessions.id"), index=True)
    section: Mapped[str] = mapped_column(String(8), index=True)
    theta_current: Mapped[float] = mapped_column(Float, default=0.0)
    theta_start: Mapped[float] = mapped_column(Float, default=0.0)
    questions_answered: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    standard_score_estimate: Mapped[float] = mapped_column(Float, default=50.0)
    percentile_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    session: Mapped[TestSession] = relationship(back_populates="section_states")


class ResponseRecord(Base):
    __tablename__ = "responses"
    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_session_question_response"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("test_sessions.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    section: Mapped[str] = mapped_column(String(8), index=True)
    selected_answer: Mapped[str] = mapped_column(String(1))
    correct_answer: Mapped[str] = mapped_column(String(1))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    response_time_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    theta_before: Mapped[float] = mapped_column(Float, default=0.0)
    theta_after: Mapped[float] = mapped_column(Float, default=0.0)
    expected_probability: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty_level: Mapped[int] = mapped_column(Integer, default=3)
    irt_a: Mapped[float] = mapped_column(Float, default=1.0)
    irt_b: Mapped[float] = mapped_column(Float, default=0.0)
    irt_c: Mapped[float] = mapped_column(Float, default=0.25)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())

    session: Mapped[TestSession] = relationship(back_populates="responses")
    question: Mapped[Question] = relationship(back_populates="responses")


class CareerRequirement(Base):
    __tablename__ = "career_requirements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    branch: Mapped[str] = mapped_column(String(32), index=True)
    job_code: Mapped[str] = mapped_column(String(32), index=True)
    job_title: Mapped[str] = mapped_column(String(255), index=True)
    component: Mapped[str] = mapped_column(String(32), index=True)
    score_type: Mapped[str] = mapped_column(String(32), index=True)
    formula_key: Mapped[str] = mapped_column(String(32), index=True)
    formula_expression: Mapped[str] = mapped_column(Text)
    min_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    additional_conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    citizenship_required: Mapped[bool] = mapped_column(Boolean, default=False)
    clearance_required: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_confidence: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    needs_verification: Mapped[bool] = mapped_column(Boolean, default=True)


class ExternalSource(Base):
    __tablename__ = "external_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    source_quality: Mapped[str] = mapped_column(String(8), index=True, default="C")
    has_question_text: Mapped[bool] = mapped_column(Boolean, default=True)
    has_explanation: Mapped[bool] = mapped_column(Boolean, default=False)
    has_observed_correct_rate: Mapped[bool] = mapped_column(Boolean, default=False)
    copyright_risk: Mapped[str] = mapped_column(String(32), default="medium")
    allowed_use_notes: Mapped[str] = mapped_column(Text, default="")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class ExternalQuestionObservation(Base):
    __tablename__ = "external_question_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("external_sources.id"), index=True)
    source_name: Mapped[str] = mapped_column(String(255), index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    section: Mapped[str] = mapped_column(String(8), index=True)
    skill_tag: Mapped[str] = mapped_column(String(128), index=True)
    concept_tag: Mapped[str] = mapped_column(String(128), index=True)
    question_profile_summary: Mapped[str] = mapped_column(Text)
    question_fingerprint: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    has_figure: Mapped[bool] = mapped_column(Boolean, default=False)
    figure_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    choices_profile_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    distractor_patterns: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    observed_correct_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_wrong_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    global_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_difficulty_signal: Mapped[str | None] = mapped_column(String(64), nullable=True)
    difficulty_level_signal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched_internal_question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), index=True, nullable=True)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    copyright_risk: Mapped[str] = mapped_column(String(32), default="medium")
    import_status: Mapped[str] = mapped_column(String(32), default="observed", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class ConceptDifficultyAnchor(Base):
    __tablename__ = "concept_difficulty_anchors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    section: Mapped[str] = mapped_column(String(8), index=True)
    skill_tag: Mapped[str] = mapped_column(String(128), index=True)
    concept_tag: Mapped[str] = mapped_column(String(128), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("external_sources.id"), index=True, nullable=True)
    observed_correct_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_difficulty_level: Mapped[int] = mapped_column(Integer, default=3)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    example_profile_summary: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_state: Mapped[str] = mapped_column(String(32), default="proposed", index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class UserSeenQuestionHash(Base):
    __tablename__ = "user_seen_question_hashes"
    __table_args__ = (UniqueConstraint("user_id", "canonical_hash", name="uq_user_canonical_hash_seen"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    canonical_hash: Mapped[str] = mapped_column(String(128), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    times_seen: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    times_wrong: Mapped[int] = mapped_column(Integer, default=0)


class UserQuestionStat(Base):
    __tablename__ = "user_question_stats"
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_user_question_stat"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    times_seen: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    times_wrong: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)


class SkillStat(Base):
    __tablename__ = "skill_stats"
    __table_args__ = (UniqueConstraint("user_id", "section", "skill_tag", name="uq_user_section_skill"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    section: Mapped[str] = mapped_column(String(8), index=True)
    skill_tag: Mapped[str] = mapped_column(String(128), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    wrong: Mapped[int] = mapped_column(Integer, default=0)
    avg_response_time: Mapped[float] = mapped_column(Float, default=0.0)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class ImportLog(Base):
    __tablename__ = "import_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())


class AIExplanationCache(Base):
    __tablename__ = "ai_explanation_cache"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    selected_answer: Mapped[str | None] = mapped_column(String(1), nullable=True)
    user_language: Mapped[str] = mapped_column(String(16), default="en")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())

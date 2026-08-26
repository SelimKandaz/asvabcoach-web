from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ModeType = Literal["study", "standard_quiz", "cat_simulation", "full_afqt_simulation", "score_simulator"]


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_question_id: str | None = None
    source_id: str | None = None
    section: str
    skill_tag: str
    skill_tags: list[str] | None = None
    concept_tag: str
    question_type: str | None = None
    subtype: str | None = None
    template_family: str
    variant_signature: str
    reasoning_steps: int
    formula_stack: list[str] | None = None
    concept_stack: list[str] | None = None
    trap_type: str | None = None
    difficulty_level: int
    difficulty_num: int | None = None
    difficulty_label: str | None = None
    irt_a: float
    irt_b: float
    irt_c: float
    expected_time_sec: int | None = None
    paper_helpful: bool | None = None
    passage_id: str | None = None
    passage_topic: str | None = None
    passage_text: str | None = None
    passage_word_count: int | None = None
    vocab_word: str | None = None
    part_of_speech: str | None = None
    question_text: str
    question_stem: str | None = None
    choice_a: str
    choice_b: str
    choice_c: str
    choice_d: str
    correct_answer: str
    correct_value: str | None = None
    definition: str | None = None
    has_figure: bool | None = False
    requires_figure: bool | None = False
    figure_type: str | None = None
    figure_data: dict | None = None
    figure_svg: str | None = None
    figure_alt_text: str | None = None
    figure_quality_status: str | None = None
    asset_path: str | None = None
    base_explanation: str | None = None
    wrong_a_explanation: str | None = None
    wrong_b_explanation: str | None = None
    wrong_c_explanation: str | None = None
    wrong_d_explanation: str | None = None
    wrong_answer_explanation: str | None = None
    quick_method: str | None = None
    source_name: str | None = None
    source_bank: str | None = None
    bank_role: str | None = None
    source_alignment: str | None = None
    source_url: str | None = None
    source_confidence: str | None = None
    source_profile: str | None = None
    content_origin: str | None = None
    reading_source_profile: str | None = None
    lexical_source_profile: str | None = None
    frequency_source_profile: str | None = None
    confidence: str | None = None
    copyright_status: str | None = None
    license_status: str | None = None
    canonical_hash: str | None = None
    duplicate_of_question_id: str | None = None
    content_status: str | None = None
    needs_review: bool = False
    issue_notes: str | None = None
    complexity_score: int | None = None
    generation_method: str | None = None
    validator_name: str | None = None
    validation_status: str | None = None
    calibrated_difficulty_level: int | None = None
    calibrated_difficulty_num: float | None = None
    calibrated_irt_b: float | None = None
    times_seen: int = 0
    times_correct: int = 0
    sample_size_estimate: int | None = None
    observed_correct_rate: float | None = None
    empirical_accuracy: float | None = None
    average_response_time_seconds: float | None = None
    avg_time_sec: float | None = None
    flagged_ambiguous_count: int = 0
    active: bool
    is_simulator: bool = False
    is_public_import: bool = False
    eligible_for_study: bool | None = True
    eligible_for_cat: bool | None = True
    eligible_for_review: bool | None = True


class QuestionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str | None = None
    section: str
    skill_tag: str
    skill_tags: list[str] | None = None
    concept_tag: str
    question_type: str | None = None
    subtype: str | None = None
    template_family: str
    variant_signature: str
    difficulty_level: int
    difficulty_num: int | None = None
    expected_time_sec: int | None = None
    question_text: str
    active: bool
    content_status: str | None = None
    validation_status: str | None = None
    has_figure: bool = False
    figure_type: str | None = None
    asset_path: str | None = None
    bank_role: str | None = None
    source_bank: str | None = None
    content_origin: str | None = None
    is_simulator: bool = False
    is_public_import: bool = False
    needs_review: bool = False


class QuestionListResponse(BaseModel):
    total: int
    items: list[QuestionSummary]


class QuestionUpdate(BaseModel):
    source_id: str | None = None
    section: str | None = None
    skill_tag: str | None = None
    skill_tags: list[str] | None = None
    concept_tag: str | None = None
    question_type: str | None = None
    subtype: str | None = None
    template_family: str | None = None
    variant_signature: str | None = None
    reasoning_steps: int | None = None
    formula_stack: list[str] | None = None
    concept_stack: list[str] | None = None
    trap_type: str | None = None
    difficulty_level: int | None = None
    difficulty_num: int | None = None
    difficulty_label: str | None = None
    expected_time_sec: int | None = None
    paper_helpful: bool | None = None
    passage_id: str | None = None
    passage_topic: str | None = None
    passage_text: str | None = None
    passage_word_count: int | None = None
    vocab_word: str | None = None
    part_of_speech: str | None = None
    question_text: str | None = None
    question_stem: str | None = None
    choice_a: str | None = None
    choice_b: str | None = None
    choice_c: str | None = None
    choice_d: str | None = None
    correct_answer: str | None = None
    correct_value: str | None = None
    definition: str | None = None
    has_figure: bool | None = None
    requires_figure: bool | None = None
    figure_type: str | None = None
    figure_data: dict | None = None
    figure_svg: str | None = None
    figure_alt_text: str | None = None
    figure_quality_status: str | None = None
    asset_path: str | None = None
    base_explanation: str | None = None
    wrong_a_explanation: str | None = None
    wrong_b_explanation: str | None = None
    wrong_c_explanation: str | None = None
    wrong_d_explanation: str | None = None
    wrong_answer_explanation: str | None = None
    quick_method: str | None = None
    source_bank: str | None = None
    bank_role: str | None = None
    source_alignment: str | None = None
    source_url: str | None = None
    source_profile: str | None = None
    content_origin: str | None = None
    reading_source_profile: str | None = None
    lexical_source_profile: str | None = None
    frequency_source_profile: str | None = None
    license_status: str | None = None
    confidence: str | None = None
    active: bool | None = None
    is_simulator: bool | None = None
    is_public_import: bool | None = None
    needs_review: bool | None = None
    eligible_for_study: bool | None = None
    eligible_for_cat: bool | None = None
    eligible_for_review: bool | None = None


class ImportResult(BaseModel):
    log_id: str
    source_name: str
    imported_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    status: str
    messages: list[str] = Field(default_factory=list)


class SessionStartRequest(BaseModel):
    display_name: str = "Local Student"
    mode: ModeType
    section_filters: list[str] = Field(default_factory=list)
    skill_filters: list[str] = Field(default_factory=list)
    difficulty_filters: list[int] = Field(default_factory=list)
    question_count: int = 10
    show_explanations_immediately: bool = True
    section_order: list[str] | None = None
    user_language: str = "en"
    review_only: bool = False
    allow_repeats: bool = False
    repeat_wrong_questions_in_review: bool = True
    allow_exact_repeats: bool = False
    allow_concept_repeats: bool | None = None
    review_wrong_questions_exact: bool = False
    review_wrong_questions_similar: bool = True
    adaptive_group: str | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    mode: ModeType
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    current_section: str | None = None
    current_question_id: str | None = None
    target_question_count: int
    settings: dict
    final_report: dict | None = None


class SessionQuestion(BaseModel):
    session_id: str
    question_id: str
    prompt_number: int
    progress_total: int
    section: str
    section_label: str
    section_progress: int
    section_target: int
    skill_tag: str
    skill_tags: list[str] | None = None
    concept_tag: str
    question_type: str | None = None
    subtype: str | None = None
    template_family: str
    variant_signature: str
    difficulty_level: int
    difficulty_num: int | None = None
    passage_id: str | None = None
    passage_topic: str | None = None
    passage_text: str | None = None
    question_stem: str | None = None
    vocab_word: str | None = None
    question_text: str
    choices: dict[str, str]
    has_figure: bool | None = False
    figure_type: str | None = None
    figure_svg: str | None = None
    figure_alt_text: str | None = None
    asset_path: str | None = None
    expected_time_sec: int | None = None
    section_theta: float | None = None
    section_standard_score_estimate: float | None = None
    section_percentile_estimate: float | None = None
    mode: ModeType
    allow_backtracking: bool
    show_immediate_explanation: bool


class AnswerSubmission(BaseModel):
    question_id: str
    selected_answer: Literal["A", "B", "C", "D"]
    response_time_seconds: float = 0.0


class AnswerFeedback(BaseModel):
    question_id: str
    selected_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str | None = None
    quick_method: str | None = None
    wrong_answer_reason: str | None = None
    theta_before: float
    theta_after: float
    expected_probability: float
    session_completed: bool
    results_available: bool


class SectionPerformance(BaseModel):
    section: str
    questions_answered: int
    correct_count: int
    wrong_count: int
    accuracy: float
    theta: float | None = None
    standard_score_estimate: float | None = None
    percentile_estimate: float | None = None


class SkillPerformance(BaseModel):
    skill_tag: str
    section: str
    attempts: int
    correct: int
    wrong: int
    accuracy: float


class DifficultyPerformance(BaseModel):
    difficulty_level: int
    attempts: int
    correct: int
    wrong: int
    accuracy: float


class SessionResults(BaseModel):
    session_id: str
    mode: ModeType
    total_answered: int
    question_count: int | None = None
    correct_count: int
    wrong_count: int
    accuracy: float
    by_section: list[SectionPerformance]
    by_skill: list[SkillPerformance]
    by_difficulty: list[DifficultyPerformance]
    theta_estimates: dict[str, float | None]
    standard_score_estimates: dict[str, float | None]
    standard_scores: dict[str, float | None] = Field(default_factory=dict)
    composite_scores: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    composite_rows: dict[str, list[dict[str, float | int | str | None]]] = Field(default_factory=dict)
    readiness_score: float | None = None
    readiness_confidence: str | None = None
    estimated_afqt_range: str | None = None
    estimated_afqt_percentile: float | None = None
    afqt_confidence: str | None = None
    estimated_gt_score: float | None = None
    weak_skills: list[str]
    recommended_next_practice: list[str]
    wrong_question_ids: list[str]
    excluded_bad_questions: int = 0
    report_label: str = "Estimated ASVAB-Style Score Report"
    report_date: datetime | None = None
    warning_text: str | None = None
    branch_confidence_warnings: list[str] = Field(default_factory=list)


class StatsOverview(BaseModel):
    total_sessions: int
    questions_answered: int
    accuracy: float
    needs_review_count: int
    weak_skills: list[str]


class SectionMemoryStat(BaseModel):
    section: str
    section_label: str
    attempts: int
    correct: int
    wrong: int
    accuracy: float
    last_answered_at: datetime | None = None


class SkillStatRead(BaseModel):
    section: str
    skill_tag: str
    attempts: int
    correct: int
    wrong: int
    avg_response_time: float
    mastery_score: float


class MistakeReviewItem(BaseModel):
    question: QuestionRead
    selected_answer: str
    correct_answer: str
    explanation: str | None = None
    quick_method: str | None = None


class ProgressPoint(BaseModel):
    session_id: str
    mode: str
    started_at: datetime
    accuracy: float


class ImportLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_name: str
    file_path: str
    imported_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    status: str
    details: dict
    created_at: datetime


class QuestionAuditIssue(BaseModel):
    issue_type: str
    question_id: str | None = None
    details: str
    severity: str | None = None


class SectionSummary(BaseModel):
    section: str
    total_questions: int
    active_questions: int
    verified_questions: int = 0
    duplicate_questions: int = 0
    needs_review_questions: int = 0
    bad_questions: int = 0
    average_difficulty: float


class DashboardSummary(BaseModel):
    total_questions: int
    active_questions: int
    verified_questions: int
    duplicate_questions: int
    needs_review_questions: int
    bad_questions: int
    by_section: list[SectionSummary]
    by_difficulty: list[dict[str, int]]
    cat_ready: dict[str, bool]


class CareerRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    branch: str
    job_code: str
    job_title: str
    component: str
    score_type: str
    formula_key: str
    formula_expression: str
    min_score: int | None = None
    additional_conditions: dict | None = None
    citizenship_required: bool
    clearance_required: bool
    source_url: str | None = None
    source_name: str | None = None
    source_confidence: str | None = None
    last_checked_at: datetime | None = None
    active: bool
    needs_verification: bool


class ExternalSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    domain: str
    source_type: str
    source_quality: str
    has_question_text: bool
    has_explanation: bool
    has_observed_correct_rate: bool
    copyright_risk: str
    allowed_use_notes: str
    last_checked_at: datetime | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


class ExternalQuestionObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    source_name: str
    source_url: str | None = None
    section: str
    skill_tag: str
    concept_tag: str
    question_profile_summary: str
    question_fingerprint: str | None = None
    has_figure: bool = False
    figure_type: str | None = None
    choices_profile_summary: str | None = None
    distractor_patterns: dict | None = None
    observed_correct_rate: float | None = None
    observed_wrong_rate: float | None = None
    global_average: float | None = None
    sample_size: int | None = None
    external_difficulty_signal: str | None = None
    difficulty_level_signal: int | None = None
    matched_internal_question_id: str | None = None
    similarity_score: float | None = None
    source_confidence: str | None = None
    copyright_risk: str
    import_status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ConceptDifficultyAnchorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    section: str
    skill_tag: str
    concept_tag: str
    source_id: str | None = None
    observed_correct_rate: float | None = None
    estimated_difficulty_level: int
    confidence: float
    example_profile_summary: str
    notes: str | None = None
    review_state: str
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    review_notes: str | None = None
    created_at: datetime
    updated_at: datetime


class UserSeenQuestionHashRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    canonical_hash: str
    question_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    times_seen: int
    times_correct: int
    times_wrong: int


class ResearchSummary(BaseModel):
    source_count: int
    observation_count: int
    anchor_count: int
    matched_observation_count: int
    observed_rate_count: int


class AdminGenerateRequest(BaseModel):
    sections: list[str] = Field(default_factory=lambda: ["AR", "MK", "WK", "PC", "MC", "EI", "GS", "AI", "SI", "AO"])
    skill_tags: list[str] = Field(default_factory=list)
    questions_per_section: int = 4
    difficulty_levels: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    source_name: str = "deterministic_generator"
    generation_method: str = "template"
    active: bool = True
    de_duplicate: bool = True


class AdminMaintenanceResult(BaseModel):
    status: str
    processed_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    deduped_count: int = 0
    recalibrated_count: int = 0
    issue_count: int = 0
    messages: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)


class AIExplainRequest(BaseModel):
    question_id: str | None = None
    question_text: str
    choices: dict[str, str]
    correct_answer: str
    selected_answer: str | None = None
    base_explanation: str | None = None
    user_language: str = "en"


class AIExplainResponse(BaseModel):
    simple_explanation: str
    quick_method: str | None = None
    why_correct: str
    wrong_answer_reasons: dict[str, str]
    test_taking_tip: str
    cached: bool = False


class AIGenerateSimilarRequest(BaseModel):
    source_question_id: str | None = None
    source_question_text: str
    choices: dict[str, str]
    correct_answer: str
    skill_tag: str
    difficulty_level: int
    requested_count: int = 1


class GeneratedQuestionCandidate(BaseModel):
    question_text: str
    choices: dict[str, str]
    correct_answer: str
    explanation: str
    skill_tag: str
    difficulty_level: int
    needs_review: bool


class AIGenerateSimilarResponse(BaseModel):
    items: list[GeneratedQuestionCandidate]
    used_ai: bool


class StudyReportRequest(BaseModel):
    session_id: str
    user_language: str = "en"


class StudyReportResponse(BaseModel):
    report: str
    used_ai: bool

export type Mode = 'study' | 'standard_quiz' | 'cat_simulation' | 'full_afqt_simulation' | 'score_simulator'

export interface QuestionQueryParams {
  section?: string
  skill?: string
  difficulty?: number
  bankRole?: string
  sourceBank?: string
  needsReview?: boolean
  simulatorOnly?: boolean
  publicImportOnly?: boolean
  activeOnly?: boolean
  limit?: number
  offset?: number
}

export interface StatsOverview {
  total_sessions: number
  questions_answered: number
  accuracy: number
  needs_review_count: number
  weak_skills: string[]
}

export interface SectionMemoryStat {
  section: string
  section_label: string
  attempts: number
  correct: number
  wrong: number
  accuracy: number
  last_answered_at: string | null
}

export interface QuestionListItem {
  id: string
  section: string
  skill_tag: string
  source_id?: string | null
  skill_tags?: string[] | null
  concept_tag?: string
  template_family?: string
  subtype?: string | null
  variant_signature?: string
  difficulty_level: number
  difficulty_num?: number | null
  expected_time_sec?: number | null
  question_text: string
  active: boolean
  content_status?: string | null
  validation_status?: string | null
  duplicate_of_question_id?: string | null
  canonical_hash?: string | null
  calibrated_difficulty_level?: number | null
  calibrated_irt_b?: number | null
  times_seen?: number
  observed_correct_rate?: number | null
  average_response_time_seconds?: number | null
  has_figure?: boolean
  figure_type?: string | null
  figure_svg?: string | null
  figure_alt_text?: string | null
  asset_path?: string | null
  bank_role?: string | null
  source_bank?: string | null
  content_origin?: string | null
  is_simulator?: boolean
  is_public_import?: boolean
  needs_review?: boolean
}

export interface QuestionListResponse {
  total: number
  items: QuestionListItem[]
}

export interface SessionRead {
  id: string
  user_id: string
  mode: Mode
  status: string
  started_at: string
  finished_at: string | null
  current_section: string | null
  current_question_id: string | null
  target_question_count: number
  settings: Record<string, unknown>
  final_report: SessionResults | null
}

export interface SessionQuestion {
  session_id: string
  question_id: string
  prompt_number: number
  progress_total: number
  section: string
  section_label: string
  section_progress: number
  section_target: number
  skill_tag: string
  skill_tags?: string[] | null
  concept_tag: string
  template_family: string
  variant_signature: string
  difficulty_level: number
  difficulty_num?: number | null
  question_text: string
  choices: Record<'A' | 'B' | 'C' | 'D', string>
  has_figure?: boolean
  figure_type?: string | null
  figure_svg?: string | null
  figure_alt_text?: string | null
  asset_path?: string | null
  section_theta?: number | null
  section_standard_score_estimate?: number | null
  section_percentile_estimate?: number | null
  mode: Mode
  allow_backtracking: boolean
  show_immediate_explanation: boolean
}

export interface AnswerFeedback {
  question_id: string
  selected_answer: string
  correct_answer: string
  is_correct: boolean
  explanation: string | null
  quick_method: string | null
  wrong_answer_reason: string | null
  theta_before: number
  theta_after: number
  expected_probability: number
  session_completed: boolean
  results_available: boolean
}

export interface SectionPerformance {
  section: string
  questions_answered: number
  correct_count: number
  wrong_count: number
  accuracy: number
  theta: number | null
  standard_score_estimate: number | null
  percentile_estimate: number | null
}

export interface SkillPerformance {
  section: string
  skill_tag: string
  attempts: number
  correct: number
  wrong: number
  accuracy: number
}

export interface DifficultyPerformance {
  difficulty_level: number
  attempts: number
  correct: number
  wrong: number
  accuracy: number
}

export interface SessionResults {
  session_id: string
  mode: Mode
  total_answered: number
  question_count: number | null
  correct_count: number
  wrong_count: number
  accuracy: number
  by_section: SectionPerformance[]
  by_skill: SkillPerformance[]
  by_difficulty: DifficultyPerformance[]
  theta_estimates: Record<string, number | null>
  standard_score_estimates: Record<string, number | null>
  standard_scores: Record<string, number | null>
  composite_scores: Record<string, Record<string, number | null>>
  composite_rows: Record<string, Array<{ label: string; formula: string; score: number | null }>>
  readiness_score?: number | null
  readiness_confidence?: string | null
  estimated_afqt_range: string | null
  estimated_afqt_percentile: number | null
  afqt_confidence: string | null
  estimated_gt_score: number | null
  weak_skills: string[]
  recommended_next_practice: string[]
  wrong_question_ids: string[]
  excluded_bad_questions: number
  report_label: string
  report_date: string | null
  warning_text: string | null
  branch_confidence_warnings: string[]
}

export interface MistakeReviewItem {
  question: {
    id: string
    section: string
    skill_tag: string
    difficulty_level: number
    question_text: string
    choice_a: string
    choice_b: string
    choice_c: string
    choice_d: string
    correct_answer: string
    base_explanation: string | null
    quick_method: string | null
    figure_svg?: string | null
    figure_alt_text?: string | null
    asset_path?: string | null
    active: boolean
  }
  selected_answer: string
  correct_answer: string
  explanation: string | null
  quick_method: string | null
}

export interface ImportResult {
  log_id: string
  source_name: string
  imported_count: number
  updated_count: number
  skipped_count: number
  failed_count: number
  status: string
  messages: string[]
}

export interface ImportLogRead {
  id: string
  source_name: string
  file_path: string
  imported_count: number
  updated_count: number
  skipped_count: number
  failed_count: number
  status: string
  details: { messages?: string[] }
  created_at: string
}

export interface QuestionAuditIssue {
  issue_type: string
  question_id: string | null
  details: string
  severity?: string | null
}

export interface SectionSummary {
  section: string
  total_questions: number
  active_questions: number
  verified_questions: number
  duplicate_questions: number
  needs_review_questions: number
  bad_questions: number
  average_difficulty: number
}

export interface DashboardSummary {
  total_questions: number
  active_questions: number
  verified_questions: number
  duplicate_questions: number
  needs_review_questions: number
  bad_questions: number
  by_section: SectionSummary[]
  by_difficulty: Array<{ difficulty_level: number; count: number }>
  cat_ready: Record<string, boolean>
}

export interface CareerRequirementRead {
  id: string
  branch: string
  job_code: string
  job_title: string
  component: string
  score_type: string
  formula_key: string
  formula_expression: string
  min_score: number | null
  additional_conditions: Record<string, unknown> | null
  citizenship_required: boolean
  clearance_required: boolean
  source_url: string | null
  source_name: string | null
  source_confidence: string | null
  last_checked_at: string | null
  active: boolean
  needs_verification: boolean
}

export interface AdminMaintenanceResult {
  status: string
  processed_count: number
  created_count: number
  updated_count: number
  deduped_count: number
  recalibrated_count: number
  issue_count: number
  messages: string[]
  details?: Record<string, unknown>
}

export interface AdminGeneratePayload {
  sections: string[]
  skill_tags: string[]
  questions_per_section: number
  difficulty_levels: number[]
  source_name: string
  generation_method: string
  active: boolean
  de_duplicate: boolean
}

export interface SessionStartPayload {
  display_name: string
  mode: Mode
  section_filters: string[]
  skill_filters: string[]
  difficulty_filters: number[]
  question_count: number
  show_explanations_immediately: boolean
  user_language: string
  section_order?: string[] | null
  review_only?: boolean
  allow_repeats?: boolean
  allow_exact_repeats?: boolean
  allow_concept_repeats?: boolean
  repeat_wrong_questions_in_review?: boolean
  review_wrong_questions_exact?: boolean
  review_wrong_questions_similar?: boolean
  adaptive_group?: string | null
}

export interface ExternalSourceRead {
  id: string
  name: string
  domain: string
  source_type: string
  source_quality: string
  has_question_text: boolean
  has_explanation: boolean
  has_observed_correct_rate: boolean
  copyright_risk: string
  allowed_use_notes: string
  last_checked_at: string | null
  active: boolean
  created_at: string
  updated_at: string
}

export interface ExternalQuestionObservationRead {
  id: string
  source_id: string
  source_name: string
  source_url: string | null
  section: string
  skill_tag: string
  concept_tag: string
  question_profile_summary: string
  question_fingerprint: string | null
  has_figure: boolean
  figure_type: string | null
  choices_profile_summary: string | null
  distractor_patterns: Record<string, unknown> | null
  observed_correct_rate: number | null
  observed_wrong_rate: number | null
  global_average: number | null
  sample_size: number | null
  external_difficulty_signal: string | null
  difficulty_level_signal: number | null
  matched_internal_question_id: string | null
  similarity_score: number | null
  source_confidence: string | null
  copyright_risk: string
  import_status: string
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ConceptDifficultyAnchorRead {
  id: string
  section: string
  skill_tag: string
  concept_tag: string
  source_id: string | null
  observed_correct_rate: number | null
  estimated_difficulty_level: number
  confidence: number
  example_profile_summary: string
  notes: string | null
  review_state: string
  reviewed_at: string | null
  reviewed_by: string | null
  review_notes: string | null
  created_at: string
  updated_at: string
}

export interface ResearchSummary {
  source_count: number
  observation_count: number
  anchor_count: number
  matched_observation_count: number
  observed_rate_count: number
}

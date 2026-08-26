import type {
  AdminGeneratePayload,
  AdminMaintenanceResult,
  ConceptDifficultyAnchorRead,
  CareerRequirementRead,
  AnswerFeedback,
  ExternalQuestionObservationRead,
  ExternalSourceRead,
  DashboardSummary,
  ImportLogRead,
  ImportResult,
  MistakeReviewItem,
  QuestionAuditIssue,
  QuestionListResponse,
  QuestionQueryParams,
  ResearchSummary,
  SectionMemoryStat,
  SectionSummary,
  SessionQuestion,
  SessionRead,
  SessionResults,
  SessionStartPayload,
  StatsOverview,
} from '../types/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

function buildQuestionQuery(params: QuestionQueryParams = {}): string {
  const searchParams = new URLSearchParams()
  if (params.section) searchParams.set('section', params.section)
  if (params.skill) searchParams.set('skill', params.skill)
  if (params.difficulty != null) searchParams.set('difficulty', String(params.difficulty))
  if (params.bankRole) searchParams.set('bank_role', params.bankRole)
  if (params.sourceBank) searchParams.set('source_bank', params.sourceBank)
  if (params.needsReview != null) searchParams.set('needs_review', String(params.needsReview))
  if (params.simulatorOnly != null) searchParams.set('simulator_only', String(params.simulatorOnly))
  if (params.publicImportOnly != null) searchParams.set('public_import_only', String(params.publicImportOnly))
  if (params.activeOnly != null) searchParams.set('active_only', String(params.activeOnly))
  if (params.limit != null) searchParams.set('limit', String(params.limit))
  if (params.offset != null) searchParams.set('offset', String(params.offset))
  const query = searchParams.toString()
  return query ? `?${query}` : ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: 'application/json',
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
    ...init,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed with status ${response.status}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export const api = {
  fetchStatsOverview: () => request<StatsOverview>('/stats/overview'),
  fetchSectionMemory: () => request<SectionMemoryStat[]>('/stats/section-memory'),
  fetchMistakes: () => request<MistakeReviewItem[]>('/stats/mistakes'),
  fetchQuestions: (params?: QuestionQueryParams) => request<QuestionListResponse>(`/questions${buildQuestionQuery({ limit: 24, ...params })}`),
  fetchImportStatus: () => request<ImportLogRead[]>('/admin/import-status'),
  fetchQuestionAudit: () => request<QuestionAuditIssue[]>('/admin/question-audit'),
  fetchSectionSummary: () => request<SectionSummary[]>('/admin/section-summary'),
  fetchDashboardSummary: () => request<DashboardSummary>('/admin/summary'),
  fetchCareerRequirements: () => request<CareerRequirementRead[]>('/admin/career-requirements'),
  fetchResearchSummary: () => request<ResearchSummary>('/admin/research-summary'),
  fetchExternalSources: () => request<ExternalSourceRead[]>('/admin/external-sources'),
  fetchExternalObservations: (limit = 200) =>
    request<ExternalQuestionObservationRead[]>(`/admin/external-observations?limit=${limit}`),
  fetchConceptAnchors: (limit = 200) =>
    request<ConceptDifficultyAnchorRead[]>(`/admin/concept-anchors?limit=${limit}`),
  discoverSources: () => request<AdminMaintenanceResult>('/admin/research/discover', { method: 'POST' }),
  harvestSource: (source: string, limit = 100) =>
    request<AdminMaintenanceResult>(`/admin/research/harvest?source=${encodeURIComponent(source)}&limit=${limit}`, {
      method: 'POST',
    }),
  matchObservations: () => request<AdminMaintenanceResult>('/admin/research/match', { method: 'POST' }),
  recalibrateFromExternalObservations: () =>
    request<AdminMaintenanceResult>('/admin/research/recalibrate', { method: 'POST' }),
  approveAnchor: (anchorId: string) =>
    request<AdminMaintenanceResult>(`/admin/research/anchors/${encodeURIComponent(anchorId)}/approve`, {
      method: 'POST',
    }),
  rejectAnchor: (anchorId: string) =>
    request<AdminMaintenanceResult>(`/admin/research/anchors/${encodeURIComponent(anchorId)}/reject`, {
      method: 'POST',
    }),
  dedupeQuestions: () => request<AdminMaintenanceResult>('/admin/dedupe', { method: 'POST' }),
  recalibrateQuestions: () => request<AdminMaintenanceResult>('/admin/recalibrate', { method: 'POST' }),
  generateQuestions: (payload: AdminGeneratePayload) =>
    request<AdminMaintenanceResult>('/admin/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  startSession: (payload: SessionStartPayload) =>
    request<SessionRead>('/sessions/start', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getNextQuestion: (sessionId: string) =>
    request<SessionQuestion | null>(`/sessions/${sessionId}/next-question`),
  answerQuestion: (sessionId: string, questionId: string, selectedAnswer: string, responseTimeSeconds: number) =>
    request<AnswerFeedback>(`/sessions/${sessionId}/answer`, {
      method: 'POST',
      body: JSON.stringify({
        question_id: questionId,
        selected_answer: selectedAnswer,
        response_time_seconds: responseTimeSeconds,
      }),
    }),
  finishSession: (sessionId: string) =>
    request<SessionResults>(`/sessions/${sessionId}/finish`, { method: 'POST' }),
  getResults: (sessionId: string) =>
    request<SessionResults>(`/sessions/${sessionId}/results`),
  deactivateQuestion: (questionId: string) =>
    request(`/questions/${questionId}/deactivate`, { method: 'POST' }),
  importQuestions: async (input: { file?: File | null; sourcePath?: string }) => {
    const formData = new FormData()
    if (input.file) {
      formData.append('upload', input.file)
    }
    if (input.sourcePath) {
      formData.append('source_path', input.sourcePath)
    }
    return request<ImportResult>('/questions/import', {
      method: 'POST',
      body: formData,
    })
  },
}

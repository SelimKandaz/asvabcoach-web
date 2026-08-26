import { ArrowLeft, Ban, CheckCheck, Database, RefreshCw, Sparkles, Upload, WandSparkles } from 'lucide-react'
import { useState } from 'react'

import type {
  AdminGeneratePayload,
  AdminMaintenanceResult,
  ConceptDifficultyAnchorRead,
  CareerRequirementRead,
  DashboardSummary,
  ExternalQuestionObservationRead,
  ExternalSourceRead,
  ImportLogRead,
  ImportResult,
  QuestionAuditIssue,
  QuestionListItem,
  QuestionQueryParams,
  ResearchSummary,
  SectionSummary,
} from '../types/api'

interface AdminImportPageProps {
  importLogs: ImportLogRead[]
  auditIssues: QuestionAuditIssue[]
  sectionSummary: SectionSummary[]
  dashboardSummary: DashboardSummary | null
  careerRequirements: CareerRequirementRead[]
  researchSummary: ResearchSummary | null
  externalSources: ExternalSourceRead[]
  externalObservations: ExternalQuestionObservationRead[]
  conceptAnchors: ConceptDifficultyAnchorRead[]
  questionPreview: QuestionListItem[]
  onBackHome: () => void
  onRefresh: () => Promise<void>
  onRefreshQuestionPreview: (filters?: QuestionQueryParams) => Promise<{ total: number; items: QuestionListItem[] }>
  onImport: (input: { file?: File | null; sourcePath?: string }) => Promise<ImportResult>
  onDedupe: () => Promise<AdminMaintenanceResult>
  onRecalibrate: () => Promise<AdminMaintenanceResult>
  onGenerate: (payload: AdminGeneratePayload) => Promise<AdminMaintenanceResult>
  onDiscoverSources: () => Promise<AdminMaintenanceResult>
  onHarvestSource: (source: string, limit: number) => Promise<AdminMaintenanceResult>
  onMatchObservations: () => Promise<AdminMaintenanceResult>
  onRecalibrateExternal: () => Promise<AdminMaintenanceResult>
  onApproveAnchor: (anchorId: string) => Promise<AdminMaintenanceResult>
  onRejectAnchor: (anchorId: string) => Promise<AdminMaintenanceResult>
  onDeactivateQuestion: (questionId: string) => Promise<void>
}

export function AdminImportPage({
  importLogs,
  auditIssues,
  sectionSummary,
  dashboardSummary,
  careerRequirements,
  researchSummary,
  externalSources,
  externalObservations,
  conceptAnchors,
  questionPreview,
  onBackHome,
  onRefresh,
  onRefreshQuestionPreview,
  onImport,
  onDedupe,
  onRecalibrate,
  onGenerate,
  onDiscoverSources,
  onHarvestSource,
  onMatchObservations,
  onRecalibrateExternal,
  onApproveAnchor,
  onRejectAnchor,
  onDeactivateQuestion,
}: AdminImportPageProps) {
  const [sourcePath, setSourcePath] = useState(
    'C:\\Users\\selim\\Downloads\\asvab_generated_10000_question_bank_v0_2.csv',
  )
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [importMessage, setImportMessage] = useState<string>('')
  const [actionMessage, setActionMessage] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [actionBusy, setActionBusy] = useState(false)
  const [generationSections, setGenerationSections] = useState('AR, MK, WK, PC, MC, EI, GS, AI, SI, AO')
  const [generationSkills, setGenerationSkills] = useState('constant_rate_total, depreciation_one_year, ohmmeter_measures_resistance, torque_direct')
  const [generationDifficultyLevels, setGenerationDifficultyLevels] = useState('1,2,3,4,5')
  const [generationCount, setGenerationCount] = useState(4)
  const [generationActive, setGenerationActive] = useState(true)
  const [researchSource, setResearchSource] = useState('src_official_asvab')
  const [researchLimit, setResearchLimit] = useState(40)
  const [previewBankRole, setPreviewBankRole] = useState('all')
  const [previewSourceBank, setPreviewSourceBank] = useState('')
  const [previewNeedsReviewOnly, setPreviewNeedsReviewOnly] = useState(false)
  const [previewSimulatorOnly, setPreviewSimulatorOnly] = useState(false)
  const [previewPublicOnly, setPreviewPublicOnly] = useState(false)

  const bankRoleOptions = [
    { value: 'all', label: 'All banks' },
    { value: 'main_practice', label: 'Main Practice' },
    { value: 'quality_patch', label: 'Quality Patch' },
    { value: 'elite_original_practice', label: 'Elite Original Practice' },
    { value: 'score_simulator', label: 'Score Simulator' },
    { value: 'public_pc_import', label: 'Public PC Import' },
    { value: 'review_archive', label: 'Review Archive' },
    { value: 'legacy_seed', label: 'Legacy Seed' },
  ]

  const bankRoleLabel: Record<string, string> = {
    main_practice: 'Main Practice',
    quality_patch: 'Quality Patch',
    elite_original_practice: 'Elite Original Practice',
    score_simulator: 'Score Simulator',
    public_pc_import: 'Public PC Import',
    review_archive: 'Review Archive',
    legacy_seed: 'Legacy Seed',
  }

  const handleImport = async () => {
    setBusy(true)
    try {
      const result = await onImport({ file: selectedFile, sourcePath })
      setImportMessage(
        `${result.status}: +${result.imported_count} imported, ${result.updated_count} updated, ${result.failed_count} failed.`,
      )
      await onRefresh()
    } finally {
      setBusy(false)
    }
  }

  const handleMaintenance = async (runner: () => Promise<AdminMaintenanceResult>, label: string) => {
    setActionBusy(true)
    try {
      const result = await runner()
      setActionMessage(`${label}: ${result.messages.join(' ') || result.status}.`)
    } finally {
      setActionBusy(false)
    }
  }

  const handleGenerate = async () => {
    setActionBusy(true)
    try {
      const sections = generationSections
        .split(',')
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean)
      const skillTags = generationSkills
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
      const difficultyLevels = generationDifficultyLevels
        .split(',')
        .map((item) => Number(item.trim()))
        .filter((value) => Number.isFinite(value) && value >= 1 && value <= 5)
      const payload: AdminGeneratePayload = {
        sections: sections.length ? sections : ['AR', 'MK', 'MC', 'EI', 'GS', 'AI', 'SI', 'AO'],
        skill_tags: skillTags,
        questions_per_section: generationCount,
        difficulty_levels: difficultyLevels.length ? difficultyLevels : [1, 2, 3, 4, 5],
        source_name: 'deterministic_generator',
        generation_method: 'template',
        active: generationActive,
        de_duplicate: true,
      }
      const result = await onGenerate(payload)
      setActionMessage(`Generate: ${result.messages.join(' ') || result.status}.`)
    } finally {
      setActionBusy(false)
    }
  }

  const runResearchAction = async (runner: () => Promise<AdminMaintenanceResult>, label: string) => {
    setActionBusy(true)
    try {
      const result = await runner()
      setActionMessage(`${label}: ${result.messages.join(' ') || result.status}.`)
    } finally {
      setActionBusy(false)
    }
  }

  const refreshPreview = async () => {
    const bankRole = previewBankRole === 'all' ? undefined : previewBankRole
    const activeOnly = previewBankRole === 'score_simulator' || previewBankRole === 'review_archive' ? false : true
    await onRefreshQuestionPreview({
      bankRole,
      sourceBank: previewSourceBank.trim() || undefined,
      needsReview: previewNeedsReviewOnly ? true : undefined,
      simulatorOnly: previewSimulatorOnly ? true : undefined,
      publicImportOnly: previewPublicOnly ? true : undefined,
      activeOnly,
      limit: 24,
    })
  }

  const readiness: Record<string, boolean> = dashboardSummary?.cat_ready ?? {}

  return (
    <div className="page-shell">
      <section className="hero-band compact">
        <div className="hero-copy">
          <span className="eyebrow">Admin Panel</span>
          <h1>Question bank intake, audit, and deactivation.</h1>
        </div>
        <div className="hero-actions">
          <button type="button" className="secondary-button" onClick={onBackHome}>
            <ArrowLeft size={16} />
            <span>Home</span>
          </button>
          <button type="button" className="secondary-button" onClick={() => void onRefresh()}>
            <RefreshCw size={16} />
            <span>Refresh</span>
          </button>
        </div>
      </section>

      <section className="workspace-band admin-grid">
        <section className="control-panel wide">
          <div className="panel-heading">
            <CheckCheck size={18} />
            <h2>Bank Summary</h2>
          </div>
          <div className="score-grid">
            <article className="metric-tile">
              <strong>{dashboardSummary?.total_questions ?? 0}</strong>
              <span>Total Questions</span>
            </article>
            <article className="metric-tile">
              <strong>{dashboardSummary?.active_questions ?? 0}</strong>
              <span>Active</span>
            </article>
            <article className="metric-tile">
              <strong>{dashboardSummary?.duplicate_questions ?? 0}</strong>
              <span>Duplicates</span>
            </article>
            <article className="metric-tile">
              <strong>{dashboardSummary?.needs_review_questions ?? 0}</strong>
              <span>Needs Review</span>
            </article>
          </div>
          <div className="status-pill-row">
            <span className={readiness.full_cat ? 'status-pill good' : 'status-pill warn'}>
              Full CAT {readiness.full_cat ? 'ready' : 'not ready'}
            </span>
            <span className={readiness.full_afqt ? 'status-pill good' : 'status-pill warn'}>
              Full AFQT {readiness.full_afqt ? 'ready' : 'not ready'}
            </span>
          </div>
        </section>

        <section className="control-panel">
          <div className="panel-heading">
            <Upload size={18} />
            <h2>Import Source</h2>
          </div>
          <label className="field">
            <span>Local Path</span>
            <input value={sourcePath} onChange={(event) => setSourcePath(event.target.value)} />
          </label>
          <label className="field">
            <span>Upload File</span>
            <input type="file" accept=".xlsx,.xls,.csv,.json,.zip" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
          </label>
          <button type="button" className="primary-button" onClick={() => void handleImport()} disabled={busy}>
            <Database size={16} />
            <span>Run Import</span>
          </button>
          {importMessage ? <p className="status-copy">{importMessage}</p> : null}
        </section>

        <section className="control-panel">
          <div className="panel-heading">
            <Sparkles size={18} />
            <h2>Generate Items</h2>
          </div>
          <label className="field">
            <span>Sections</span>
            <input value={generationSections} onChange={(event) => setGenerationSections(event.target.value)} />
          </label>
          <label className="field">
            <span>Skill Tags</span>
            <input value={generationSkills} onChange={(event) => setGenerationSkills(event.target.value)} />
          </label>
          <label className="field">
            <span>Questions per section</span>
            <input
              type="number"
              min={1}
              max={20}
              value={generationCount}
              onChange={(event) => setGenerationCount(Number(event.target.value))}
            />
          </label>
          <label className="field">
            <span>Difficulty levels</span>
            <input
              value={generationDifficultyLevels}
              onChange={(event) => setGenerationDifficultyLevels(event.target.value)}
              placeholder="1,2,3,4,5"
            />
          </label>
          <label className="switch-row">
            <span>Activate generated questions</span>
            <input type="checkbox" checked={generationActive} onChange={(event) => setGenerationActive(event.target.checked)} />
          </label>
          <button type="button" className="primary-button" onClick={() => void handleGenerate()} disabled={actionBusy}>
            <WandSparkles size={16} />
            <span>Generate Bank</span>
          </button>
          {actionMessage ? <p className="status-copy">{actionMessage}</p> : null}
        </section>

        <section className="control-panel wide">
          <div className="panel-heading">
            <Database size={18} />
            <h2>Research Dashboard</h2>
          </div>
          <div className="score-grid">
            <article className="metric-tile">
              <strong>{researchSummary?.source_count ?? 0}</strong>
              <span>Sources</span>
            </article>
            <article className="metric-tile">
              <strong>{researchSummary?.observation_count ?? 0}</strong>
              <span>Observations</span>
            </article>
            <article className="metric-tile">
              <strong>{researchSummary?.anchor_count ?? 0}</strong>
              <span>Anchors</span>
            </article>
            <article className="metric-tile">
              <strong>{researchSummary?.matched_observation_count ?? 0}</strong>
              <span>Matched</span>
            </article>
          </div>
          <div className="research-grid">
            <label className="field">
              <span>Harvest source</span>
              <input value={researchSource} onChange={(event) => setResearchSource(event.target.value)} />
            </label>
            <label className="field">
              <span>Harvest limit</span>
              <input
                type="number"
                min={1}
                max={200}
                value={researchLimit}
                onChange={(event) => setResearchLimit(Number(event.target.value))}
              />
            </label>
          </div>
          <div className="secondary-actions">
            <button type="button" className="secondary-button" onClick={() => void runResearchAction(onDiscoverSources, 'Discover sources')} disabled={actionBusy}>
              <Database size={16} />
              <span>Discover Sources</span>
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => void runResearchAction(() => onHarvestSource(researchSource, researchLimit), 'Harvest source')}
              disabled={actionBusy}
            >
              <Upload size={16} />
              <span>Harvest Source</span>
            </button>
            <button type="button" className="secondary-button" onClick={() => void runResearchAction(onMatchObservations, 'Match observations')} disabled={actionBusy}>
              <CheckCheck size={16} />
              <span>Match Observations</span>
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => void runResearchAction(onRecalibrateExternal, 'External recalibration')}
              disabled={actionBusy}
            >
              <Sparkles size={16} />
              <span>Recalibrate External</span>
            </button>
          </div>
          {actionMessage ? <p className="status-copy">{actionMessage}</p> : null}
        </section>

        <section className="control-panel wide">
          <div className="panel-heading">
            <h2>External Sources</h2>
          </div>
          <div className="table-stack">
            {externalSources.slice(0, 12).map((source) => (
              <article key={source.id} className="table-row">
                <strong>{source.name}</strong>
                <span>{source.source_type}</span>
                <span>{source.source_quality}</span>
                <span>{source.domain}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="control-panel wide">
          <div className="panel-heading">
            <h2>External Observations</h2>
          </div>
          <div className="table-stack">
            {externalObservations.slice(0, 12).map((observation) => (
              <article key={observation.id} className="table-row">
                <strong>{observation.section}</strong>
                <span>{observation.skill_tag}</span>
                <span>{observation.concept_tag}</span>
                <span>{observation.observed_correct_rate != null ? `${Math.round(observation.observed_correct_rate * 100)}%` : 'N/A'}</span>
                <span>{observation.matched_internal_question_id ?? 'unmatched'}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="control-panel wide">
          <div className="panel-heading">
            <h2>Concept Anchors</h2>
          </div>
          <div className="table-stack">
            {conceptAnchors.slice(0, 12).map((anchor) => (
              <article key={anchor.id} className="table-row">
                <strong>{anchor.concept_tag}</strong>
                <span>{anchor.section}</span>
                <span>{anchor.skill_tag}</span>
                <span>{anchor.review_state}</span>
                <span>{anchor.estimated_difficulty_level}</span>
                <div className="secondary-actions inline">
                  <button type="button" className="secondary-button" onClick={() => void runResearchAction(() => onApproveAnchor(anchor.id), `Approve ${anchor.concept_tag}`)} disabled={actionBusy}>
                    <CheckCheck size={16} />
                    <span>Approve</span>
                  </button>
                  <button type="button" className="secondary-button" onClick={() => void runResearchAction(() => onRejectAnchor(anchor.id), `Reject ${anchor.concept_tag}`)} disabled={actionBusy}>
                    <Ban size={16} />
                    <span>Reject</span>
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="control-panel">
          <div className="panel-heading">
            <Database size={18} />
            <h2>Quality Actions</h2>
          </div>
          <div className="action-stack">
            <button type="button" className="secondary-button" onClick={() => void handleMaintenance(onDedupe, 'Dedupe')} disabled={actionBusy}>
              <CheckCheck size={16} />
              <span>Dedupe Canonical Hashes</span>
            </button>
            <button type="button" className="secondary-button" onClick={() => void handleMaintenance(onRecalibrate, 'Recalibrate')} disabled={actionBusy}>
              <Sparkles size={16} />
              <span>Recalibrate Difficulty</span>
            </button>
          </div>
          {actionMessage ? <p className="status-copy">{actionMessage}</p> : null}
        </section>

        <section className="control-panel wide">
          <div className="panel-heading">
            <h2>Section Summary</h2>
          </div>
          <div className="table-stack">
            {sectionSummary.map((row) => (
              <article key={row.section} className="table-row">
                <strong>{row.section}</strong>
                <span>{row.active_questions}/{row.total_questions} active</span>
                <span>Verified {row.verified_questions}</span>
                <span>Dupes {row.duplicate_questions}</span>
                <span>Needs review {row.needs_review_questions}</span>
                <span>Avg diff {row.average_difficulty}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="control-panel">
          <div className="panel-heading">
            <h2>Recent Imports</h2>
          </div>
          <div className="table-stack">
            {importLogs.map((log) => (
              <article key={log.id} className="table-row">
                <strong>{log.source_name}</strong>
                <span>{log.imported_count} new</span>
                <span>{log.updated_count} updated</span>
                <span>{log.failed_count} failed</span>
              </article>
            ))}
          </div>
        </section>

        <section className="control-panel wide">
          <div className="panel-heading">
            <h2>Audit Issues</h2>
          </div>
          <div className="table-stack">
            {auditIssues.slice(0, 18).map((issue, index) => (
              <article key={`${issue.issue_type}-${issue.question_id ?? index}`} className="table-row">
                <strong>{issue.issue_type}</strong>
                <span>{issue.question_id ?? 'n/a'}</span>
                <span>{issue.severity ?? 'unknown'}</span>
                <span>{issue.details}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="control-panel">
          <div className="panel-heading">
            <h2>Career Requirements</h2>
          </div>
          <div className="table-stack">
            {careerRequirements.map((item) => (
              <article key={item.id} className="table-row">
                <strong>{item.branch}</strong>
                <span>{item.job_code}</span>
                <span>{item.job_title}</span>
                <span>{item.formula_key} {item.min_score ?? 'n/a'}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="control-panel wide">
          <div className="panel-heading">
            <h2>Question Preview</h2>
          </div>
          <div className="research-grid">
            <label className="field">
              <span>Bank Role</span>
              <select value={previewBankRole} onChange={(event) => setPreviewBankRole(event.target.value)}>
                {bankRoleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Source Bank</span>
              <input value={previewSourceBank} onChange={(event) => setPreviewSourceBank(event.target.value)} placeholder="asvab_v5_1_quality_patch_5000" />
            </label>
            <label className="switch-row">
              <span>Needs review only</span>
              <input type="checkbox" checked={previewNeedsReviewOnly} onChange={(event) => setPreviewNeedsReviewOnly(event.target.checked)} />
            </label>
            <label className="switch-row">
              <span>Simulator only</span>
              <input type="checkbox" checked={previewSimulatorOnly} onChange={(event) => setPreviewSimulatorOnly(event.target.checked)} />
            </label>
            <label className="switch-row">
              <span>Public import only</span>
              <input type="checkbox" checked={previewPublicOnly} onChange={(event) => setPreviewPublicOnly(event.target.checked)} />
            </label>
            <button type="button" className="secondary-button" onClick={() => void refreshPreview()}>
              <RefreshCw size={16} />
              <span>Refresh Preview</span>
            </button>
          </div>
          <div className="table-stack">
            {questionPreview.map((question) => (
              <article key={question.id} className="table-row">
                <strong>{question.section}</strong>
                <span>{question.skill_tag}</span>
                <span>{question.skill_tags?.join(', ') || 'n/a'}</span>
                <span>{question.subtype ?? question.template_family ?? 'n/a'}</span>
                <span>{question.difficulty_num ?? question.difficulty_level}</span>
                <span>{question.difficulty_level}</span>
                <span>{question.content_origin ?? 'n/a'}</span>
                <span>{question.question_text}</span>
                <span>{bankRoleLabel[question.bank_role ?? 'main_practice'] ?? question.bank_role ?? 'main_practice'}</span>
                <span>{question.source_bank ?? 'n/a'}</span>
                <span>{question.asset_path ?? 'no asset'}</span>
                <span>{question.is_simulator ? 'Simulator' : 'Practice'}</span>
                <span>{question.needs_review ? 'Needs review' : 'Ready'}</span>
                <button
                  type="button"
                  className="icon-button"
                  title="Deactivate question"
                  onClick={() => void onDeactivateQuestion(question.id)}
                >
                  <Ban size={16} />
                </button>
              </article>
            ))}
          </div>
        </section>
      </section>
    </div>
  )
}

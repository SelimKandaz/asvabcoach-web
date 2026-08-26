import { Activity, Brain, Database, Flag, Gauge, LogIn, Play, ShieldCheck, Target, Zap } from 'lucide-react'
import { useState } from 'react'

import type { Mode, SectionMemoryStat, SessionStartPayload, StatsOverview } from '../types/api'

const sections = ['AR', 'MK', 'WK', 'PC', 'GS', 'EI', 'AI', 'AS', 'SI', 'MC', 'AO']
const difficulties = [1, 2, 3, 4, 5]
const sectionLabels: Record<string, string> = {
  AR: 'Arithmetic Reasoning',
  MK: 'Mathematics Knowledge',
  WK: 'Word Knowledge',
  PC: 'Paragraph Comprehension',
  GS: 'General Science',
  EI: 'Electronics Information',
  AI: 'Auto Information',
  AS: 'Auto Shop',
  SI: 'Shop Information',
  MC: 'Mechanical Comprehension',
  AO: 'Assembling Objects',
}
interface QuickSectionPreset {
  key: string
  title: string
  detail: string
  sections: string[]
  adaptiveGroup?: string
}

const quickSectionPresets: QuickSectionPreset[] = [
  { key: 'math-only', title: 'Math Only', detail: 'AR + MK', sections: ['AR', 'MK'], adaptiveGroup: 'math' },
  ...sections.map((section) => ({
    key: section,
    title: section,
    detail: sectionLabels[section] ?? section,
    sections: [section],
  })),
]

interface HomePageProps {
  stats: StatsOverview | null
  sectionMemory: SectionMemoryStat[]
  onStart: (payload: SessionStartPayload) => Promise<void>
  onOpenReview: () => void
  onOpenAdmin: () => void
  busy: boolean
}

const modeCards: Array<{
  mode: Mode
  title: string
  icon: typeof Brain
  accent: string
}> = [
  { mode: 'study', title: 'Study Mode', icon: Brain, accent: 'moss' },
  { mode: 'standard_quiz', title: 'Standard Quiz', icon: ShieldCheck, accent: 'ember' },
  { mode: 'cat_simulation', title: 'Full CAT', icon: Target, accent: 'storm' },
  { mode: 'full_afqt_simulation', title: 'Full AFQT', icon: Flag, accent: 'gold' },
  { mode: 'score_simulator', title: 'Score Simulator', icon: Gauge, accent: 'storm' },
]

function formatLastAnswered(value: string | null): string {
  if (!value) {
    return 'No attempts yet'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString()
}

export function HomePage({ stats, sectionMemory, onStart, onOpenReview, onOpenAdmin, busy }: HomePageProps) {
  const [displayName, setDisplayName] = useState('Local Student')
  const [selectedSections, setSelectedSections] = useState<string[]>(['AR', 'MK', 'WK', 'PC'])
  const [selectedDifficulties, setSelectedDifficulties] = useState<number[]>([2, 3, 4])
  const [skillText, setSkillText] = useState('')
  const [questionCount, setQuestionCount] = useState(16)
  const [showImmediateExplanations, setShowImmediateExplanations] = useState(true)

  const toggleSection = (section: string) => {
    setSelectedSections((current) =>
      current.includes(section) ? current.filter((item) => item !== section) : [...current, section],
    )
  }

  const toggleDifficulty = (difficulty: number) => {
    setSelectedDifficulties((current) =>
      current.includes(difficulty)
        ? current.filter((item) => item !== difficulty)
        : [...current, difficulty].sort(),
    )
  }

  const buildSessionPayload = (
    mode: Mode,
    sectionFiltersOverride?: string[],
    adaptiveGroupOverride?: string | null,
  ): SessionStartPayload => {
    const skillFilters = skillText
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)

    const catBlueprintSections = ['GS', 'AR', 'WK', 'PC', 'MK', 'EI', 'AI', 'AS', 'SI', 'MC', 'AO']
    const afqtSections = ['AR', 'WK', 'PC', 'MK']

    const adaptiveGroup =
      adaptiveGroupOverride ??
      (sectionFiltersOverride && sectionFiltersOverride.length === 1 ? sectionFiltersOverride[0] : null)

    return {
      display_name: displayName,
      mode,
      section_filters:
        mode === 'cat_simulation' || mode === 'score_simulator'
          ? catBlueprintSections
          : mode === 'full_afqt_simulation'
          ? afqtSections
          : sectionFiltersOverride ?? selectedSections,
      skill_filters: mode === 'study' || mode === 'standard_quiz' ? skillFilters : [],
      difficulty_filters: selectedDifficulties,
      question_count: questionCount,
      show_explanations_immediately:
        mode === 'study' ? true : mode === 'score_simulator' ? false : showImmediateExplanations,
      user_language: 'en',
      allow_repeats: false,
      repeat_wrong_questions_in_review: true,
      section_order: sectionFiltersOverride ?? selectedSections,
      adaptive_group: adaptiveGroup,
    }
  }

  const handleStart = async (mode: Mode) => {
    await onStart(buildSessionPayload(mode))
  }

  const handleQuickSectionQuiz = async (preset: QuickSectionPreset) => {
    await onStart(buildSessionPayload('standard_quiz', preset.sections, preset.adaptiveGroup ?? null))
  }

  return (
    <div className="page-shell">
      <section className="hero-band">
        <div className="hero-copy">
          <span className="eyebrow">ASVAB Coach</span>
          <h1>Adaptive practice with a deterministic scoring core.</h1>
          <p>
            Estimated practice metrics, section-by-section progress, and a clean route from question
            bank import to review.
          </p>
          <div className="hero-actions">
            <button type="button" className="secondary-button" onClick={onOpenReview}>
              <ShieldCheck size={16} />
              <span>Review Mistakes</span>
            </button>
            <button type="button" className="secondary-button" onClick={onOpenAdmin}>
              <LogIn size={16} />
              <span>Admin Giriş</span>
            </button>
          </div>
        </div>
        <div className="hero-metrics">
          <article className="metric-tile">
            <Activity size={18} />
            <strong>{stats?.total_sessions ?? 0}</strong>
            <span>Sessions</span>
          </article>
          <article className="metric-tile">
            <Zap size={18} />
            <strong>{stats ? `${Math.round(stats.accuracy * 100)}%` : '0%'}</strong>
            <span>Accuracy</span>
          </article>
          <article className="metric-tile">
            <Database size={18} />
            <strong>{stats?.questions_answered ?? 0}</strong>
            <span>Responses</span>
          </article>
          <article className="metric-tile">
            <Flag size={18} />
            <strong>{stats?.needs_review_count ?? 0}</strong>
            <span>Needs Review</span>
          </article>
        </div>
      </section>

      <section className="workspace-band">
        <div className="mode-grid">
          {modeCards.map(({ mode, title, icon: Icon, accent }) => (
            <button
              key={mode}
              type="button"
              className={`mode-card accent-${accent}`}
              onClick={() => void handleStart(mode)}
              disabled={busy}
            >
              <span className="mode-card-icon">
                <Icon size={18} />
              </span>
              <strong>{title}</strong>
              <span>
                {mode === 'study'
                  ? 'Immediate feedback'
                  : mode === 'score_simulator'
                  ? 'Dedicated simulator bank'
                  : 'Timed practice flow'}
              </span>
              <span className="mode-card-action">
                <Play size={16} />
              </span>
            </button>
          ))}
        </div>

        <div className="control-grid">
          <section className="control-panel">
            <div className="panel-heading">
              <h2>Session Setup</h2>
            </div>
            <label className="field">
              <span>Display Name</span>
              <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            </label>
            <label className="field">
              <span>Skill Filter</span>
              <input
                value={skillText}
                onChange={(event) => setSkillText(event.target.value)}
                placeholder="percentages, algebra, reading_inference"
              />
            </label>
            <label className="field">
              <span>Question Count</span>
              <input
                type="number"
                min={5}
                max={64}
                value={questionCount}
                onChange={(event) => setQuestionCount(Number(event.target.value))}
              />
            </label>
            <label className="switch-row">
              <span>Show explanations during quiz</span>
              <input
                type="checkbox"
                checked={showImmediateExplanations}
                onChange={(event) => setShowImmediateExplanations(event.target.checked)}
              />
            </label>
          </section>

          <section className="control-panel">
            <div className="panel-heading">
              <h2>Sections</h2>
            </div>
            <div className="pill-grid">
              {sections.map((section) => (
                <button
                  key={section}
                  type="button"
                  className={selectedSections.includes(section) ? 'pill active' : 'pill'}
                  onClick={() => toggleSection(section)}
                >
                  {section}
                </button>
              ))}
            </div>
            <div className="panel-heading">
              <h2>Difficulties</h2>
            </div>
            <div className="pill-grid">
              {difficulties.map((difficulty) => (
                <button
                  key={difficulty}
                  type="button"
                  className={selectedDifficulties.includes(difficulty) ? 'pill active' : 'pill'}
                  onClick={() => toggleDifficulty(difficulty)}
                >
                  {difficulty}
                </button>
              ))}
            </div>
          </section>

          <section className="control-panel wide">
            <div className="panel-heading">
              <h2>Section Exams</h2>
            </div>
            <div className="quick-launch-grid">
              {quickSectionPresets.map((preset) => (
                <button
                  key={preset.key}
                  type="button"
                  className="section-launch-button"
                  onClick={() => void handleQuickSectionQuiz(preset)}
                  disabled={busy}
                >
                  <strong>{preset.title}</strong>
                  <span>{preset.detail}</span>
                  <span className="section-launch-action">
                    <Play size={14} />
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section className="control-panel status-panel">
            <div className="panel-heading">
              <h2>Focus Queue</h2>
            </div>
            {stats?.weak_skills?.length ? (
              <ul className="weak-skill-list">
                {stats.weak_skills.map((skill) => (
                  <li key={skill}>
                    <Target size={16} />
                    <span>{skill.replace(':', ' / ').replaceAll('_', ' ')}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted-copy">No weak-skill history yet.</p>
            )}
            <div className="secondary-actions">
              <button type="button" className="secondary-button" onClick={onOpenReview}>
                <ShieldCheck size={16} />
                <span>Review Mistakes</span>
              </button>
              <button type="button" className="secondary-button" onClick={onOpenAdmin}>
                <LogIn size={16} />
                <span>Admin Giriş</span>
              </button>
            </div>
          </section>

          <section className="control-panel wide">
            <div className="panel-heading">
              <h2>Section Memory</h2>
            </div>
            {sectionMemory.length ? (
              <div className="table-stack">
                {sectionMemory.map((item) => (
                  <article key={item.section} className="table-row section-memory-row">
                    <strong>{item.section_label}</strong>
                    <span>{item.attempts} solved</span>
                    <span>{item.correct} correct</span>
                    <span>{item.wrong} wrong</span>
                    <span>{Math.round(item.accuracy * 100)}%</span>
                    <span>{formatLastAnswered(item.last_answered_at)}</span>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted-copy">Section memory appears after you answer questions.</p>
            )}
          </section>
        </div>
      </section>
    </div>
  )
}

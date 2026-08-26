import { Gauge, LockKeyhole, Radar, StopCircle } from 'lucide-react'

import { QuestionCard } from '../components/QuestionCard'
import { SectionProgress } from '../components/SectionProgress'
import { Timer } from '../components/Timer'
import type { Mode, SessionQuestion } from '../types/api'

interface CatSimulationPageProps {
  mode: Mode
  question: SessionQuestion
  questionStartedAt: number
  busy: boolean
  onAnswer: (choice: 'A' | 'B' | 'C' | 'D', responseTimeSeconds: number) => Promise<void>
  onFinish: () => Promise<void>
}

export function CatSimulationPage({
  mode,
  question,
  questionStartedAt,
  busy,
  onAnswer,
  onFinish,
}: CatSimulationPageProps) {
  const handleSelect = async (choice: 'A' | 'B' | 'C' | 'D') => {
    if (busy) {
      return
    }
    const elapsed = Math.max(1, Math.round((Date.now() - questionStartedAt) / 1000))
    await onAnswer(choice, elapsed)
  }

  return (
    <div className="page-shell">
      <section className="session-band">
        <div className="session-topline">
          <div>
            <span className="eyebrow">
              {mode === 'cat_simulation' ? 'Full CAT' : mode === 'score_simulator' ? 'Score Simulator' : 'Full AFQT'}
            </span>
            <h1>{question.section_label}</h1>
          </div>
          <Timer startedAtMs={questionStartedAt} paused={busy} />
        </div>
        <div className="session-meta-grid">
          <SectionProgress
            label={`Question ${question.prompt_number}`}
            value={question.prompt_number}
            max={question.progress_total}
          />
          <SectionProgress
            label={question.section}
            value={question.section_progress}
            max={question.section_target}
          />
          <div className="meta-chip">
            <Radar size={16} />
            <span>{question.skill_tag.replaceAll('_', ' ')}</span>
          </div>
          <div className="meta-chip">
            <Gauge size={16} />
            <span>Difficulty: {question.difficulty_level}</span>
          </div>
          <div className="meta-chip">
            <Gauge size={16} />
            <span>
              Section score: {question.section_standard_score_estimate != null ? question.section_standard_score_estimate.toFixed(1) : '50.0'}
            </span>
          </div>
          <div className="meta-chip">
            <LockKeyhole size={16} />
            <span>No backtracking</span>
          </div>
        </div>
      </section>

      <section className="workspace-band session-layout">
        <QuestionCard
          questionText={question.question_text}
          choices={question.choices}
          selectedAnswer={null}
          disabled={busy}
          revealAnswer={false}
          figureSvg={question.figure_svg ?? null}
          figureAltText={question.figure_alt_text ?? null}
          assetPath={question.asset_path ?? null}
          onSelect={(choice) => void handleSelect(choice)}
        />
        <div className="review-column">
          <div className="placeholder-panel tight">
            <p>Results and explanations open after the simulation wraps.</p>
          </div>
          <div className="action-stack">
            <button type="button" className="ghost-button" onClick={() => void onFinish()} disabled={busy}>
              <StopCircle size={16} />
              <span>Finish Simulation</span>
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

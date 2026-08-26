import { ArrowRight, CheckCircle2, StopCircle } from 'lucide-react'

import { ExplanationPanel } from '../components/ExplanationPanel'
import { QuestionCard } from '../components/QuestionCard'
import { SectionProgress } from '../components/SectionProgress'
import { Timer } from '../components/Timer'
import type { AnswerFeedback, Mode, SessionQuestion } from '../types/api'

interface StudyModePageProps {
  mode: Mode
  question: SessionQuestion
  questionStartedAt: number
  answerFeedback: AnswerFeedback | null
  busy: boolean
  onAnswer: (choice: 'A' | 'B' | 'C' | 'D', responseTimeSeconds: number) => Promise<void>
  onNext: () => Promise<void>
  onFinish: () => Promise<void>
}

export function StudyModePage({
  mode,
  question,
  questionStartedAt,
  answerFeedback,
  busy,
  onAnswer,
  onNext,
  onFinish,
}: StudyModePageProps) {
  const answeredThisQuestion = answerFeedback?.question_id === question.question_id

  const handleSelect = async (choice: 'A' | 'B' | 'C' | 'D') => {
    if (answeredThisQuestion || busy) {
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
              {mode === 'study' ? 'Study Mode' : mode === 'score_simulator' ? 'Score Simulator' : 'Standard Quiz'}
            </span>
            <h1>{question.section_label}</h1>
          </div>
          <Timer startedAtMs={questionStartedAt} paused={answeredThisQuestion} />
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
          <div className="meta-chip">Skill: {question.skill_tag.replaceAll('_', ' ')}</div>
          <div className="meta-chip">Difficulty: {question.difficulty_level}</div>
          <div className="meta-chip">
            Section score: {question.section_standard_score_estimate != null ? question.section_standard_score_estimate.toFixed(1) : '50.0'}
          </div>
        </div>
      </section>

      <section className="workspace-band session-layout">
        <QuestionCard
          questionText={question.question_text}
          choices={question.choices}
          selectedAnswer={answeredThisQuestion ? answerFeedback?.selected_answer ?? null : null}
          correctAnswer={answerFeedback?.correct_answer ?? null}
          disabled={answeredThisQuestion || busy}
          revealAnswer={Boolean(answeredThisQuestion)}
          figureSvg={question.figure_svg ?? null}
          figureAltText={question.figure_alt_text ?? null}
          assetPath={question.asset_path ?? null}
          onSelect={(choice) => void handleSelect(choice)}
        />

        <div className="review-column">
          {answeredThisQuestion ? (
            <div className={`answer-banner ${answerFeedback?.is_correct ? 'is-correct' : 'is-wrong'}`}>
              <CheckCircle2 size={18} />
              <span>{answerFeedback?.is_correct ? 'Correct' : 'Incorrect'}</span>
            </div>
          ) : null}

          {answeredThisQuestion && answerFeedback?.explanation ? (
            <ExplanationPanel
              explanation={answerFeedback.explanation}
              quickMethod={answerFeedback.quick_method}
              wrongAnswerReason={answerFeedback.wrong_answer_reason}
              correctAnswer={answerFeedback.correct_answer}
            />
          ) : (
            <div className="placeholder-panel">
              <p>Explanation panel unlocks after each answer.</p>
            </div>
          )}

          <div className="action-stack">
            <button
              type="button"
              className="primary-button"
              onClick={() => void onNext()}
              disabled={!answeredThisQuestion || busy}
            >
              <ArrowRight size={16} />
              <span>Next Question</span>
            </button>
            <button type="button" className="ghost-button" onClick={() => void onFinish()} disabled={busy}>
              <StopCircle size={16} />
              <span>Finish Session</span>
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

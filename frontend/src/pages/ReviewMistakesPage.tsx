import { ArrowLeft, RotateCcw } from 'lucide-react'

import { ExplanationPanel } from '../components/ExplanationPanel'
import type { MistakeReviewItem, SectionMemoryStat } from '../types/api'

interface ReviewMistakesPageProps {
  sectionMemory: SectionMemoryStat[]
  mistakes: MistakeReviewItem[]
  onBackHome: () => void
  onRefresh: () => Promise<void>
}

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

export function ReviewMistakesPage({ sectionMemory, mistakes, onBackHome, onRefresh }: ReviewMistakesPageProps) {
  return (
    <div className="page-shell">
      <section className="hero-band compact">
        <div className="hero-copy">
          <span className="eyebrow">Review Mistakes</span>
          <h1>Missed questions queued for another pass.</h1>
        </div>
        <div className="hero-actions">
          <button type="button" className="secondary-button" onClick={onBackHome}>
            <ArrowLeft size={16} />
            <span>Home</span>
          </button>
          <button type="button" className="secondary-button" onClick={() => void onRefresh()}>
            <RotateCcw size={16} />
            <span>Refresh</span>
          </button>
        </div>
      </section>

      <section className="workspace-band">
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
          <div className="placeholder-panel tight">
            <p>No section history yet.</p>
          </div>
        )}
      </section>

      <section className="workspace-band review-stack">
        {mistakes.length ? (
          mistakes.map((item) => (
            <article key={`${item.question.id}-${item.selected_answer}`} className="mistake-card">
              <div className="mistake-meta">
                <span>{item.question.section}</span>
                <span>{item.question.skill_tag.replaceAll('_', ' ')}</span>
                <span>Difficulty {item.question.difficulty_level}</span>
              </div>
              {item.question.figure_svg ? (
                <div
                  className="question-figure"
                  role={item.question.figure_alt_text ? 'img' : undefined}
                  aria-label={item.question.figure_alt_text ?? undefined}
                  dangerouslySetInnerHTML={{ __html: item.question.figure_svg }}
                />
              ) : item.question.asset_path ? (
                <div className="question-figure">
                  <img
                    src={`/api/question-assets/${encodeURI(item.question.asset_path.replace(/^\/+/, ''))}`}
                    alt={item.question.figure_alt_text ?? item.question.question_text}
                  />
                </div>
              ) : null}
              <h2>{item.question.question_text}</h2>
              <div className="mistake-choices">
                <span>Your answer: {item.selected_answer}</span>
                <span>Correct answer: {item.correct_answer}</span>
              </div>
              <ExplanationPanel
                explanation={item.explanation}
                quickMethod={item.quick_method}
                wrongAnswerReason={null}
                correctAnswer={item.correct_answer}
              />
            </article>
          ))
        ) : (
          <div className="placeholder-panel">
            <p>No missed questions yet.</p>
          </div>
        )}
      </section>
    </div>
  )
}

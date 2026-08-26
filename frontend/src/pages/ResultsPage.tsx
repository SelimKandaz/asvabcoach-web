import { ArrowLeft, Brain, ChartColumn, ShieldCheck, Sparkles } from 'lucide-react'

import { ScoreSummary } from '../components/ScoreSummary'
import type { SectionPerformance, SessionResults } from '../types/api'

interface ResultsPageProps {
  results: SessionResults
  onBackHome: () => void
  onOpenReview: () => void
}

const SCORE_ORDER = ['GS', 'AR', 'WK', 'PC', 'MK', 'EI', 'AI', 'AS', 'SI', 'MC', 'AO', 'VE']
const BRANCH_ORDER = ['Army', 'Air Force', 'Navy', 'Marines']

function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'N/A'
  }
  return Math.round(value).toString()
}

function formatDate(value: string | null): string {
  if (!value) {
    return ''
  }
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

export function ResultsPage({ results, onBackHome, onOpenReview }: ResultsPageProps) {
  const sectionPerformanceMap: Record<string, SectionPerformance> = Object.fromEntries(
    results.by_section.map((item) => [item.section, item]),
  ) as Record<string, SectionPerformance>

  return (
    <div className="page-shell">
      <section className="hero-band compact">
        <div className="hero-copy">
          <span className="eyebrow">{results.report_label}</span>
          <h1>{results.mode === 'score_simulator' ? 'Estimated score simulator report.' : 'Estimated ASVAB-style score report.'}</h1>
          <p>
            {results.report_date ? `Generated ${formatDate(results.report_date)}.` : ''}
            {results.warning_text ? ` ${results.warning_text}` : ''}
          </p>
        </div>
        <div className="hero-actions">
          <button type="button" className="secondary-button" onClick={onBackHome}>
            <ArrowLeft size={16} />
            <span>Home</span>
          </button>
          <button type="button" className="secondary-button" onClick={onOpenReview}>
            <ShieldCheck size={16} />
            <span>Review Mistakes</span>
          </button>
        </div>
      </section>

      <section className="workspace-band">
        <div className="score-grid">
          <ScoreSummary
            title="Accuracy"
            value={`${Math.round(results.accuracy * 100)}%`}
            detail={`${results.correct_count}/${results.total_answered} correct`}
          />
          <ScoreSummary
            title="AFQT Estimate"
            value={results.estimated_afqt_range ?? 'N/A'}
            detail={
              results.estimated_afqt_percentile != null
                ? `Percentile ${Math.round(results.estimated_afqt_percentile)}`
                : 'Confidence limited'
            }
          />
          <ScoreSummary
            title="GT Estimate"
            value={formatScore(results.estimated_gt_score)}
            detail="Army line score estimate"
          />
          <ScoreSummary
            title={results.mode === 'score_simulator' ? 'Readiness' : 'Readiness Score'}
            value={results.readiness_score != null ? `${Math.round(results.readiness_score)}/100` : 'N/A'}
            detail={
              results.readiness_confidence ? `${results.readiness_confidence.toUpperCase()} confidence` : 'No readiness data'
            }
          />
          <ScoreSummary
            title="Confidence"
            value={(results.afqt_confidence ?? 'low').toUpperCase()}
            detail={`${results.excluded_bad_questions} questions filtered out`}
          />
        </div>

        <div className="analysis-grid">
          <section className="analysis-panel">
            <div className="panel-heading">
              <ChartColumn size={18} />
              <h2>Section Standard Scores</h2>
            </div>
            <div className="table-stack">
              {SCORE_ORDER.map((section) => {
                const row = sectionPerformanceMap[section]
                return (
                  <article key={section} className="table-row">
                  <strong>{section}</strong>
                  <span>{formatScore(results.standard_scores[section])}</span>
                  <span>
                    {results.standard_score_estimates[section] != null
                      ? `Theta ${results.theta_estimates[section]?.toFixed(2) ?? 'N/A'}`
                      : 'Not tested'}
                  </span>
                  <span>
                    {row?.percentile_estimate != null ? `P ${Math.round(row.percentile_estimate ?? 0)}` : ' '}
                  </span>
                </article>
                )
              })}
            </div>
          </section>

          <section className="analysis-panel">
            <div className="panel-heading">
              <Sparkles size={18} />
              <h2>Branch Composites</h2>
            </div>
            <div className="table-stack">
              {BRANCH_ORDER.map((branch) => {
                const rows = results.composite_rows[branch] ?? []
                return (
                  <article key={branch} className="branch-block">
                    <div className="panel-heading spaced">
                      <h2>{branch}</h2>
                    </div>
                    <div className="table-stack">
                      {rows.map((row) => (
                        <div key={`${branch}-${row.label}`} className="table-row">
                          <strong>{row.label}</strong>
                          <span>{row.formula}</span>
                          <span>{formatScore(row.score)}</span>
                        </div>
                      ))}
                    </div>
                  </article>
                )
              })}
            </div>
          </section>
        </div>

        <div className="analysis-grid">
          <section className="analysis-panel">
            <div className="panel-heading">
              <Brain size={18} />
              <h2>Weak Skills</h2>
            </div>
            <ul className="weak-skill-list">
              {results.weak_skills.length ? (
                results.weak_skills.map((skill) => (
                  <li key={skill}>
                    <span>{skill.replace(':', ' / ').replaceAll('_', ' ')}</span>
                  </li>
                ))
              ) : (
                <li>
                  <span>No weak-skill data yet.</span>
                </li>
              )}
            </ul>
            <div className="panel-heading spaced">
              <h2>Recommended Next Practice</h2>
            </div>
            <ul className="weak-skill-list">
              {results.recommended_next_practice.length ? (
                results.recommended_next_practice.map((item) => (
                  <li key={item}>
                    <span>{item}</span>
                  </li>
                ))
              ) : (
                <li>
                  <span>Keep rotating across the selected sections.</span>
                </li>
              )}
            </ul>
          </section>

          <section className="analysis-panel">
            <div className="panel-heading">
              <ShieldCheck size={18} />
              <h2>Session Breakdown</h2>
            </div>
            <div className="table-stack">
              {results.by_section.map((section) => (
                <article key={section.section} className="table-row">
                  <strong>{section.section}</strong>
                  <span>{section.questions_answered}</span>
                  <span>{Math.round(section.accuracy * 100)}%</span>
                  <span>{formatScore(section.standard_score_estimate)}</span>
                </article>
              ))}
            </div>
            {results.branch_confidence_warnings.length ? (
              <>
                <div className="panel-heading spaced">
                  <h2>Confidence Notes</h2>
                </div>
                <ul className="weak-skill-list">
                  {results.branch_confidence_warnings.map((note) => (
                    <li key={note}>
                      <span>{note}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </section>
        </div>
      </section>
    </div>
  )
}

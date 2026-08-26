import { startTransition, useEffect, useState } from 'react'
import { AlertTriangle, Home, LoaderCircle, LogIn, ShieldCheck } from 'lucide-react'

import './App.css'
import { api } from './api/client'
import { AdminImportPage } from './pages/AdminImportPage'
import { CatSimulationPage } from './pages/CatSimulationPage'
import { HomePage } from './pages/HomePage'
import { ResultsPage } from './pages/ResultsPage'
import { ReviewMistakesPage } from './pages/ReviewMistakesPage'
import { StudyModePage } from './pages/StudyModePage'
import type {
  AdminGeneratePayload,
  CareerRequirementRead,
  AnswerFeedback,
  ConceptDifficultyAnchorRead,
  ExternalQuestionObservationRead,
  ExternalSourceRead,
  ImportLogRead,
  MistakeReviewItem,
  QuestionAuditIssue,
  QuestionListItem,
  QuestionQueryParams,
  DashboardSummary,
  ResearchSummary,
  SectionMemoryStat,
  SectionSummary,
  SessionQuestion,
  SessionRead,
  SessionResults,
  SessionStartPayload,
  StatsOverview,
} from './types/api'

type View = 'home' | 'study' | 'cat' | 'results' | 'review' | 'admin'

function App() {
  const [view, setView] = useState<View>('home')
  const [stats, setStats] = useState<StatsOverview | null>(null)
  const [sectionMemory, setSectionMemory] = useState<SectionMemoryStat[]>([])
  const [mistakes, setMistakes] = useState<MistakeReviewItem[]>([])
  const [importLogs, setImportLogs] = useState<ImportLogRead[]>([])
  const [auditIssues, setAuditIssues] = useState<QuestionAuditIssue[]>([])
  const [sectionSummary, setSectionSummary] = useState<SectionSummary[]>([])
  const [questionPreview, setQuestionPreview] = useState<QuestionListItem[]>([])
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null)
  const [careerRequirements, setCareerRequirements] = useState<CareerRequirementRead[]>([])
  const [researchSummary, setResearchSummary] = useState<ResearchSummary | null>(null)
  const [externalSources, setExternalSources] = useState<ExternalSourceRead[]>([])
  const [externalObservations, setExternalObservations] = useState<ExternalQuestionObservationRead[]>([])
  const [conceptAnchors, setConceptAnchors] = useState<ConceptDifficultyAnchorRead[]>([])
  const [session, setSession] = useState<SessionRead | null>(null)
  const [question, setQuestion] = useState<SessionQuestion | null>(null)
  const [questionStartedAt, setQuestionStartedAt] = useState(0)
  const [answerFeedback, setAnswerFeedback] = useState<AnswerFeedback | null>(null)
  const [results, setResults] = useState<SessionResults | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')

  const refreshDashboard = async () => {
    const [statsOverview, sectionMemoryRows, reviewItems, preview] = await Promise.all([
      api.fetchStatsOverview(),
      api.fetchSectionMemory(),
      api.fetchMistakes(),
      api.fetchQuestions(),
    ])
    startTransition(() => {
      setStats(statsOverview)
      setSectionMemory(sectionMemoryRows)
      setMistakes(reviewItems)
      setQuestionPreview(preview.items)
    })
  }

  const refreshQuestionPreview = async (filters?: QuestionQueryParams) => {
    const preview = await api.fetchQuestions(filters)
    startTransition(() => {
      setQuestionPreview(preview.items)
    })
    return preview
  }

  const refreshAdmin = async () => {
    const [logs, issues, summary, preview, requirements, research, sources, observations, anchors] = await Promise.all([
      api.fetchImportStatus(),
      api.fetchQuestionAudit(),
      api.fetchDashboardSummary(),
      api.fetchQuestions(),
      api.fetchCareerRequirements(),
      api.fetchResearchSummary(),
      api.fetchExternalSources(),
      api.fetchExternalObservations(),
      api.fetchConceptAnchors(),
    ])
    startTransition(() => {
      setImportLogs(logs)
      setAuditIssues(issues)
      setDashboardSummary(summary)
      setSectionSummary(summary.by_section)
      setQuestionPreview(preview.items)
      setCareerRequirements(requirements)
      setResearchSummary(research)
      setExternalSources(sources)
      setExternalObservations(observations)
      setConceptAnchors(anchors)
    })
  }

  useEffect(() => {
    void (async () => {
      setLoading(true)
      try {
        await refreshDashboard()
      } catch (caughtError) {
        setError(caughtError instanceof Error ? caughtError.message : 'Failed to load dashboard data.')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const navigateHome = async () => {
    setView('home')
    setAnswerFeedback(null)
    setQuestion(null)
    await refreshDashboard()
  }

  const handleStart = async (payload: SessionStartPayload) => {
    setLoading(true)
    setError('')
    try {
      const nextSession = await api.startSession(payload)
      const nextQuestion = await api.getNextQuestion(nextSession.id)

      setSession(nextSession)
      setAnswerFeedback(null)
      setResults(null)

      if (nextQuestion) {
        setQuestion(nextQuestion)
        setQuestionStartedAt(Date.now())
        setView(payload.mode === 'study' || payload.mode === 'standard_quiz' ? 'study' : 'cat')
      } else {
        const nextResults = await api.getResults(nextSession.id)
        setResults(nextResults)
        setView('results')
      }
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Failed to start the session.')
    } finally {
      setLoading(false)
    }
  }

  const advanceToNextQuestion = async () => {
    if (!session) {
      return
    }
    setLoading(true)
    setError('')
    try {
      const nextQuestion = await api.getNextQuestion(session.id)
      setAnswerFeedback(null)
      if (nextQuestion) {
        setQuestion(nextQuestion)
        setQuestionStartedAt(Date.now())
      } else {
        const nextResults = await api.getResults(session.id)
        setResults(nextResults)
        setView('results')
        await refreshDashboard()
      }
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Failed to load the next question.')
    } finally {
      setLoading(false)
    }
  }

  const handleAnswer = async (selectedAnswer: 'A' | 'B' | 'C' | 'D', responseTimeSeconds: number) => {
    if (!session || !question) {
      return
    }

    setLoading(true)
    setError('')
    try {
      const feedback = await api.answerQuestion(
        session.id,
        question.question_id,
        selectedAnswer,
        responseTimeSeconds,
      )
      setAnswerFeedback(feedback)

      const isAdaptive =
        session.mode === 'cat_simulation' ||
        session.mode === 'full_afqt_simulation' ||
        session.mode === 'score_simulator'
      if (feedback.session_completed) {
        const nextResults = await api.getResults(session.id)
        setResults(nextResults)
        setView('results')
        await refreshDashboard()
      } else if (isAdaptive) {
        const nextQuestion = await api.getNextQuestion(session.id)
        if (nextQuestion) {
          setQuestion(nextQuestion)
          setQuestionStartedAt(Date.now())
          setAnswerFeedback(null)
        }
      }
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Failed to submit the answer.')
    } finally {
      setLoading(false)
    }
  }

  const handleFinishSession = async () => {
    if (!session) {
      return
    }
    setLoading(true)
    setError('')
    try {
      const nextResults = await api.finishSession(session.id)
      setResults(nextResults)
      setView('results')
      await refreshDashboard()
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Failed to finish the session.')
    } finally {
      setLoading(false)
    }
  }

  const openReview = async () => {
    setLoading(true)
    setError('')
    try {
      const [memoryRows, reviewItems] = await Promise.all([api.fetchSectionMemory(), api.fetchMistakes()])
      setSectionMemory(memoryRows)
      setMistakes(reviewItems)
      setView('review')
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Failed to load mistakes.')
    } finally {
      setLoading(false)
    }
  }

  const openAdmin = async () => {
    setLoading(true)
    setError('')
    try {
      await refreshAdmin()
      setView('admin')
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Failed to load admin data.')
    } finally {
      setLoading(false)
    }
  }

  const handleImport = async (input: { file?: File | null; sourcePath?: string }) => {
    const result = await api.importQuestions(input)
    await refreshAdmin()
    await refreshDashboard()
    return result
  }

  const handleDedupeQuestions = async () => {
    const result = await api.dedupeQuestions()
    await refreshAdmin()
    return result
  }

  const handleRecalibrateQuestions = async () => {
    const result = await api.recalibrateQuestions()
    await refreshAdmin()
    return result
  }

  const handleGenerateQuestions = async (payload: AdminGeneratePayload) => {
    const result = await api.generateQuestions(payload)
    await refreshAdmin()
    return result
  }

  const handleDiscoverSources = async () => {
    const result = await api.discoverSources()
    await refreshAdmin()
    return result
  }

  const handleHarvestSource = async (source: string, limit: number) => {
    const result = await api.harvestSource(source, limit)
    await refreshAdmin()
    return result
  }

  const handleMatchObservations = async () => {
    const result = await api.matchObservations()
    await refreshAdmin()
    return result
  }

  const handleRecalibrateExternalObservations = async () => {
    const result = await api.recalibrateFromExternalObservations()
    await refreshAdmin()
    return result
  }

  const handleApproveAnchor = async (anchorId: string) => {
    const result = await api.approveAnchor(anchorId)
    await refreshAdmin()
    return result
  }

  const handleRejectAnchor = async (anchorId: string) => {
    const result = await api.rejectAnchor(anchorId)
    await refreshAdmin()
    return result
  }

  const handleDeactivateQuestion = async (questionId: string) => {
    setLoading(true)
    try {
      await api.deactivateQuestion(questionId)
      await refreshAdmin()
      await refreshDashboard()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <span className="brand-mark">AC</span>
          <div>
            <strong>ASVAB Coach</strong>
            <span>Practice platform</span>
          </div>
        </div>
        <nav className="top-nav">
          <button type="button" className="nav-button" onClick={() => void navigateHome()}>
            <Home size={16} />
            <span>Home</span>
          </button>
          <button type="button" className="nav-button" onClick={() => void openReview()}>
            <ShieldCheck size={16} />
            <span>Review</span>
          </button>
          <button type="button" className="nav-button" onClick={() => void openAdmin()}>
            <LogIn size={16} />
            <span>Admin Giriş</span>
          </button>
        </nav>
      </header>

      {error ? (
        <div className="error-strip">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      ) : null}

      {loading ? (
        <div className="loading-strip">
          <LoaderCircle size={16} className="spin" />
          <span>Working...</span>
        </div>
      ) : null}

      <main className="main-shell">
        {view === 'home' ? (
          <HomePage
            stats={stats}
            sectionMemory={sectionMemory}
            onStart={handleStart}
            onOpenReview={() => void openReview()}
            onOpenAdmin={() => void openAdmin()}
            busy={loading}
          />
        ) : null}

        {view === 'study' && question && session ? (
          <StudyModePage
            mode={session.mode}
            question={question}
            questionStartedAt={questionStartedAt}
            answerFeedback={answerFeedback}
            busy={loading}
            onAnswer={handleAnswer}
            onNext={advanceToNextQuestion}
            onFinish={handleFinishSession}
          />
        ) : null}

        {view === 'cat' && question && session ? (
          <CatSimulationPage
            mode={session.mode}
            question={question}
            questionStartedAt={questionStartedAt}
            busy={loading}
            onAnswer={handleAnswer}
            onFinish={handleFinishSession}
          />
        ) : null}

        {view === 'results' && results ? (
          <ResultsPage
            results={results}
            onBackHome={() => void navigateHome()}
            onOpenReview={() => void openReview()}
          />
        ) : null}

        {view === 'review' ? (
          <ReviewMistakesPage
            sectionMemory={sectionMemory}
            mistakes={mistakes}
            onBackHome={() => void navigateHome()}
            onRefresh={async () => {
              const [memoryRows, reviewItems] = await Promise.all([api.fetchSectionMemory(), api.fetchMistakes()])
              setSectionMemory(memoryRows)
              setMistakes(reviewItems)
            }}
          />
        ) : null}

        {view === 'admin' ? (
          <AdminImportPage
            importLogs={importLogs}
            auditIssues={auditIssues}
            sectionSummary={sectionSummary}
            dashboardSummary={dashboardSummary}
            careerRequirements={careerRequirements}
            researchSummary={researchSummary}
            externalSources={externalSources}
            externalObservations={externalObservations}
            conceptAnchors={conceptAnchors}
            questionPreview={questionPreview}
            onBackHome={() => void navigateHome()}
            onRefresh={refreshAdmin}
            onRefreshQuestionPreview={refreshQuestionPreview}
            onImport={handleImport}
            onDedupe={handleDedupeQuestions}
            onRecalibrate={handleRecalibrateQuestions}
            onGenerate={handleGenerateQuestions}
            onDiscoverSources={handleDiscoverSources}
            onHarvestSource={handleHarvestSource}
            onMatchObservations={handleMatchObservations}
            onRecalibrateExternal={handleRecalibrateExternalObservations}
            onApproveAnchor={handleApproveAnchor}
            onRejectAnchor={handleRejectAnchor}
            onDeactivateQuestion={handleDeactivateQuestion}
          />
        ) : null}
      </main>
    </div>
  )
}

export default App

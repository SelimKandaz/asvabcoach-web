interface ExplanationPanelProps {
  explanation: string | null
  quickMethod: string | null
  wrongAnswerReason: string | null
  correctAnswer: string
}

export function ExplanationPanel({
  explanation,
  quickMethod,
  wrongAnswerReason,
  correctAnswer,
}: ExplanationPanelProps) {
  return (
    <aside className="explanation-panel">
      <div className="explanation-header">
        <span className="eyebrow">Review</span>
        <strong>{correctAnswer}</strong>
      </div>
      {explanation ? <p>{explanation}</p> : null}
      {wrongAnswerReason ? <p>{wrongAnswerReason}</p> : null}
      {quickMethod ? <p className="quick-method">{quickMethod}</p> : null}
    </aside>
  )
}


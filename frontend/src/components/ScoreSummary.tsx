interface ScoreSummaryProps {
  title: string
  value: string
  detail: string
}

export function ScoreSummary({ title, value, detail }: ScoreSummaryProps) {
  return (
    <article className="score-card">
      <span className="score-card-title">{title}</span>
      <strong className="score-card-value">{value}</strong>
      <span className="score-card-detail">{detail}</span>
    </article>
  )
}


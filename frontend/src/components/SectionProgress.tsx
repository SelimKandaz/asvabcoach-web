interface SectionProgressProps {
  label: string
  value: number
  max: number
}

export function SectionProgress({ label, value, max }: SectionProgressProps) {
  const ratio = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div className="section-progress">
      <div className="section-progress-row">
        <span>{label}</span>
        <span>
          {value}/{max}
        </span>
      </div>
      <div className="progress-track" aria-hidden="true">
        <div className="progress-value" style={{ width: `${ratio}%` }} />
      </div>
    </div>
  )
}


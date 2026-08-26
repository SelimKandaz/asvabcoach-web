import { ChoiceButton } from './ChoiceButton'

interface QuestionCardProps {
  questionText: string
  choices: Record<'A' | 'B' | 'C' | 'D', string>
  selectedAnswer: string | null
  correctAnswer?: string | null
  disabled?: boolean
  revealAnswer?: boolean
  figureSvg?: string | null
  figureAltText?: string | null
  assetPath?: string | null
  onSelect: (choice: 'A' | 'B' | 'C' | 'D') => void
}

export function QuestionCard({
  questionText,
  choices,
  selectedAnswer,
  correctAnswer,
  disabled = false,
  revealAnswer = false,
  figureSvg,
  figureAltText,
  assetPath,
  onSelect,
}: QuestionCardProps) {
  const choiceKeys: Array<'A' | 'B' | 'C' | 'D'> = ['A', 'B', 'C', 'D']
  const resolvedAssetSrc = assetPath
    ? `/api/question-assets/${encodeURI(assetPath.replace(/^\/+/, ''))}`
    : null

  const getState = (choice: 'A' | 'B' | 'C' | 'D') => {
    if (!revealAnswer) {
      if (selectedAnswer === choice) {
        return 'selected'
      }
      return disabled ? 'locked' : 'idle'
    }
    if (correctAnswer === choice) {
      return 'correct'
    }
    if (selectedAnswer === choice && correctAnswer !== choice) {
      return 'wrong'
    }
    return 'locked'
  }

  return (
    <section className="question-card">
      {figureSvg ? (
        <div
          className="question-figure"
          role={figureAltText ? 'img' : undefined}
          aria-label={figureAltText ?? undefined}
          dangerouslySetInnerHTML={{ __html: figureSvg }}
        />
      ) : resolvedAssetSrc ? (
        <div className="question-figure">
          <img src={resolvedAssetSrc} alt={figureAltText ?? questionText} />
        </div>
      ) : null}
      {figureAltText ? <p className="figure-caption">{figureAltText}</p> : null}
      <div className="question-stem">
        <p>{questionText}</p>
      </div>
      <div className="choice-grid">
        {choiceKeys.map((choice) => (
          <ChoiceButton
            key={choice}
            label={choice}
            disabled={disabled}
            state={getState(choice)}
            onClick={() => onSelect(choice)}
          >
            {choices[choice]}
          </ChoiceButton>
        ))}
      </div>
    </section>
  )
}

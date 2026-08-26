import type { ReactNode } from 'react'

type ChoiceState = 'idle' | 'selected' | 'correct' | 'wrong' | 'locked'

interface ChoiceButtonProps {
  label: string
  children: ReactNode
  disabled?: boolean
  state?: ChoiceState
  onClick?: () => void
}

export function ChoiceButton({
  label,
  children,
  disabled = false,
  state = 'idle',
  onClick,
}: ChoiceButtonProps) {
  return (
    <button
      type="button"
      className={`choice-button choice-${state}`}
      disabled={disabled}
      onClick={onClick}
    >
      <span className="choice-label">{label}</span>
      <span className="choice-text">{children}</span>
    </button>
  )
}


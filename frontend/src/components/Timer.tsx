import { useEffect, useState } from 'react'

interface TimerProps {
  startedAtMs: number
  paused?: boolean
}

export function Timer({ startedAtMs, paused = false }: TimerProps) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (paused) {
      return undefined
    }
    const interval = window.setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - startedAtMs) / 1000)))
    }, 250)
    return () => {
      window.clearInterval(interval)
    }
  }, [paused, startedAtMs])

  const minutes = String(Math.floor(elapsed / 60)).padStart(2, '0')
  const seconds = String(elapsed % 60).padStart(2, '0')

  return <span className="timer-readout">{minutes}:{seconds}</span>
}

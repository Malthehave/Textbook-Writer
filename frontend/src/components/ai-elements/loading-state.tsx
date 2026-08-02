import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useEffect, useState } from 'react'

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

function OrbitDots({ className }: { className?: string }) {
  return (
    <span className={cn('relative inline-flex size-3.5 items-center justify-center', className)}>
      <span className="absolute inset-0 animate-spin rounded-full border border-live/30 border-t-live" />
      <span className="size-1 rounded-full bg-live" />
    </span>
  )
}

export function LoadingState({
  label,
  active,
  onStop,
  className,
}: {
  label: string
  active: boolean
  onStop?: () => void
  className?: string
}) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!active) {
      setElapsed(0)
      return
    }
    const started = performance.now()
    const id = window.setInterval(() => {
      setElapsed((performance.now() - started) / 1000)
    }, 100)
    return () => window.clearInterval(id)
  }, [active, label])

  if (!active) return null

  return (
    <div
      className={cn(
        'flex items-center gap-2.5 rounded-[var(--radius-md)] bg-panel px-3 py-2 text-sm text-foreground',
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <OrbitDots />
      <span className="min-w-0 flex-1 truncate">
        <span className="text-foreground">{label}</span>
      </span>
      <span className="shrink-0 font-mono text-xs tabular-nums text-mist">
        {formatElapsed(elapsed)}
      </span>
      {onStop ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 shrink-0 px-2 text-xs"
          onClick={onStop}
        >
          Stop
        </Button>
      ) : null}
    </div>
  )
}

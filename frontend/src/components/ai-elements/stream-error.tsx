import { AlertCircleIcon, XIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function StreamError({
  title,
  detail,
  onDismiss,
  className,
}: {
  title: string
  detail: string
  onDismiss?: () => void
  className?: string
}) {
  return (
    <div
      role="alert"
      className={cn(
        'flex gap-3 rounded-[var(--radius-md)] bg-danger/10 px-3 py-2.5 text-sm text-foreground',
        className,
      )}
    >
      <AlertCircleIcon className="mt-0.5 size-4 shrink-0 text-danger" />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-medium text-danger">{title}</p>
        <p className="whitespace-pre-wrap text-xs text-foreground/80">{detail}</p>
      </div>
      {onDismiss ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="size-7 shrink-0 text-danger hover:bg-danger/10 hover:text-danger"
          onClick={onDismiss}
          aria-label="Dismiss error"
        >
          <XIcon className="size-3.5" />
        </Button>
      ) : null}
    </div>
  )
}

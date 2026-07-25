import { BotIcon, BrainIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/utils'
import { specialistLabel, type SpecialistRun } from '@/specialists'

function shortText(value: unknown, max = 600): string {
  const text =
    typeof value === 'string' ? value : value === undefined ? '' : JSON.stringify(value, null, 2)
  if (text.length <= max) return text
  return `${text.slice(0, max)}\n…`
}

export function SpecialistPanel({
  toolName,
  state,
  output,
  run,
  defaultOpen = false,
}: {
  toolName: string
  state: string
  input?: unknown
  output?: unknown
  run?: SpecialistRun
  defaultOpen?: boolean
}) {
  const failed =
    state === 'output-error' || run?.status === 'failed' || Boolean(run?.errorText)
  const running =
    !failed &&
    (state === 'input-available' || state === 'input-streaming' || run?.status === 'running')
  const title = specialistLabel(toolName)
  const errorText =
    run?.errorText ||
    (typeof output === 'string' && output.toLowerCase().includes('error occurred')
      ? output
      : undefined)
  const statusLabel = run?.label
  const hasBody =
    Boolean(errorText) || Boolean(run?.reasoning) || Boolean(run?.text) || Boolean(output)

  return (
    <Collapsible
      defaultOpen={defaultOpen || failed || running}
      className={cn(
        'group mb-3 w-full rounded-xl bg-muted/40',
        failed && 'bg-destructive/10',
      )}
    >
      <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left">
        <div className="flex min-w-0 items-center gap-2">
          <BotIcon className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate text-sm font-medium">{title}</span>
          <Badge
            variant="secondary"
            className={cn(
              'border-0',
              running && 'text-foreground',
              failed && 'bg-destructive/15 text-destructive',
            )}
          >
            {failed ? (
              'Failed'
            ) : running ? (
              <span className="inline-flex items-center gap-1.5">
                <Spinner className="size-3" />
                {statusLabel || 'Running'}
              </span>
            ) : (
              'Done'
            )}
          </Badge>
        </div>
      </CollapsibleTrigger>
      {hasBody ? (
        <CollapsibleContent className="space-y-2 px-3 pb-3">
          {errorText ? (
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-background/70 p-2 font-mono text-[11px] text-destructive">
              {errorText}
            </pre>
          ) : null}
          {run?.reasoning ? (
            <div className="space-y-1">
              <p className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <BrainIcon className="size-3" />
                Reasoning
              </p>
              <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded-lg bg-background/70 p-2 font-mono text-[11px] text-muted-foreground">
                {shortText(run.reasoning, 1200)}
              </pre>
            </div>
          ) : null}
          {run?.text ? (
            <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded-lg bg-background/70 p-2 font-mono text-[11px] text-muted-foreground">
              {shortText(run.text, 1200)}
            </pre>
          ) : null}
          {output !== undefined && output !== '' && !errorText ? (
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-background/70 p-2 font-mono text-[11px]">
              {shortText(output, 800)}
            </pre>
          ) : null}
        </CollapsibleContent>
      ) : null}
    </Collapsible>
  )
}

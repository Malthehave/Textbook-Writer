import { useEffect, useState } from 'react'
import { LoaderCircleIcon } from 'lucide-react'
import { MessageResponse } from '@/components/ai-elements/message'
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from '@/components/ai-elements/reasoning'
import { cn } from '@/lib/utils'
import { isSpecialistTool, specialistLabel } from '@/specialists'

function formatPayload(value: unknown): string {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value
  if (Array.isArray(value) && value.length === 0) return ''
  if (
    typeof value === 'object' &&
    !Array.isArray(value) &&
    Object.keys(value).length === 0
  ) {
    return ''
  }
  if (
    typeof value === 'object' &&
    !Array.isArray(value) &&
    Object.keys(value).length === 1 &&
    typeof (value as { input?: unknown }).input === 'string'
  ) {
    return (value as { input: string }).input
  }
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function previewLine(value: unknown, max = 72): string {
  const text = formatPayload(value).replace(/\s+/g, ' ').trim()
  if (!text) return ''
  if (text.length <= max) return text
  return `${text.slice(0, max)}…`
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="transition-transform duration-150"
      style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  )
}

function PayloadBlock({
  label,
  text,
  scrollable = true,
}: {
  label: string
  text: string
  scrollable?: boolean
}) {
  if (!text) return null
  return (
    <div className="min-w-0 space-y-1">
      <div className="text-xs font-medium tracking-wide text-mist uppercase">
        {label}
      </div>
      <pre
        className={cn(
          'm-0 max-w-full min-w-0 overflow-x-auto rounded-[var(--radius-sm)] bg-panel px-2.5 py-2 font-mono text-xs leading-relaxed break-all whitespace-pre-wrap text-mist',
          scrollable && 'max-h-80 overflow-y-auto',
        )}
      >
        {text}
      </pre>
    </div>
  )
}

export type SubagentTranscriptEvent = {
  outer_tool_call_id: string
  agent_name: string
  event_type:
    | 'assistant-delta'
    | 'reasoning-delta'
    | 'tool-called'
    | 'tool-output'
  payload: {
    text?: string
    tool_call_id?: string
    tool_name?: string
    input?: unknown
    output?: unknown
  }
}

type TranscriptEntry =
  | {
      kind: 'message'
      agentName: string
      text: string
    }
  | {
      kind: 'reasoning'
      agentName: string
      text: string
    }
  | {
      kind: 'tool'
      agentName: string
      toolCallId: string
      toolName: string
      input?: unknown
      output?: unknown
    }

function transcriptEntries(
  events: SubagentTranscriptEvent[],
): TranscriptEntry[] {
  const entries: TranscriptEntry[] = []
  const tools = new Map<string, Extract<TranscriptEntry, { kind: 'tool' }>>()
  for (const event of events) {
    if (
      event.event_type === 'assistant-delta' ||
      event.event_type === 'reasoning-delta'
    ) {
      const kind =
        event.event_type === 'reasoning-delta' ? 'reasoning' : 'message'
      const previous = entries.at(-1)
      if (
        previous &&
        previous.kind === kind &&
        previous.agentName === event.agent_name
      ) {
        previous.text += event.payload.text ?? ''
      } else {
        entries.push({
          kind,
          agentName: event.agent_name,
          text: event.payload.text ?? '',
        })
      }
      continue
    }
    const toolCallId = event.payload.tool_call_id ?? ''
    if (event.event_type === 'tool-called') {
      const entry: Extract<TranscriptEntry, { kind: 'tool' }> = {
        kind: 'tool',
        agentName: event.agent_name,
        toolCallId,
        toolName: event.payload.tool_name ?? 'tool',
        input: event.payload.input,
      }
      entries.push(entry)
      tools.set(toolCallId, entry)
      continue
    }
    const tool = tools.get(toolCallId)
    if (tool) tool.output = event.payload.output
  }
  return entries
}

export function TaskRow({
  toolName,
  state,
  input,
  output,
  errorText,
  transcript = [],
  defaultOpen = false,
}: {
  toolName: string
  state: string
  input?: unknown
  output?: unknown
  errorText?: string
  transcript?: SubagentTranscriptEvent[]
  defaultOpen?: boolean
}) {
  const failed = state === 'output-error'
  const running =
    !failed && (state === 'input-available' || state === 'input-streaming')
  const title = specialistLabel(toolName)
  const chip = failed ? 'Failed' : running ? 'Running…' : 'Done'
  const inputText = formatPayload(input)
  const outputText = errorText?.trim() || formatPayload(output)
  const headerPreview = previewLine(errorText || output || input)
  const [open, setOpen] = useState(
    defaultOpen || failed || (running && isSpecialistTool(toolName)),
  )
  const entries = transcriptEntries(transcript)

  useEffect(() => {
    if (running && transcript.length > 0) setOpen(true)
  }, [running, transcript.length])

  return (
    <div className="w-full min-w-0 max-w-full">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="group/row flex h-7 w-full min-w-0 items-center gap-2 rounded-[var(--radius-sm)] px-[3px] text-left transition-colors duration-100 hover:bg-panel"
      >
        <span className="relative flex size-4 shrink-0 items-center justify-center text-mist">
          {running ? (
            <LoaderCircleIcon className="size-3.5 animate-spin text-live" />
          ) : (
            <>
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className={cn(
                  'transition-opacity duration-100 group-hover/row:opacity-0',
                  open && 'opacity-0',
                )}
              >
                <path d="M12 8V4H8" />
                <rect width="16" height="12" x="4" y="8" rx="2" />
                <path d="M2 14h2" />
                <path d="M20 14h2" />
                <path d="M15 13v2" />
                <path d="M9 13v2" />
              </svg>
              <span
                className={cn(
                  'absolute group-hover/row:opacity-100',
                  open ? 'opacity-100' : 'opacity-0',
                )}
              >
                <Chevron open={open} />
              </span>
            </>
          )}
        </span>
        <span
          className={cn(
            'min-w-0 shrink truncate text-xs font-medium',
            failed ? 'text-danger' : 'text-foreground',
          )}
        >
          {title}
        </span>
        <span
          className={cn(
            'inline-flex h-5 min-w-0 flex-1 items-center truncate rounded-[var(--radius-sm)] bg-panel px-1.5 font-mono text-xs text-mist',
            failed && 'text-danger',
          )}
          title={headerPreview || chip}
        >
          {headerPreview || chip}
        </span>
      </button>

      <div
        className="grid min-w-0 transition-[grid-template-rows,opacity] duration-300"
        style={{
          gridTemplateRows: open ? '1fr' : '0fr',
          opacity: open ? 1 : 0,
          transitionTimingFunction: 'cubic-bezier(0.23, 1, 0.32, 1)',
        }}
      >
        <div className="min-h-0 min-w-0 overflow-hidden">
          <div className="mt-0.5 mb-1 ml-2 flex min-w-0 flex-col gap-2 border-l border-border py-1.5 pl-3.5">
            {!inputText && !outputText && entries.length === 0 ? (
              <span className="text-xs text-mist">
                {running ? 'Working…' : 'Completed'}
              </span>
            ) : (
              <>
                {entries.length > 0 ? (
                  <div className="min-w-0 space-y-1.5">
                    {entries.map((entry, index) => {
                      if (entry.kind === 'reasoning') {
                        return (
                          <Reasoning
                            key={`reasoning-${index}`}
                            className="w-full"
                            isStreaming={running && index === entries.length - 1}
                          >
                            <ReasoningTrigger />
                            <ReasoningContent>{entry.text}</ReasoningContent>
                          </Reasoning>
                        )
                      }
                      if (entry.kind === 'message') {
                        return (
                          <MessageResponse key={`message-${index}`}>
                            {entry.text}
                          </MessageResponse>
                        )
                      }
                      return (
                        <TaskRow
                          key={`tool-${entry.toolCallId || index}`}
                          toolName={entry.toolName}
                          state={
                            entry.output === undefined
                              ? 'input-available'
                              : 'output-available'
                          }
                          input={entry.input}
                          output={entry.output}
                        />
                      )
                    })}
                  </div>
                ) : null}
                <PayloadBlock
                  label="Input"
                  text={inputText}
                  scrollable={false}
                />
                <PayloadBlock
                  label={failed || errorText ? 'Error' : 'Output'}
                  text={outputText}
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

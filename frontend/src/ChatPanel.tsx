import { useEffect, useMemo, useState } from 'react'
import { useChat } from '@ai-sdk/react'
import {
  DefaultChatTransport,
  type DynamicToolUIPart,
  type ToolUIPart,
  type UIMessage,
} from 'ai'
import { BookOpenIcon } from 'lucide-react'
import {
  BookProgressPanel,
  type BookProgress,
} from '@/components/ai-elements/book-progress'

type BookCostTotals = {
  requests: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_input_tokens: number
  cache_write_tokens: number
  cost_usd: number
  unpriced_requests: number
}

type BookCostUpdate = {
  currency: string
  pricing_source: string
  totals: BookCostTotals
  by_model?: Record<string, BookCostTotals>
  last_call?: {
    agent: string
    model: string
    cost_usd: number | null
    priced: boolean
  } | null
}

function formatUsd(amount: number): string {
  if (amount >= 1) return `$${amount.toFixed(2)}`
  if (amount >= 0.01) return `$${amount.toFixed(3)}`
  return `$${amount.toFixed(4)}`
}

function formatTokens(total: number): string {
  if (total >= 1_000_000) return `${(total / 1_000_000).toFixed(1)}M tok`
  if (total >= 1_000) return `${(total / 1_000).toFixed(1)}k tok`
  return `${total} tok`
}

function isBookCostUpdate(value: unknown): value is BookCostUpdate {
  if (!value || typeof value !== 'object') return false
  const totals = (value as BookCostUpdate).totals
  return (
    !!totals &&
    typeof totals === 'object' &&
    typeof totals.cost_usd === 'number' &&
    typeof totals.total_tokens === 'number'
  )
}
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation'
import { LoadingState } from '@/components/ai-elements/loading-state'
import {
  Message,
  MessageContent,
  MessageResponse,
} from '@/components/ai-elements/message'
import {
  PromptInput,
  type PromptInputMessage,
  PromptInputSubmit,
  PromptInputTextarea,
} from '@/components/ai-elements/prompt-input'
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from '@/components/ai-elements/reasoning'
import { StreamError } from '@/components/ai-elements/stream-error'
import {
  TaskRow,
  type SubagentTranscriptEvent,
} from '@/components/ai-elements/task-row'
import { Skeleton } from '@/components/ui/skeleton'

function partToolName(part: DynamicToolUIPart | ToolUIPart): string {
  if (part.type === 'dynamic-tool') return part.toolName
  return part.type.slice('tool-'.length)
}

function isSubagentEventPart(
  part: unknown,
): part is { type: 'data-subagent-event'; data: SubagentTranscriptEvent } {
  if (!part || typeof part !== 'object') return false
  const candidate = part as {
    type?: unknown
    data?: { outer_tool_call_id?: unknown; event_type?: unknown }
  }
  return (
    candidate.type === 'data-subagent-event' &&
    typeof candidate.data?.outer_tool_call_id === 'string' &&
    typeof candidate.data?.event_type === 'string'
  )
}

function isBookProgress(value: unknown): value is BookProgress {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<BookProgress>
  return (
    typeof candidate.status === 'string' &&
    Array.isArray(candidate.chapters) &&
    typeof candidate.milestones?.completed === 'number' &&
    typeof candidate.milestones?.total === 'number'
  )
}

function inputText(input: unknown): string {
  if (typeof input === 'string') return input
  try {
    return JSON.stringify(input)
  } catch {
    return ''
  }
}

function chapterLabel(input: unknown): string {
  const match = inputText(input).match(/\bch(?:apter)?[\s_-]*(\d+)\b/i)
  return match ? `Chapter ${match[1]}` : 'the chapter'
}

function toolActivity(toolName: string, input: unknown): string {
  const text = inputText(input)
  const chapter = chapterLabel(input)
  if (toolName === 'research-architect') return 'Researching and grounding the scope'
  if (toolName === 'curriculum-architect') return 'Planning the textbook curriculum'
  if (toolName === 'chapter-writer') {
    return /\b(revis|rewrit|fix|update)\w*/i.test(text)
      ? `Revising ${chapter}`
      : `Writing ${chapter}`
  }
  if (toolName === 'chapter-reviewer') return `Reviewing ${chapter}`
  if (toolName === 'independent-verifier') {
    return `Solving ${chapter} exercises independently`
  }
  if (toolName === 'solution-comparator') {
    return `Checking ${chapter} exercise answers`
  }
  if (toolName === 'html-diagram-author') return `Updating ${chapter} diagram`
  if (toolName === 'validate-production-artifact') return 'Validating the latest artifact'
  if (toolName === 'build-textbook-pdf') return 'Compiling and measuring the PDF'
  return `Running ${toolName.replaceAll('-', ' ')}`
}

function currentBookActivity(messages: UIMessage[]): string | null {
  const transcriptEvents: SubagentTranscriptEvent[] = []
  const parentInputs = new Map<string, unknown>()
  for (const message of messages) {
    for (const part of message.parts as unknown[]) {
      if (isSubagentEventPart(part)) {
        transcriptEvents.push(part.data)
        continue
      }
      if (!part || typeof part !== 'object') continue
      const tool = part as { toolCallId?: unknown; input?: unknown }
      if (typeof tool.toolCallId === 'string' && 'input' in tool) {
        parentInputs.set(tool.toolCallId, tool.input)
      }
    }
  }

  const finishedNestedCalls = new Set(
    transcriptEvents
      .filter((event) => event.event_type === 'tool-output')
      .map((event) => event.payload.tool_call_id)
      .filter((callId): callId is string => typeof callId === 'string'),
  )
  for (const event of transcriptEvents.toReversed()) {
    if (
      event.event_type === 'tool-called' &&
      event.payload.tool_call_id &&
      event.payload.tool_name &&
      !finishedNestedCalls.has(event.payload.tool_call_id)
    ) {
      return toolActivity(
        event.payload.tool_name,
        event.payload.input ?? parentInputs.get(event.outer_tool_call_id),
      )
    }
  }

  for (const message of messages.toReversed()) {
    for (const part of [...message.parts].reverse()) {
      if (part.type !== 'dynamic-tool' && !part.type.startsWith('tool-')) continue
      const tool = part as DynamicToolUIPart | ToolUIPart
      if (tool.state !== 'input-available' && tool.state !== 'input-streaming') {
        continue
      }
      return toolActivity(
        partToolName(tool),
        'input' in tool ? tool.input : undefined,
      )
    }
  }
  return null
}

function humanizeChatError(message: string): { title: string; detail: string } {
  const lower = message.toLowerCase()
  if (lower.includes('no tool invocation found')) {
    return {
      title: 'Stream protocol glitch',
      detail:
        'The UI got a tool result before its matching tool start. Send another message to continue.',
    }
  }
  if (lower.includes('network') || lower.includes('failed to fetch')) {
    return {
      title: 'Connection lost',
      detail:
        'The browser lost the stream (proxy timeout, API reload, or network drop). Check tool rows above for partial progress, then send another message.',
    }
  }
  if (lower.includes('run failed') || lower.includes('invalid_request_error')) {
    return {
      title: 'Agent run failed',
      detail: message,
    }
  }
  return {
    title: 'Something went wrong',
    detail: message,
  }
}

function MessageParts({
  message,
  isLastMessage,
  isStreaming,
}: {
  message: UIMessage
  isLastMessage: boolean
  isStreaming: boolean
}) {
  const reasoningParts = message.parts.filter((part) => part.type === 'reasoning')
  const reasoningText = reasoningParts.map((part) => part.text).join('\n\n')
  const lastPart = message.parts.at(-1)
  const isReasoningStreaming =
    isLastMessage && isStreaming && lastPart?.type === 'reasoning'
  const transcriptByCall = new Map<string, SubagentTranscriptEvent[]>()
  for (const part of message.parts as unknown[]) {
    if (!isSubagentEventPart(part)) continue
    const callId = part.data.outer_tool_call_id
    const events = transcriptByCall.get(callId) ?? []
    events.push(part.data)
    transcriptByCall.set(callId, events)
  }
  return (
    <>
      {reasoningParts.length > 0 ? (
        <Reasoning className="w-full" isStreaming={isReasoningStreaming}>
          <ReasoningTrigger />
          <ReasoningContent>{reasoningText}</ReasoningContent>
        </Reasoning>
      ) : null}

      {message.parts.map((part, index) => {
        const key = `${message.id}-${index}`
        if (part.type === 'text') {
          return <MessageResponse key={key}>{part.text}</MessageResponse>
        }
        if (part.type === 'reasoning') return null
        if (part.type === 'dynamic-tool' || part.type.startsWith('tool-')) {
          const toolPart = part as DynamicToolUIPart | ToolUIPart
          const toolName = partToolName(toolPart)
          return (
            <div key={key} className="mb-1.5 min-w-0 max-w-full">
              <TaskRow
                toolName={toolName}
                state={toolPart.state}
                input={'input' in toolPart ? toolPart.input : undefined}
                output={'output' in toolPart ? toolPart.output : undefined}
                errorText={
                  'errorText' in toolPart ? toolPart.errorText : undefined
                }
                transcript={transcriptByCall.get(toolPart.toolCallId) ?? []}
                defaultOpen={toolPart.state === 'output-error'}
              />
            </div>
          )
        }
        return null
      })}
    </>
  )
}

export function ChatPanel({
  sessionId,
  sessionTitle,
  onActivity,
}: {
  sessionId: string
  sessionTitle: string
  onActivity: () => void
}) {
  const [ready, setReady] = useState(false)
  const [history, setHistory] = useState<UIMessage[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setReady(false)
    setLoadError(null)
    fetch(`/api/sessions/${sessionId}/messages`)
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text())
        return res.json() as Promise<UIMessage[]>
      })
      .then((messages) => {
        if (!cancelled) {
          setHistory(messages)
          setReady(true)
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setLoadError(err.message)
          setHistory([])
          setReady(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [sessionId])

  if (!ready) {
    return (
      <div className="flex h-full flex-col gap-3 p-5">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-4 w-28" />
        <Skeleton className="mt-4 h-24 w-full rounded-[var(--radius-lg)]" />
        <Skeleton className="h-16 w-3/4 rounded-[var(--radius-lg)]" />
      </div>
    )
  }

  return (
    <ChatPanelReady
      sessionId={sessionId}
      sessionTitle={sessionTitle}
      initialMessages={history}
      loadError={loadError}
      onActivity={onActivity}
    />
  )
}

function ChatPanelReady({
  sessionId,
  sessionTitle,
  initialMessages,
  loadError,
  onActivity,
}: {
  sessionId: string
  sessionTitle: string
  initialMessages: UIMessage[]
  loadError: string | null
  onActivity: () => void
}) {
  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: '/api/chat',
      }),
    [],
  )
  const [input, setInput] = useState('')
  const [bookCost, setBookCost] = useState<BookCostUpdate | null>(null)
  const [bookProgress, setBookProgress] = useState<BookProgress | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(`/api/sessions/${sessionId}/usage`)
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text())
        return res.json() as Promise<unknown>
      })
      .then((payload) => {
        if (!cancelled && isBookCostUpdate(payload)) setBookCost(payload)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [sessionId])

  const { messages, sendMessage, status, error, clearError, stop } = useChat({
    id: sessionId,
    messages: initialMessages,
    transport,
    onData: (dataPart) => {
      if (dataPart.type === 'data-book-cost' && isBookCostUpdate(dataPart.data)) {
        setBookCost(dataPart.data)
      }
    },
    onError: () => {
      onActivity()
    },
    onFinish: () => {
      onActivity()
    },
  })

  const isStreaming = status === 'streaming'
  const busy = status === 'streaming' || status === 'submitted'
  const chatError = error ? humanizeChatError(error.message) : null
  const stickyError = loadError
    ? { title: 'Could not load history', detail: loadError }
    : chatError

  useEffect(() => {
    let cancelled = false
    const refresh = () => {
      fetch(`/api/sessions/${sessionId}/progress`)
        .then(async (res) => {
          if (!res.ok) throw new Error(await res.text())
          return res.json() as Promise<unknown>
        })
        .then((payload) => {
          if (!cancelled && isBookProgress(payload)) setBookProgress(payload)
        })
        .catch(() => undefined)
    }
    refresh()
    if (!busy) {
      return () => {
        cancelled = true
      }
    }
    const interval = window.setInterval(refresh, 1500)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [busy, sessionId])

  const currentActivity = useMemo(
    () => currentBookActivity(messages) ?? (busy ? 'Manager coordinating next stage' : null),
    [busy, messages],
  )

  const lastMessage = messages.at(-1)
  const waitingForFirstToken =
    busy &&
    (!lastMessage ||
      lastMessage.role !== 'assistant' ||
      lastMessage.parts.length === 0)

  function handleSubmit(message: PromptInputMessage) {
    if (!message.text.trim() || busy) return
    clearError()
    void sendMessage({ text: message.text }).then(() => onActivity())
    setInput('')
  }

  const statusLabel =
    status === 'submitted'
      ? 'Waiting for the manager to start…'
      : waitingForFirstToken
        ? 'Manager starting…'
        : 'Manager working…'

  const costLabel =
    bookCost == null
      ? null
      : bookCost.totals.requests === 0
        ? 'Cost $0.00'
        : `${formatUsd(bookCost.totals.cost_usd)} · ${formatTokens(bookCost.totals.total_tokens)}`

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-start justify-between gap-3 px-5 pb-2 pt-4">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium tracking-tight">{sessionTitle}</div>
          <div className="text-xs text-mist">Manager conversation</div>
        </div>
        {costLabel ? (
          <div
            className="shrink-0 rounded-[var(--radius-md)] bg-panel px-2 py-1 font-mono text-xs tabular-nums text-mist"
            title={
              bookCost?.last_call
                ? `Last: ${bookCost.last_call.agent} · ${bookCost.last_call.model}`
                : 'Estimated OpenAI API cost for this book'
            }
          >
            {costLabel}
          </div>
        ) : null}
      </header>

      <BookProgressPanel progress={bookProgress} activity={currentActivity} />

      <Conversation className="min-h-0">
        <ConversationContent className="gap-5 px-5 py-3">
          {messages.length === 0 ? (
            <ConversationEmptyState
              className="mx-auto max-w-md"
              icon={<BookOpenIcon className="size-9" />}
              title="What should this textbook cover?"
              description="Describe the subject, your level, and any goals. The manager will shape a brief, then research, write, verify, and publish."
            />
          ) : (
            messages.map((message, index) => {
              const isLast = index === messages.length - 1
              const emptyAssistant =
                message.role === 'assistant' &&
                message.parts.length === 0 &&
                isLast &&
                busy
              return (
                <Message from={message.role} key={message.id}>
                  <MessageContent>
                    {emptyAssistant ? (
                      <p className="text-sm text-mist">Starting response…</p>
                    ) : (
                      <MessageParts
                        message={message}
                        isLastMessage={isLast}
                        isStreaming={isStreaming}
                      />
                    )}
                  </MessageContent>
                </Message>
              )
            })
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <div className="shrink-0 space-y-2 border-t border-border/70 bg-surface/90 px-4 pb-4 pt-3 backdrop-blur-sm">
        <LoadingState
          active={busy}
          label={statusLabel}
          onStop={() => {
            stop()
          }}
        />

        {stickyError ? (
          <StreamError
            title={stickyError.title}
            detail={
              busy
                ? stickyError.detail
                : `${stickyError.detail}\n\nThe run has stopped. Review failed tools above, then send another message.`
            }
            onDismiss={error ? () => clearError() : undefined}
          />
        ) : null}

        <PromptInput onSubmit={handleSubmit} className="relative w-full">
          <PromptInputTextarea
            value={input}
            onChange={(event) => setInput(event.currentTarget.value)}
            placeholder="Ask the manager to build a textbook…"
            className="min-h-12 pr-12"
            disabled={busy}
          />
          <PromptInputSubmit
            status={status}
            disabled={!input.trim() || busy}
            className="absolute right-1 bottom-1"
          />
        </PromptInput>
      </div>
    </div>
  )
}

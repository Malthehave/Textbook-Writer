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
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation'
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
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from '@/components/ai-elements/tool'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { SpecialistPanel } from '@/SpecialistPanel'
import {
  applySpecialistEvent,
  isSpecialistTool,
  type SpecialistDataEvent,
  type SpecialistRun,
} from '@/specialists'

function partToolName(part: DynamicToolUIPart | ToolUIPart): string {
  if (part.type === 'dynamic-tool') return part.toolName
  return part.type.slice('tool-'.length)
}

function humanizeChatError(message: string): { title: string; detail: string } {
  const lower = message.toLowerCase()
  if (lower.includes('no tool invocation found')) {
    return {
      title: 'Stream protocol glitch',
      detail:
        'The UI got a tool result before its matching tool start (fixed in the API stream mapper). Start a new message; if it repeats, grab /api/sessions/<id>/debug.',
    }
  }
  if (lower.includes('network') || lower.includes('failed to fetch')) {
    return {
      title: 'Connection lost',
      detail:
        'The browser lost the stream (proxy timeout, API reload, or network drop). The run is not still generating — check tool panels above for partial progress, then send another message to continue.',
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
  specialistRuns,
}: {
  message: UIMessage
  isLastMessage: boolean
  isStreaming: boolean
  specialistRuns: Record<string, SpecialistRun>
}) {
  const reasoningParts = message.parts.filter((part) => part.type === 'reasoning')
  const reasoningText = reasoningParts.map((part) => part.text).join('\n\n')
  const lastPart = message.parts.at(-1)
  const isReasoningStreaming =
    isLastMessage && isStreaming && lastPart?.type === 'reasoning'

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
        if (part.type === 'reasoning') {
          return null
        }
        if (part.type === 'dynamic-tool' || part.type.startsWith('tool-')) {
          const toolPart = part as DynamicToolUIPart | ToolUIPart
          const toolName = partToolName(toolPart)
          const toolCallId = toolPart.toolCallId

          if (isSpecialistTool(toolName)) {
            return (
              <SpecialistPanel
                key={key}
                toolName={toolName}
                state={toolPart.state}
                output={'output' in toolPart ? toolPart.output : undefined}
                run={specialistRuns[toolCallId]}
                defaultOpen={toolPart.state !== 'output-available'}
              />
            )
          }

          if (part.type === 'dynamic-tool') {
            const dynamicPart = part as DynamicToolUIPart
            return (
              <Tool key={key} className="mb-3 border-0 bg-muted/50 shadow-none">
                <ToolHeader
                  type="dynamic-tool"
                  state={dynamicPart.state}
                  toolName={dynamicPart.toolName}
                />
                <ToolContent>
                  {'input' in dynamicPart ? <ToolInput input={dynamicPart.input} /> : null}
                  <ToolOutput
                    output={'output' in dynamicPart ? dynamicPart.output : undefined}
                    errorText={'errorText' in dynamicPart ? dynamicPart.errorText : undefined}
                  />
                </ToolContent>
              </Tool>
            )
          }

          const typedPart = part as ToolUIPart
          return (
            <Tool key={key} className="mb-3 border-0 bg-muted/50 shadow-none">
              <ToolHeader type={typedPart.type} state={typedPart.state} />
              <ToolContent>
                {'input' in typedPart ? <ToolInput input={typedPart.input} /> : null}
                <ToolOutput
                  output={'output' in typedPart ? typedPart.output : undefined}
                  errorText={'errorText' in typedPart ? typedPart.errorText : undefined}
                />
              </ToolContent>
            </Tool>
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
        <Skeleton className="mt-4 h-24 w-full rounded-xl" />
        <Skeleton className="h-16 w-3/4 rounded-xl" />
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
  const [specialistRuns, setSpecialistRuns] = useState<Record<string, SpecialistRun>>({})
  const [runLabel, setRunLabel] = useState<string | null>(null)

  const { messages, sendMessage, status, error, clearError, stop } = useChat({
    id: sessionId,
    messages: initialMessages,
    transport,
    onData: (dataPart) => {
      if (dataPart.type === 'data-run-status') {
        const label = (dataPart.data as { label?: string } | undefined)?.label
        if (label) setRunLabel(label)
        return
      }
      if (dataPart.type !== 'data-specialist') return
      const event = dataPart.data as SpecialistDataEvent
      if (!event?.parentToolCallId) return
      setSpecialistRuns((current) => applySpecialistEvent(current, event))
    },
  })

  const isStreaming = status === 'streaming'
  const busy = status === 'streaming' || status === 'submitted'
  const chatError = error ? humanizeChatError(error.message) : null

  function handleSubmit(message: PromptInputMessage) {
    if (!message.text.trim() || busy) return
    setRunLabel('Sending…')
    clearError()
    sendMessage({ text: message.text }).then(() => onActivity())
    setInput('')
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="px-5 pb-1 pt-4">
        <div className="truncate text-sm font-medium">{sessionTitle}</div>
        <div className="text-xs text-muted-foreground">Manager conversation</div>
      </div>

      {busy ? (
        <div className="mx-4 mt-3 flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 text-sm text-foreground">
          <Spinner className="size-3.5" />
          <span className="min-w-0 flex-1 truncate">
            {status === 'submitted'
              ? 'Waiting for the manager to start…'
              : runLabel || 'Manager working…'}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 shrink-0 px-2 text-xs"
            onClick={() => stop()}
          >
            Stop
          </Button>
        </div>
      ) : null}

      {loadError || chatError ? (
        <div className="px-4 pt-3">
          <Alert variant="destructive" className="border-0 bg-destructive/10 shadow-none">
            <AlertTitle>{loadError ? 'Could not load history' : chatError?.title}</AlertTitle>
            <AlertDescription className="mt-1 space-y-2">
              <p className="whitespace-pre-wrap">{loadError || chatError?.detail}</p>
              {!busy ? (
                <p className="text-xs text-destructive/80">
                  The run has stopped. Review failed tools above, then send another message.
                </p>
              ) : null}
              {error ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 border-destructive/30 bg-background/60"
                  onClick={() => clearError()}
                >
                  Dismiss
                </Button>
              ) : null}
            </AlertDescription>
          </Alert>
        </div>
      ) : null}

      <Conversation className="min-h-0">
        <ConversationContent className="gap-6 px-5 py-4">
          {messages.length === 0 ? (
            <ConversationEmptyState
              icon={<BookOpenIcon className="size-10" />}
              title="What should this textbook cover?"
              description="Describe the subject, your level, and any goals. The manager will shape a brief, then research, write, verify, and publish."
            />
          ) : (
            messages.map((message, index) => (
              <Message from={message.role} key={message.id}>
                <MessageContent>
                  <MessageParts
                    message={message}
                    isLastMessage={index === messages.length - 1}
                    isStreaming={isStreaming}
                    specialistRuns={specialistRuns}
                  />
                </MessageContent>
              </Message>
            ))
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <div className="px-4 pb-4 pt-1">
        <PromptInput onSubmit={handleSubmit} className="relative w-full">
          <PromptInputTextarea
            value={input}
            onChange={(event) => setInput(event.currentTarget.value)}
            placeholder="Ask the manager to build a textbook…"
            className="pr-12"
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

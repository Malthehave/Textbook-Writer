import { useEffect, useMemo, useState } from 'react'
import { useChat } from '@ai-sdk/react'
import {
  DefaultChatTransport,
  type DynamicToolUIPart,
  type ToolUIPart,
  type UIMessage,
} from 'ai'
import { UserRoundIcon } from 'lucide-react'
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
import { TaskRow } from '@/components/ai-elements/task-row'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

const PERSONA_CHAT_ID = 'learner-persona-interview'

type PersonaPayload = {
  markdown: string
  path: string
  updated_at: number | null
}

function partToolName(part: DynamicToolUIPart | ToolUIPart): string {
  if (part.type === 'dynamic-tool') return part.toolName
  return part.type.slice('tool-'.length)
}

function InterviewMessageParts({
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
          return (
            <div key={key} className="mb-1.5 min-w-0 max-w-full">
              <TaskRow
                toolName={partToolName(toolPart)}
                state={toolPart.state}
                input={'input' in toolPart ? toolPart.input : undefined}
                output={'output' in toolPart ? toolPart.output : undefined}
                errorText={
                  'errorText' in toolPart ? toolPart.errorText : undefined
                }
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

function PersonaInterviewReady({
  initialMessages,
  onPersonaMayHaveChanged,
}: {
  initialMessages: UIMessage[]
  onPersonaMayHaveChanged: () => void
}) {
  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: '/api/persona/chat',
      }),
    [],
  )
  const [input, setInput] = useState('')
  const { messages, sendMessage, status, error, clearError, stop } = useChat({
    id: PERSONA_CHAT_ID,
    messages: initialMessages,
    transport,
    onFinish: () => onPersonaMayHaveChanged(),
  })
  const busy = status === 'streaming' || status === 'submitted'
  const isStreaming = status === 'streaming'

  function handleSubmit(message: PromptInputMessage) {
    if (!message.text.trim() || busy) return
    clearError()
    void sendMessage({ text: message.text }).then(() => onPersonaMayHaveChanged())
    setInput('')
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <Conversation className="min-h-0 min-w-0 overflow-hidden">
        <ConversationContent className="min-w-0 gap-4 px-1 py-2">
          {messages.length === 0 ? (
            <ConversationEmptyState
              className="mx-auto w-full max-w-md px-2"
              icon={<UserRoundIcon className="size-8" />}
              title="Who you are"
              description="Share your role, resume or site links, strengths, and durable skill gaps. Book goals and scope stay with the textbook chat—this profile is just background the manager reuses."
            />
          ) : (
            messages.map((message, index) => {
              const isLast = index === messages.length - 1
              return (
                <Message
                  from={message.role}
                  key={message.id}
                  className="min-w-0 max-w-full"
                >
                  <MessageContent className="min-w-0 max-w-full overflow-hidden break-words [overflow-wrap:anywhere]">
                    <InterviewMessageParts
                      message={message}
                      isLastMessage={isLast}
                      isStreaming={isStreaming}
                    />
                  </MessageContent>
                </Message>
              )
            })
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <div className="min-w-0 shrink-0 space-y-2 border-t border-border/70 p-1 pt-3">
        <LoadingState
          active={busy}
          label={
            status === 'submitted'
              ? 'Interviewer starting…'
              : 'Interviewer working…'
          }
          onStop={() => stop()}
        />
        {error ? (
          <StreamError
            title="Interview failed"
            detail={error.message}
            onDismiss={() => clearError()}
          />
        ) : null}
        <PromptInput onSubmit={handleSubmit} className="relative w-full min-w-0">
          <PromptInputTextarea
            value={input}
            onChange={(event) => setInput(event.currentTarget.value)}
            placeholder="Tell the interviewer about yourself…"
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

function PersonaInterview({
  onPersonaMayHaveChanged,
}: {
  onPersonaMayHaveChanged: () => void
}) {
  const [ready, setReady] = useState(false)
  const [history, setHistory] = useState<UIMessage[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setReady(false)
    setLoadError(null)
    fetch('/api/persona/messages')
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
  }, [])

  if (!ready) {
    return (
      <div className="flex min-h-0 flex-1 flex-col gap-3">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-24 w-full rounded-[var(--radius-md)]" />
        <Skeleton className="h-16 w-3/4 rounded-[var(--radius-md)]" />
      </div>
    )
  }

  return (
    <>
      {loadError ? (
        <StreamError
          title="Could not load interview history"
          detail={loadError}
          onDismiss={() => setLoadError(null)}
        />
      ) : null}
      <PersonaInterviewReady
        initialMessages={history}
        onPersonaMayHaveChanged={onPersonaMayHaveChanged}
      />
    </>
  )
}

export function PersonaPanel({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [tab, setTab] = useState<'edit' | 'interview'>('interview')
  const [markdown, setMarkdown] = useState('')
  const [savedMarkdown, setSavedMarkdown] = useState('')
  const [path, setPath] = useState('output/learner/persona.md')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [interviewEpoch, setInterviewEpoch] = useState(0)
  const dirty = markdown !== savedMarkdown
  const saveStatus = saveError
    ? 'Save failed'
    : saving
      ? 'Saving…'
      : dirty
        ? 'Editing…'
        : 'Saved'

  async function refreshPersona() {
    const res = await fetch('/api/persona')
    if (!res.ok) throw new Error(await res.text())
    const payload = (await res.json()) as PersonaPayload
    setMarkdown(payload.markdown)
    setSavedMarkdown(payload.markdown)
    setPath(payload.path)
  }

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoadError(null)
    setInterviewEpoch((value) => value + 1)
    fetch('/api/persona')
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text())
        return res.json() as Promise<PersonaPayload>
      })
      .then((persona) => {
        if (cancelled) return
        setMarkdown(persona.markdown)
        setSavedMarkdown(persona.markdown)
        setPath(persona.path)
      })
      .catch((err: Error) => {
        if (!cancelled) setLoadError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  useEffect(() => {
    if (!open || tab !== 'edit') return
    if (markdown === savedMarkdown) return

    let cancelled = false
    const toSave = markdown
    const timer = window.setTimeout(() => {
      setSaving(true)
      setSaveError(null)
      void fetch('/api/persona', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ markdown: toSave }),
      })
        .then(async (res) => {
          if (!res.ok) throw new Error(await res.text())
          return res.json() as Promise<PersonaPayload>
        })
        .then((payload) => {
          if (cancelled) return
          setSavedMarkdown(payload.markdown)
          setPath(payload.path)
          setMarkdown((current) =>
            current === toSave ? payload.markdown : current,
          )
        })
        .catch((err: Error) => {
          if (!cancelled) setSaveError(err.message)
        })
        .finally(() => {
          if (!cancelled) setSaving(false)
        })
    }, 450)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [markdown, open, savedMarkdown, tab])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-full max-w-full min-w-0 flex-col gap-0 overflow-hidden p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-xl"
      >
        <SheetHeader className="min-w-0 shrink-0 border-b border-border/70 px-4 py-3 pr-12">
          <SheetTitle>Learner profile</SheetTitle>
          <SheetDescription className="text-balance">
            Who you are—identity, role, background, strengths, and durable gaps. The
            textbook manager personalizes from this; book goals stay in each book chat.
          </SheetDescription>
        </SheetHeader>

        <div className="flex min-w-0 shrink-0 gap-1 border-b border-border/70 px-3 py-2">
          {(
            [
              ['interview', 'Interview'],
              ['edit', 'Edit'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={cn(
                'rounded-[var(--radius-md)] px-3 py-1.5 text-sm outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50',
                tab === id && 'bg-surface text-foreground shadow-sm',
              )}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col px-4 py-3">
          {loadError ? (
            <StreamError
              title="Could not load profile"
              detail={loadError}
              onDismiss={() => setLoadError(null)}
            />
          ) : null}

          {tab === 'edit' ? (
            <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
              <div className="flex min-w-0 items-center justify-between gap-2 px-1">
                <p className="min-w-0 truncate font-mono text-xs text-mist">{path}</p>
                <p
                  className={cn(
                    'shrink-0 text-xs',
                    saveError ? 'text-danger' : 'text-mist',
                  )}
                >
                  {saveStatus}
                </p>
              </div>
              {saveError ? (
                <StreamError
                  title="Could not save profile"
                  detail={saveError}
                  onDismiss={() => setSaveError(null)}
                />
              ) : null}
              <div className="flex min-h-0 min-w-0 flex-1 p-1">
                <Textarea
                  value={markdown}
                  onChange={(event) => setMarkdown(event.currentTarget.value)}
                  placeholder={`## Profile synopsis\n\n## Identity\n\n## Current role\n\n## Work experience / CV\n\n## Education\n\n## Strong knowledge\n\n## Durable skill gaps\n\n## How they learn best\n`}
                  className="min-h-0 min-w-0 flex-1 resize-none overflow-auto font-mono text-xs leading-relaxed break-words"
                />
              </div>
            </div>
          ) : open ? (
            <PersonaInterview
              key={interviewEpoch}
              onPersonaMayHaveChanged={() => {
                void refreshPersona().catch(() => undefined)
              }}
            />
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  )
}

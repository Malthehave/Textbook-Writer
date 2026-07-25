import { useCallback, useEffect, useState } from 'react'
import { FileTextIcon, PlusIcon } from 'lucide-react'
import { ChatPanel } from '@/ChatPanel'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable'
import { cn } from '@/lib/utils'

type Session = {
  id: string
  book_id: string
  workspace: string
  title: string
  created_at: string
  updated_at: string
}

type Artifact = {
  path: string
  bytes: number
  kind: string
}

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json() as Promise<T>
}

function artifactKindLabel(kind: string, path: string): string {
  if (kind === 'pdf') return 'PDF'
  if (kind === 'png' || path.endsWith('.png')) return 'Figure'
  if (path.endsWith('.json')) return 'JSON'
  if (path.endsWith('.md')) return 'MD'
  return kind.toUpperCase() || 'FILE'
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const softHandle =
  'w-2 bg-transparent after:w-1 after:rounded-full after:bg-transparent hover:after:bg-foreground/10'

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null)
  const [artifactContent, setArtifactContent] = useState<string>('')
  const [showPdf, setShowPdf] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionsReady, setSessionsReady] = useState(false)

  const refreshSessions = useCallback(async () => {
    const rows = await fetchJSON<Session[]>('/api/sessions')
    setSessions(rows)
    return rows
  }, [])

  const refreshArtifacts = useCallback(async (id: string) => {
    const rows = await fetchJSON<Artifact[]>(`/api/sessions/${id}/artifacts`)
    setArtifacts(rows)
    if (rows.some((row) => row.kind === 'pdf')) setShowPdf(true)
  }, [])

  useEffect(() => {
    refreshSessions()
      .then((rows) => {
        setSessionId((current) => {
          if (current || rows.length === 0) return current
          const latest = [...rows].sort(
            (a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at),
          )[0]
          return latest.id
        })
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setSessionsReady(true))
  }, [refreshSessions])

  useEffect(() => {
    if (!sessionId) return
    refreshArtifacts(sessionId).catch(() => setArtifacts([]))
    const timer = window.setInterval(() => {
      refreshArtifacts(sessionId).catch(() => undefined)
    }, 4000)
    return () => window.clearInterval(timer)
  }, [sessionId, refreshArtifacts])

  useEffect(() => {
    if (!sessionId || !selectedArtifact) {
      setArtifactContent('')
      return
    }
    const kind = selectedArtifact.split('.').pop()?.toLowerCase()
    if (kind === 'pdf' || kind === 'png') {
      setArtifactContent('')
      return
    }
    fetchJSON<{ content: string }>(
      `/api/sessions/${sessionId}/artifacts/content?path=${encodeURIComponent(selectedArtifact)}`,
    )
      .then((row) => setArtifactContent(row.content))
      .catch((err: Error) => setArtifactContent(err.message))
  }, [sessionId, selectedArtifact])

  async function onNewBook() {
    setBusy(true)
    setError(null)
    try {
      const created = await fetchJSON<Session>('/api/sessions', { method: 'POST' })
      await refreshSessions()
      setSessionId(created.id)
      setSelectedArtifact(null)
      setShowPdf(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const activeSession = sessions.find((session) => session.id === sessionId) ?? null
  const pdfUrl =
    sessionId && artifacts.some((row) => row.kind === 'pdf')
      ? `/api/sessions/${sessionId}/pdf#view=FitH`
      : null

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 bg-muted/50 p-3">
      <header className="flex items-center justify-between gap-4 px-2 pt-1">
        <div className="min-w-0">
          <h1 className="text-base font-semibold tracking-tight">Textbook Writer</h1>
          <p className="text-xs text-muted-foreground">
            Research · freeze · write · verify · publish
          </p>
        </div>
        <Button onClick={onNewBook} disabled={busy} size="sm">
          <PlusIcon />
          {busy ? 'Starting…' : 'New book'}
        </Button>
      </header>

      {error ? (
        <Alert variant="destructive" className="border-0 bg-destructive/10 shadow-none">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <ResizablePanelGroup orientation="horizontal" className="min-h-0 flex-1">
        <ResizablePanel defaultSize="18" minSize="14" maxSize="28">
          <div className="flex h-full min-h-0 flex-col rounded-2xl bg-sidebar/80 px-2 py-3 text-sidebar-foreground">
            <div className="mb-3 flex items-center justify-between px-2">
              <span className="text-xs font-medium text-muted-foreground">Sessions</span>
              <Badge variant="secondary" className="border-0">
                {sessions.length}
              </Badge>
            </div>
            <ScrollArea className="flex-1">
              <div className="space-y-0.5 px-1">
                {!sessionsReady ? (
                  <div className="space-y-2 p-1">
                    <Skeleton className="h-12 w-full rounded-xl" />
                    <Skeleton className="h-12 w-full rounded-xl" />
                  </div>
                ) : sessions.length === 0 ? (
                  <p className="px-2 py-4 text-sm text-muted-foreground">
                    No books yet. Start one to open the manager.
                  </p>
                ) : (
                  sessions.map((session) => {
                    const active = session.id === sessionId
                    return (
                      <Button
                        key={session.id}
                        type="button"
                        variant="ghost"
                        className={cn(
                          'h-auto w-full flex-col items-start gap-0.5 rounded-xl px-3 py-2.5',
                          active && 'bg-background text-foreground shadow-sm hover:bg-background',
                        )}
                        onClick={() => {
                          setSessionId(session.id)
                          setSelectedArtifact(null)
                        }}
                      >
                        <span className="w-full truncate text-left text-sm font-medium">
                          {session.title}
                        </span>
                        <span className="w-full truncate text-left font-mono text-[11px] text-muted-foreground">
                          {session.book_id}
                        </span>
                      </Button>
                    )
                  })
                )}
              </div>
            </ScrollArea>
          </div>
        </ResizablePanel>

        <ResizableHandle className={softHandle} />

        <ResizablePanel defaultSize="52" minSize="35">
          <div className="h-full min-h-0 overflow-hidden rounded-2xl bg-background shadow-sm">
            {!sessionsReady ? (
              <div className="flex h-full flex-col gap-3 p-5">
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-24 w-full rounded-xl" />
              </div>
            ) : sessionId ? (
              <ChatPanel
                key={sessionId}
                sessionId={sessionId}
                sessionTitle={activeSession?.title ?? 'Untitled book'}
                onActivity={() => {
                  refreshArtifacts(sessionId).catch(() => undefined)
                  refreshSessions().catch(() => undefined)
                }}
              />
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
                <div className="rounded-2xl bg-muted/60 p-4">
                  <FileTextIcon className="size-8 text-muted-foreground" />
                </div>
                <div className="space-y-1">
                  <h2 className="text-sm font-medium">Start a book</h2>
                  <p className="max-w-sm text-sm text-muted-foreground">
                    Tell the manager what you want to learn. It researches, freezes sources, writes,
                    verifies exercises, and publishes a PDF.
                  </p>
                </div>
                <Button onClick={onNewBook} disabled={busy}>
                  <PlusIcon />
                  {busy ? 'Starting…' : 'New book'}
                </Button>
              </div>
            )}
          </div>
        </ResizablePanel>

        <ResizableHandle className={softHandle} />

        <ResizablePanel defaultSize="30" minSize="20">
          <div className="flex h-full min-h-0 flex-col rounded-2xl bg-sidebar/80 px-2 py-3 text-sidebar-foreground">
            <div className="mb-3 flex items-center justify-between gap-2 px-2">
              <span className="text-xs font-medium text-muted-foreground">Artifacts</span>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={!pdfUrl}
                onClick={() => setShowPdf((value) => !value)}
              >
                {showPdf ? 'Hide PDF' : 'Show PDF'}
              </Button>
            </div>
            <ResizablePanelGroup orientation="vertical" className="min-h-0 flex-1">
              <ResizablePanel defaultSize="35" minSize="20">
                <ScrollArea className="h-full">
                  <div className="space-y-0.5 px-1">
                    {artifacts.length === 0 ? (
                      <p className="px-2 py-4 text-sm text-muted-foreground">
                        Artifacts appear as the manager researches, writes, and publishes.
                      </p>
                    ) : (
                      artifacts.map((artifact) => {
                        const active = selectedArtifact === artifact.path
                        return (
                          <Button
                            key={artifact.path}
                            type="button"
                            variant="ghost"
                            className={cn(
                              'h-auto w-full items-start justify-start gap-2 rounded-xl px-2 py-2',
                              active && 'bg-background text-foreground shadow-sm hover:bg-background',
                            )}
                            onClick={() => {
                              setSelectedArtifact(artifact.path)
                              if (artifact.kind === 'pdf') setShowPdf(true)
                            }}
                          >
                            <Badge variant="secondary" className="shrink-0 border-0">
                              {artifactKindLabel(artifact.kind, artifact.path)}
                            </Badge>
                            <span className="min-w-0 flex-1 text-left">
                              <span className="block truncate font-mono text-[11px]">
                                {artifact.path}
                              </span>
                              <span className="block text-[11px] text-muted-foreground">
                                {formatBytes(artifact.bytes)}
                              </span>
                            </span>
                          </Button>
                        )
                      })
                    )}
                  </div>
                </ScrollArea>
              </ResizablePanel>
              <ResizableHandle className="h-2 bg-transparent after:h-1 after:w-10 after:rounded-full after:bg-transparent hover:after:bg-foreground/10" />
              <ResizablePanel defaultSize="65" minSize="30">
                <div className="mx-1 mb-1 h-full min-h-0 overflow-hidden rounded-xl bg-background/70">
                  {showPdf && pdfUrl ? (
                    <iframe title="PDF preview" src={pdfUrl} className="h-full w-full bg-background" />
                  ) : selectedArtifact?.endsWith('.png') && sessionId ? (
                    <img
                      alt={selectedArtifact}
                      src={`/api/sessions/${sessionId}/files/${selectedArtifact}`}
                      className="h-full w-full object-contain p-3"
                    />
                  ) : (
                    <ScrollArea className="h-full">
                      <pre className="whitespace-pre-wrap p-4 font-mono text-xs text-muted-foreground">
                        {artifactContent || 'Select an artifact to preview.'}
                      </pre>
                    </ScrollArea>
                  )}
                </div>
              </ResizablePanel>
            </ResizablePanelGroup>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}

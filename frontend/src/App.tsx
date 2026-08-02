import { useCallback, useEffect, useState } from 'react'
import {
  ChevronRightIcon,
  FileTextIcon,
  FolderIcon,
  FolderOpenIcon,
  PlusIcon,
  UserRoundIcon,
} from 'lucide-react'
import { ChatPanel } from '@/ChatPanel'
import { PersonaPanel } from '@/PersonaPanel'
import { StreamError } from '@/components/ai-elements/stream-error'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar'
import { useIsMobile } from '@/hooks/use-mobile'
import { cn } from '@/lib/utils'

type Session = {
  id: string
  title: string
  created_at: string
  updated_at: string
}

type Artifact = {
  path: string
  bytes: number
  kind: string
}

type ArtifactTreeNode =
  | { type: 'dir'; name: string; path: string; children: ArtifactTreeNode[] }
  | { type: 'file'; name: string; artifact: Artifact }

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json() as Promise<T>
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function buildArtifactTree(artifacts: Artifact[]): ArtifactTreeNode[] {
  type DirDraft = {
    type: 'dir'
    name: string
    path: string
    children: Map<string, DirDraft | { type: 'file'; name: string; artifact: Artifact }>
  }

  const root = new Map<string, DirDraft | { type: 'file'; name: string; artifact: Artifact }>()

  for (const artifact of artifacts) {
    const parts = artifact.path.split('/').filter(Boolean)
    let current = root
    let prefix = ''
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      const isFile = i === parts.length - 1
      prefix = prefix ? `${prefix}/${part}` : part
      if (isFile) {
        current.set(part, { type: 'file', name: part, artifact })
        continue
      }
      const existing = current.get(part)
      if (!existing || existing.type !== 'dir') {
        const dir: DirDraft = {
          type: 'dir',
          name: part,
          path: prefix,
          children: new Map(),
        }
        current.set(part, dir)
        current = dir.children
      } else {
        current = existing.children
      }
    }
  }

  function toNodes(
    map: Map<string, DirDraft | { type: 'file'; name: string; artifact: Artifact }>,
  ): ArtifactTreeNode[] {
    return [...map.values()]
      .map((node): ArtifactTreeNode =>
        node.type === 'dir'
          ? {
              type: 'dir',
              name: node.name,
              path: node.path,
              children: toNodes(node.children),
            }
          : node,
      )
      .sort((a, b) => {
        if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
        return a.name.localeCompare(b.name)
      })
  }

  return toNodes(root)
}

function SessionsSidebar({
  sessions,
  sessionsReady,
  sessionId,
  busy,
  onSelect,
  onNewBook,
}: {
  sessions: Session[]
  sessionsReady: boolean
  sessionId: string | null
  busy: boolean
  onSelect: (id: string) => void
  onNewBook: () => void
}) {
  const { isMobile, setOpenMobile } = useSidebar()

  return (
    <Sidebar
      collapsible="offcanvas"
      variant="floating"
      className="top-14 bottom-0 z-20 py-3 pl-3 pr-0"
    >
      <SidebarHeader className="px-2 pt-0 pb-1">
        <span className="px-2 text-xs font-medium text-mist">Sessions</span>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="px-0 py-0">
          <SidebarGroupContent>
            <SidebarMenu>
              {!sessionsReady ? (
                <>
                  <SidebarMenuItem>
                    <SidebarMenuSkeleton showIcon />
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuSkeleton showIcon />
                  </SidebarMenuItem>
                </>
              ) : sessions.length === 0 ? (
                <p className="px-2 py-3 text-sm text-mist">
                  No books yet. Start one to open the manager.
                </p>
              ) : (
                sessions.map((session) => (
                  <SidebarMenuItem key={session.id}>
                    <SidebarMenuButton
                      type="button"
                      size="lg"
                      isActive={session.id === sessionId}
                      tooltip={session.title}
                      className="h-auto items-start rounded-[var(--radius-md)] py-2 hover:bg-muted hover:text-foreground data-active:bg-surface data-active:text-foreground data-active:shadow-sm data-active:hover:bg-surface"
                      onClick={() => {
                        onSelect(session.id)
                        if (isMobile) setOpenMobile(false)
                      }}
                    >
                      <div className="flex min-w-0 flex-1 flex-col gap-0.5 text-left">
                        <span className="truncate font-medium">{session.title}</span>
                        <span className="truncate font-mono text-xs text-mist">
                          {session.id}
                        </span>
                      </div>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="px-2 pb-0">
        <Button className="w-full" onClick={onNewBook} disabled={busy} size="sm">
          <PlusIcon />
          {busy ? 'Starting…' : 'New book'}
        </Button>
      </SidebarFooter>
    </Sidebar>
  )
}

function ArtifactTreeRows({
  nodes,
  depth,
  selectedArtifact,
  onSelect,
}: {
  nodes: ArtifactTreeNode[]
  depth: number
  selectedArtifact: string | null
  onSelect: (artifact: Artifact) => void
}) {
  return (
    <>
      {nodes.map((node) => {
        if (node.type === 'dir') {
          const containsSelected =
            selectedArtifact != null &&
            (selectedArtifact === node.path ||
              selectedArtifact.startsWith(`${node.path}/`))
          return (
            <Collapsible key={node.path} defaultOpen={depth < 2 || containsSelected}>
              <CollapsibleTrigger
                className={cn(
                  'flex w-max min-w-full items-center gap-1.5 rounded-[var(--radius-md)] py-1.5 pr-2 text-left text-xs text-mist outline-none hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 [&[data-state=open]>svg:first-child]:rotate-90',
                )}
                style={{ paddingLeft: `${0.5 + depth * 0.75}rem` }}
              >
                <ChevronRightIcon className="size-3.5 shrink-0 transition-transform" />
                <FolderIcon className="size-3.5 shrink-0" />
                <span className="whitespace-nowrap font-mono">{node.name}</span>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <ArtifactTreeRows
                  nodes={node.children}
                  depth={depth + 1}
                  selectedArtifact={selectedArtifact}
                  onSelect={onSelect}
                />
              </CollapsibleContent>
            </Collapsible>
          )
        }

        const active = selectedArtifact === node.artifact.path
        return (
          <button
            key={node.artifact.path}
            type="button"
            title={`${node.artifact.path} · ${formatBytes(node.artifact.bytes)}`}
            className={cn(
              'flex w-max min-w-full items-center gap-1.5 rounded-[var(--radius-md)] py-1.5 pr-2 text-left outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50',
              active && 'bg-surface text-foreground shadow-sm hover:bg-surface',
            )}
            style={{ paddingLeft: `${0.5 + depth * 0.75}rem` }}
            onClick={() => onSelect(node.artifact)}
          >
            <span className="size-3.5 shrink-0" aria-hidden />
            <FileTextIcon className="size-3.5 shrink-0 text-mist" />
            <span className="whitespace-nowrap font-mono text-xs">{node.name}</span>
          </button>
        )
      })}
    </>
  )
}

function ArtifactList({
  artifacts,
  selectedArtifact,
  onSelect,
}: {
  artifacts: Artifact[]
  selectedArtifact: string | null
  onSelect: (artifact: Artifact) => void
}) {
  if (artifacts.length === 0) {
    return (
      <p className="px-2 py-4 text-sm text-mist">
        This chat’s book starts empty. Artifacts appear as the manager researches,
        writes, and publishes.
      </p>
    )
  }

  const tree = buildArtifactTree(artifacts)

  return (
    <div className="w-max min-w-full px-1 py-0.5">
      <div className="mb-1 flex w-max min-w-full items-center gap-1.5 px-2 py-1 font-mono text-xs text-mist">
        <FolderOpenIcon className="size-3.5 shrink-0" />
        <span className="whitespace-nowrap">/book</span>
      </div>
      <ArtifactTreeRows
        nodes={tree}
        depth={0}
        selectedArtifact={selectedArtifact}
        onSelect={onSelect}
      />
    </div>
  )
}

function ArtifactPreview({
  sessionId,
  pdfUrl,
  previewPdf,
  selectedArtifact,
  artifactContent,
}: {
  sessionId: string | null
  pdfUrl: string | null
  previewPdf: boolean
  selectedArtifact: string | null
  artifactContent: string
}) {
  if (previewPdf) {
    if (!pdfUrl) {
      return <p className="p-4 text-sm text-mist">No PDF published yet.</p>
    }
    return <iframe title="PDF preview" src={pdfUrl} className="h-full w-full bg-paper" />
  }
  if (selectedArtifact?.endsWith('.png') && sessionId) {
    return (
      <img
        alt={selectedArtifact}
        src={`/api/sessions/${sessionId}/files/${selectedArtifact}`}
        className="h-full w-full object-contain p-3"
      />
    )
  }
  return (
    <ScrollArea className="h-full">
      <pre className="whitespace-pre-wrap break-all p-4 font-mono text-xs text-mist">
        {artifactContent || 'Loading…'}
      </pre>
    </ScrollArea>
  )
}

export default function App() {
  /*
    THESIS: Compile console — chat owns the book; rails hold sessions and artifacts.
    OWN-WORLD: Cool paper, ink primary, live blue only while streaming.
    STORY: Start a book, talk to the manager, watch artifacts appear, open the PDF.
    FIRST VIEWPORT: Header + three columns; empty chat invites the first brief.
    FORM: Perimeter-rail staging inside a restrained operate system.
  */
  const isMobile = useIsMobile()
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null)
  const [artifactContent, setArtifactContent] = useState<string>('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewPdf, setPreviewPdf] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionsReady, setSessionsReady] = useState(false)
  const [artifactsOpen, setArtifactsOpen] = useState(false)
  const [personaOpen, setPersonaOpen] = useState(false)

  const refreshSessions = useCallback(async () => {
    const rows = await fetchJSON<Session[]>('/api/sessions')
    setSessions(rows)
    return rows
  }, [])

  const refreshArtifacts = useCallback(async (id: string) => {
    const rows = await fetchJSON<Artifact[]>(`/api/sessions/${id}/artifacts`)
    setArtifacts(rows)
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
    if (!previewOpen || previewPdf || !sessionId || !selectedArtifact) {
      setArtifactContent('')
      return
    }
    const kind = selectedArtifact.split('.').pop()?.toLowerCase()
    if (kind === 'pdf' || kind === 'png') {
      setArtifactContent('')
      return
    }
    let cancelled = false
    setArtifactContent('Loading…')
    fetchJSON<{ content: string }>(
      `/api/sessions/${sessionId}/artifacts/content?path=${encodeURIComponent(selectedArtifact)}`,
    )
      .then((row) => {
        if (!cancelled) setArtifactContent(row.content)
      })
      .catch((err: Error) => {
        if (!cancelled) setArtifactContent(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [previewOpen, previewPdf, sessionId, selectedArtifact])

  async function onNewBook() {
    setBusy(true)
    setError(null)
    try {
      const created = await fetchJSON<Session>('/api/sessions', { method: 'POST' })
      await refreshSessions()
      setSessionId(created.id)
      setSelectedArtifact(null)
      setPreviewOpen(false)
      setPreviewPdf(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  function selectSession(id: string) {
    setSessionId(id)
    setSelectedArtifact(null)
    setPreviewOpen(false)
    setPreviewPdf(false)
  }

  function selectArtifact(artifact: Artifact) {
    setSelectedArtifact(artifact.path)
    setPreviewPdf(artifact.kind === 'pdf')
    setPreviewOpen(true)
  }

  function openPdfPreview() {
    setPreviewPdf(true)
    setPreviewOpen(true)
  }

  const activeSession = sessions.find((session) => session.id === sessionId) ?? null
  const pdfUrl =
    sessionId && artifacts.some((row) => row.kind === 'pdf')
      ? `/api/sessions/${sessionId}/pdf#view=FitH`
      : null

  const chatSurface = (
    <div className="h-full min-h-0 overflow-hidden rounded-[var(--radius-lg)] bg-surface shadow-sm">
      {!sessionsReady ? (
        <div className="flex h-full flex-col gap-3 p-5">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-24 w-full rounded-[var(--radius-md)]" />
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
          <div className="rounded-[var(--radius-lg)] bg-panel p-4">
            <FileTextIcon className="size-8 text-mist" />
          </div>
          <div className="space-y-1">
            <h2 className="text-sm font-medium">Start a book</h2>
            <p className="max-w-sm text-sm text-mist">
              Tell the manager what you want to learn. It researches, writes chapters,
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
  )

  const artifactsRail = (
    <div className="flex h-full min-h-0 flex-col rounded-[var(--radius-lg)] bg-panel px-2 py-3">
      <div className="mb-3 flex items-center justify-between gap-2 px-2">
        <span className="text-xs font-medium text-mist">Artifacts</span>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="shrink-0"
          disabled={!pdfUrl}
          onClick={openPdfPreview}
        >
          Open PDF
        </Button>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <ArtifactList
          artifacts={artifacts}
          selectedArtifact={selectedArtifact}
          onSelect={selectArtifact}
        />
      </ScrollArea>
    </div>
  )

  return (
    <SidebarProvider className="h-svh bg-paper">
      {/* Full-width header so SidebarTrigger never shifts with the rail */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-border/70 bg-background px-3">
        <div className="flex min-w-0 items-center gap-2">
          <SidebarTrigger className="shrink-0" />
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold tracking-tight text-ink">
              Textbook Writer
            </h1>
            <p className="hidden text-xs text-mist sm:block">
              Research · write · verify · publish
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setPersonaOpen(true)}
          >
            <UserRoundIcon />
            <span className="hidden sm:inline">Profile</span>
          </Button>
          {isMobile ? (
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              aria-label="Open artifacts"
              onClick={() => setArtifactsOpen(true)}
            >
              <FolderOpenIcon />
            </Button>
          ) : null}
          <Button onClick={onNewBook} disabled={busy} size="sm">
            <PlusIcon />
            <span className="hidden sm:inline">{busy ? 'Starting…' : 'New book'}</span>
          </Button>
        </div>
      </header>

      <SessionsSidebar
        sessions={sessions}
        sessionsReady={sessionsReady}
        sessionId={sessionId}
        busy={busy}
        onSelect={selectSession}
        onNewBook={onNewBook}
      />
      <SidebarInset className="min-h-0 overflow-hidden bg-paper pt-14">
        {error ? (
          <div className="px-3 pt-3">
            <StreamError title="Could not reach the API" detail={error} onDismiss={() => setError(null)} />
          </div>
        ) : null}

        <div className="min-h-0 flex-1 p-3">
          {isMobile ? (
            <div className="h-full min-h-0">{chatSurface}</div>
          ) : (
            <div className="flex h-full min-h-0 gap-3">
              <div className="min-w-0 flex-1">{chatSurface}</div>
              <div className="w-[min(28rem,34%)] shrink-0">{artifactsRail}</div>
            </div>
          )}
        </div>
      </SidebarInset>

      <PersonaPanel open={personaOpen} onOpenChange={setPersonaOpen} />

      <Sheet open={artifactsOpen} onOpenChange={setArtifactsOpen}>
        <SheetContent side="right" className="w-[min(24rem,94vw)] gap-0 p-0">
          <SheetHeader className="border-b border-border/70 px-4 py-3">
            <SheetTitle>Artifacts</SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-2">
            <div className="flex justify-end px-1">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={!pdfUrl}
                onClick={openPdfPreview}
              >
                Open PDF
              </Button>
            </div>
            <ScrollArea className="min-h-0 flex-1">
              <ArtifactList
                artifacts={artifacts}
                selectedArtifact={selectedArtifact}
                onSelect={selectArtifact}
              />
            </ScrollArea>
          </div>
        </SheetContent>
      </Sheet>

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="flex h-[min(85vh,52rem)] w-full max-w-[calc(100%-2rem)] flex-col gap-3 p-0 sm:max-w-4xl">
          <DialogHeader className="shrink-0 border-b border-border/70 px-4 py-3 pr-12">
            <DialogTitle className="truncate font-mono text-sm font-medium">
              {previewPdf ? 'PDF' : selectedArtifact ?? 'Preview'}
            </DialogTitle>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-hidden">
            <ArtifactPreview
              sessionId={sessionId}
              pdfUrl={pdfUrl}
              previewPdf={previewPdf}
              selectedArtifact={selectedArtifact}
              artifactContent={artifactContent}
            />
          </div>
        </DialogContent>
      </Dialog>
    </SidebarProvider>
  )
}

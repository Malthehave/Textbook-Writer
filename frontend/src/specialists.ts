export const SPECIALIST_TOOL_NAMES = new Set([
  'research-scout',
  'research-architect',
  'research-auditor',
  'curriculum-architect',
  'coverage-auditor',
  'curriculum-repair',
  'chapter-writer',
  'html-diagram-author',
  'independent-verifier',
  'solution-comparator',
  'exercise-repair',
  'continuity-editor',
])

export function isSpecialistTool(toolName: string): boolean {
  return SPECIALIST_TOOL_NAMES.has(toolName)
}

export function specialistLabel(toolName: string): string {
  return toolName
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export type SpecialistRun = {
  agentName: string
  status: 'running' | 'completed' | 'failed'
  label?: string
  errorText?: string
  text: string
  reasoning: string
}

export type SpecialistDataEvent = {
  parentToolCallId: string
  agentName: string
  kind: 'status' | 'text-delta' | 'reasoning-delta' | 'tool-input' | 'tool-output'
  status?: 'running' | 'completed' | 'failed'
  label?: string
  errorText?: string
  text?: string
  toolCallId?: string
  toolName?: string
  input?: unknown
  output?: unknown
}

export function applySpecialistEvent(
  current: Record<string, SpecialistRun>,
  event: SpecialistDataEvent,
): Record<string, SpecialistRun> {
  const id = event.parentToolCallId
  const prev = current[id] ?? {
    agentName: event.agentName,
    status: 'running' as const,
    text: '',
    reasoning: '',
  }
  const next: SpecialistRun = {
    ...prev,
    agentName: event.agentName || prev.agentName,
  }

  switch (event.kind) {
    case 'status':
      if (event.status) next.status = event.status
      if (event.label) next.label = event.label
      if (event.errorText) next.errorText = event.errorText
      break
    case 'text-delta':
      next.text += event.text ?? ''
      break
    case 'reasoning-delta':
      next.reasoning += event.text ?? ''
      break
    case 'tool-input':
      if (event.toolName) next.label = `Using ${event.toolName}`
      break
    case 'tool-output':
      break
  }

  return { ...current, [id]: next }
}

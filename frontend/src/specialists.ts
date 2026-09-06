export const SPECIALIST_TOOL_NAMES = new Set([
  'research-architect',
  'lead-author',
  'reader-experience-editor',
  'publication-reviewer',
  // Legacy session tools remain recognizable in restored transcripts.
  'curriculum-architect',
  'chapter-writer',
  'chapter-reviewer',
  'html-diagram-author',
  'independent-verifier',
  'solution-comparator',
])

export function isSpecialistTool(toolName: string): boolean {
  return SPECIALIST_TOOL_NAMES.has(toolName)
}

export function specialistLabel(toolName: string): string {
  if (toolName === 'lead-author') return 'Lead author'
  if (toolName === 'reader-experience-editor') return 'Reader-experience editor'
  if (toolName === 'publication-reviewer') return 'Publication reviewer'
  return toolName
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export const SPECIALIST_TOOL_NAMES = new Set([
  'research-architect',
  'curriculum-architect',
  'chapter-writer',
  'independent-verifier',
  'solution-comparator',
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

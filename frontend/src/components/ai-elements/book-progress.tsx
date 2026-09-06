import {
  CheckCircle2Icon,
  CircleDashedIcon,
  CircleIcon,
  TriangleAlertIcon,
} from 'lucide-react'

import { cn } from '@/lib/utils'

export type ChapterProgress = {
  chapter_id: string
  title: string
  position: number
  stage: string
  draft: string
  editorial: string
  answers: string
  exercise_qa: string
  accepted: boolean
}

export type BookProgress = {
  status: string
  research: string
  curriculum: string
  editorial_state: string
  manuscript: string
  publication_review: string
  next_actions: string[]
  chapters: ChapterProgress[]
  completed_chapters: number
  total_chapters: number
  milestones: {
    completed: number
    total: number
  }
  publication: {
    status: string
    actual_pages?: number
    minimum_pages?: number
    maximum_pages?: number
    within_tolerance?: boolean
    quality_passed?: boolean
    quality_issues?: Array<{ category: string; message: string }>
    solutions_pdf_path?: string
  }
}

const CHAPTER_STAGE_LABELS: Record<string, string> = {
  pending: 'Waiting',
  'draft-invalid': 'Draft issue',
  drafted: 'Drafted',
  'review-invalid': 'Review issue',
  'revision-requested': 'Needs revision',
  revised: 'Rewritten',
  'awaiting-acceptance': 'Review passed',
  'editorial-approved': 'Editorially approved',
  'verification-invalid': 'QA issue',
  'awaiting-exercise-qa': 'Awaiting QA',
  'awaiting-comparison': 'Comparing answers',
  'solving-exercises': 'Solving exercises',
  'exercise-revision': 'Fixing exercises',
  complete: 'Approved',
}

function StatusIcon({
  status,
  className,
}: {
  status: string
  className?: string
}) {
  if (status === 'complete' || status === 'approved' || status === 'approve') {
    return <CheckCircle2Icon className={cn('size-3.5 text-primary', className)} />
  }
  if (status === 'invalid' || status.includes('invalid')) {
    return (
      <TriangleAlertIcon className={cn('size-3.5 text-destructive', className)} />
    )
  }
  if (status === 'pending') {
    return <CircleIcon className={cn('size-3.5 text-mist/60', className)} />
  }
  return <CircleDashedIcon className={cn('size-3.5 text-amber-600', className)} />
}

function Phase({
  label,
  status,
}: {
  label: string
  status: string
}) {
  return (
    <div className="flex shrink-0 items-center gap-1.5 text-xs">
      <StatusIcon status={status} />
      <span className={status === 'pending' ? 'text-mist' : 'text-foreground'}>
        {label}
      </span>
    </div>
  )
}

export function BookProgressPanel({
  progress,
  activity,
}: {
  progress: BookProgress | null
  activity: string | null
}) {
  if (!progress) return null
  const visible =
    progress.research !== 'pending' ||
    progress.curriculum !== 'pending' ||
    progress.chapters.length > 0
  if (!visible) return null

  const percentage =
    progress.milestones.total > 0
      ? Math.round(
          (progress.milestones.completed / progress.milestones.total) * 100,
        )
      : 0
  const publicationStatus =
    progress.publication.status === 'complete'
      ? 'complete'
      : progress.publication.status === 'invalid'
        ? 'invalid'
        : progress.publication.status === 'needs-fit-revision'
          ? 'needs-fit-revision'
          : progress.publication.status === 'needs-quality-revision'
            ? 'needs-quality-revision'
          : 'pending'
  const summary =
    activity ??
    (progress.status === 'published'
      ? 'Textbook and compiled review approved'
      : progress.status === 'publication-revision'
        ? 'Compiled textbook needs a targeted revision'
        : progress.next_actions[0]
          ? `Next: ${progress.next_actions[0].replaceAll('-', ' ')}`
          : `${progress.completed_chapters} of ${progress.total_chapters} chapters approved`)

  return (
    <section className="shrink-0 px-5 pb-2" aria-label="Book production progress">
      <div className="overflow-hidden rounded-[var(--radius-lg)] border border-border/70 bg-panel/55">
        <div className="flex items-start justify-between gap-3 px-3 py-2.5">
          <div className="min-w-0">
            <div className="text-xs font-medium tracking-wide text-mist uppercase">
              Book progress
            </div>
            <div className="mt-0.5 truncate text-sm">
              {summary}
            </div>
          </div>
          <div className="shrink-0 font-mono text-xs tabular-nums text-mist">
            {percentage}% milestones
          </div>
        </div>

        <div className="h-0.5 bg-border/60">
          <div
            className="h-full bg-primary transition-[width] duration-300"
            style={{ width: `${percentage}%` }}
          />
        </div>

        <div className="flex min-w-0 gap-3 overflow-x-auto px-3 py-2">
          <Phase label="Research" status={progress.research} />
          <Phase label="Learning plan" status={progress.curriculum} />
          {progress.chapters.map((chapter) => (
            <div
              key={chapter.chapter_id}
              className="flex shrink-0 items-center gap-1.5 text-xs"
              title={chapter.title}
            >
              <StatusIcon status={chapter.stage} />
              <span className="text-foreground">Ch {chapter.position}</span>
              <span className="text-mist">
                {CHAPTER_STAGE_LABELS[chapter.stage] ?? chapter.stage}
              </span>
            </div>
          ))}
          <Phase label="Reader experience" status={progress.manuscript} />
          <Phase label="PDF" status={publicationStatus} />
          <Phase label="Compiled review" status={progress.publication_review} />
        </div>
      </div>
    </section>
  )
}

---
name: manager-orchestration
description: >-
  Run the textbook compiler in phase order, resume safely from disk, and apply
  reader, exercise, and publication gates.
---

# Manager orchestration

You own the learner chat. Specialists are tools and every specialist invocation is fresh.
Canonical state is this book's shared `production/` directory, never the transcript. Pass a
self-contained task brief and canonical paths in every tool input. Inspect artifacts after
short specialist status returns. Compile only with `build-textbook-pdf`.

## Modern roster

| Specialist | Writes |
|---|---|
| research-architect | `production/research.json` |
| lead-author | `production/book-plan.json` and every `production/chapters/<id>.json` |
| html-diagram-author | stable HTML/PNG plus atomic chapter figure attachment |
| reader-experience-editor | `production/manuscript.review.json` |
| independent-verifier | `production/chapters/<id>.answers.json` |
| solution-comparator | `production/chapters/<id>.verification.json` |
| publication-reviewer | `production/publication.review.json` |

The blind solver is the canonical answer-key author. The lead author's draft answers exist
only for comparison. The reader editor judges prose while it is still editable.

## Modes

- `quality-slice`: default for fast iteration; one 1,500–2,200 word chapter, 2–3
  progressive exercises, no more than one visual, 8–10 target pages. It follows a complete
  learning progression and omits report-like front matter.
- `short-book`: 2–3 chapters, 5,000–8,000 manuscript words, 18–28 target pages.
- `production`: a larger full workflow using the same lead-author and reader gates.
- `prototype`: legacy resume only; do not recommend it for a new book.

## Mandatory modern phase order

### A — Confirm the learning promise

Agree audience, starting point, depth, scope, target capability, mode, must-cover topics,
and relevant learner URLs. A durable persona informs teaching choices but is not a
curriculum. Do not research until the learner confirms the book scope.

### B — Research

Call `research-architect`; validate `production/research.json`. Formal subject evidence
must be represented here with real HTTPS sources and source IDs.

### C — Lead-author manuscript

Call `lead-author` once with the complete confirmed brief. It owns plan and all prose in the
same run. Validate `production/book-plan.json` and every chapter. For modern modes, each plan
slice must explicitly define the reader's start, conceptual obstacle, intuition bridge,
worked-example progression, mechanisms, misconceptions, evidence/demonstration, and
practice progression. Call `forecast-textbook-pages` once after the full manuscript exists.

If the lead author returns `invalid=...`, re-invoke it with the exact validation error. Do
not manager-edit production JSON. Do not split initial modern authorship into unrelated
chapter-writer calls.

### D — Figures

Call `html-diagram-author` once for each planned visual after prose exists. Validate the
complete attached chapter. Do not send prose through a diagram-authoring loop.

### E — Reader-experience gate

Call `reader-experience-editor` on every chapter in reading order. Validate and open
`production/manuscript.review.json`. It must have all eight reader-experience scores.
Approval requires every score at least 4.

On revise, call `lead-author` once with the canonical review path. It should implement all
related notes together while preserving unaffected text, IDs, figures, and sources. Re-run
the whole reader gate after any prose edit. Never start independent exercise QA before a
fresh reader approval.

### F — Exercise QA

For every frozen chapter, call `independent-verifier`, validate its blind answers, then call
`solution-comparator`. Different chapters may use the two tool slots concurrently. Inspect
verification JSON; a status line is not evidence. For any non-approve verdict, pass the
verification path to `lead-author` for exercise-only repair, then solve and compare again.

### G — Publish and inspect

Call `build-textbook-pdf`; it writes the current PDF and
`production/publication-report.json`. Require deterministic quality and measured page fit
inside the inclusive target ±15% range. Only this report—not word counts, images, or a
forecast—can drive a fit revision.

Then call `publication-reviewer` once. It returns every PDF page as an individual preview
image and must inspect them all. Validate and open `production/publication.review.json`.
Finish only on a fresh approval. Route a material defect to the smallest owning stage,
re-run all stale downstream gates, compile, and inspect the new PDF. Keep the latest PDF
available during repair.

## Recovery

Call `inspect-pipeline-state` at startup and after every gate. Execute its `next_actions`.
Actions are `research-architect`, `lead-author:complete-manuscript`, a planned diagram,
`reader-experience-editor` or `lead-author:manuscript-revision`, exercise QA, compile, and
publication review. Existing books with an unscored manuscript approval return to the
reader-experience editor once; old per-chapter review files are ignored.

On any invalid artifact, give the exact error back to the producing specialist and keep
repairing until valid. Never use publication to discover stale schemas. Never run two lead
author calls concurrently.

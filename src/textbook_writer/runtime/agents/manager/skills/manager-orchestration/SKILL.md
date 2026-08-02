---
name: manager-orchestration
description: >-
  How the textbook manager uses each specialist and the book filesystem, in
  phase order. Use before calling specialists or recovering from errors.
---

# Manager orchestration

You own the learner chat. Specialists are tools. This chat is **one book**;
canonical state is this chat’s sandbox root—not the chat transcript.

You and every specialist share that **same sandbox root** (this chat only). Each
specialist tool call is a fresh run: put the task brief in the tool `input` string;
they do not remember prior calls. Specialists write stage artifacts under
`production/`; their tool returns are short status lines only. Inspect artifacts with
**Shell** and the **file editor**. PDF compile is the `build-textbook-pdf` tool — never
Shell-import the app package.

## Roster (editor view)

You are the editor. You do **not** run the diagrammer yourself — the chapter author owns
figures. You **do** run independent exercise QA after a chapter is written (authors must
not grade their own exercises).

| Specialist | Writes |
|---|---|
| research-architect | `production/research.json` |
| curriculum-architect | `production/book-plan.json` |
| chapter-writer | `production/chapters/<id>.json` (+ figures via nested diagrammer) |
| independent-verifier | `production/chapters/<id>.answers.json` |
| solution-comparator | `production/chapters/<id>.verification.json` |

## Disk layout

| Path | Role |
|---|---|
| `production/research.json` | Research (sources + topics) |
| `production/book-plan.json` | Curriculum plan |
| `production/chapters/<id>.json` | Chapter + exercises |
| `production/chapters/<id>.answers.json` | Blind solve |
| `production/chapters/<id>.verification.json` | Grade |
| `production/book.json` | Assembled book |
| `build/<slug>.pdf` | Measured PDF |

Before re-running a stage, `ls production/`. Resume from disk when a good artifact exists.

## Phase order (mandatory)

### A — Goal
Chat only. Clarify audience, depth, scope, and length with the learner. Collect HTTPS
URLs. Do not start research until they confirm the scope in chat.

Rough page guidance for later planning: ~5/8/12 pages per chapter for
compact/intermediate/deep, plus ~20% overhead (min 4). Put `target_pages` on the
book plan when curriculum runs.

### B — Research
`research-architect` → `research.json` (web search; follow `$research`).
The architect owns finding real sources.

### C — Curriculum
`curriculum-architect` → `book-plan.json` (include `target_pages` from the agreed
scope). If the plan is weak, edit the JSON or re-run the architect with a short fix
brief—no separate auditor/repair agents.

### D — Per chapter (plan order)
1. `chapter-writer` → chapter JSON **and** its figures (author calls the diagrammer)
2. `independent-verifier` — answer-free exercises only (blind QA; you commission this)
3. `solution-comparator` → `production/chapters/<id>.verification.json`
4. **Exercise QA gate (mandatory — never skip)** — open the verification file with Shell/file
   editor and inspect every `verdicts[].decision`:

#### If any verdict is `reject` or `revise`
Do **not** advance to the next chapter or to publish.

1. Build a rewrite brief from the verification file: for each non-`approve` verdict, include
   `exercise_ref`, `decision`, `result`, `ambiguity`, and the full `notes` text.
2. Call `chapter-writer` with that brief in the tool `input` (plus chapter id / plan slice).
   The author must fix those defects; do not paraphrase away the notes.
3. Re-run `independent-verifier` (fresh answers file).
4. Re-run `solution-comparator`.
5. Re-open `.verification.json`. Repeat the gate.

**Cap:** at most **two** rewrite cycles per chapter after the first compare (initial write +
up to two fix passes). If still not all-`approve`, stop and tell the learner which exercises
failed and why (quote `notes`) — do not publish that chapter’s broken exercises.

#### If every verdict is `approve`
Chapter is QA-clear. Continue to the next chapter (or publish when all planned chapters are
clear).

Never treat a comparator tool status line as proof of approval — only the verification JSON
on disk counts.

### E — Publish
Only after **every** planned chapter has an all-`approve` `.verification.json` on disk.
Call `build-textbook-pdf`. Tell the learner the measured `pdf_path` / page counts from the
tool return. Never invent page counts.

## Error recovery

- **missing sources / bad source_refs** → architect put URLs in `source_refs`. Retry with:
  “Use source_id strings in source_refs; put URLs only on sources[].url.”
- **two independent hosts** → need a second hostname, not a second path on the same site.
- **missing production/X** → prior stage not on disk; run the prior step, don’t invent JSON.

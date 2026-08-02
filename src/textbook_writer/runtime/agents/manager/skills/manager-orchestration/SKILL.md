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
| chapter-reviewer | `production/chapters/<id>.review.json` |
| independent-verifier | `production/chapters/<id>.answers.json` |
| solution-comparator | `production/chapters/<id>.verification.json` |

## Disk layout

| Path | Role |
|---|---|
| `production/research.json` | Research (sources + topics) |
| `production/book-plan.json` | Curriculum plan |
| `production/editorial-state.json` | Manager-owned cross-chapter memory |
| `production/chapters/<id>.json` | Chapter + exercises |
| `production/chapters/<id>.review.json` | Cross-chapter editorial review |
| `production/chapters/<id>.answers.json` | Blind solve |
| `production/chapters/<id>.verification.json` | Grade |
| `production/book.json` | Assembled book |
| `build/<slug>.pdf` | Measured PDF |

Before re-running a stage, `ls production/`. Resume from disk when a good artifact exists.

## Phase order (mandatory)

### A — Goal
Chat only. Clarify audience, depth, scope, and length with the learner. Collect HTTPS
URLs. Do not start research until they confirm the scope in chat.

Pass the agreed audience, depth, scope, and target pages in the curriculum tool input.
Page count constrains scope, never typography. Reserve 25–35% for figures, exercises,
answers, front matter, and bibliography; budget remaining prose at roughly 350–500 words
per page. Typical exercise density is 2–3 per compact chapter, 3–5 intermediate, and 5–8
deep, with focused, applied, and synthesis practice rather than one omnibus prompt.

### B — Research
`research-architect` → `research.json` (web search; follow `$research`).
The architect owns finding real sources.

### C — Curriculum
`curriculum-architect` → `book-plan.json` (include `target_pages` from the agreed
scope). Inspect chapter order, total target words, exercise counts/assessment briefs, and
visual purposes before accepting it. If the plan is weak, edit the JSON or re-run the
architect with a short fix brief—no separate auditor/repair agents.

Create `production/editorial-state.json` after accepting the plan:

```json
{
  "accepted_chapter_refs": [],
  "established_concepts": [],
  "terminology": {},
  "running_system_state": [],
  "reusable_examples": [],
  "open_threads": []
}
```

### D — Per chapter (plan order)
1. `chapter-writer` → chapter JSON **and** its figures (author calls the diagrammer)
2. `chapter-reviewer` → `production/chapters/<id>.review.json`
3. **Editorial gate (mandatory — never skip)** — open the review file yourself.
4. `independent-verifier` — answer-free exercises only (blind QA; you commission this)
5. `solution-comparator` → `production/chapters/<id>.verification.json`
6. **Exercise QA gate (mandatory — never skip)** — open the verification file with Shell/file
   editor and inspect every `verdicts[].decision`:

#### Editorial gate

The reviewer is evidence, not the decision-maker. Inspect `decision`, `summary`, and every
note. Confirm the draft fits the full plan and accepted book, not only its own chapter brief.

If the decision is `revise`, do **not** run exercise QA. Call `chapter-writer` with the
chapter id and every note's `category`, full `evidence`, and full `requested_change`. Re-run
`chapter-reviewer` and reopen the file. Allow at most two editorial rewrite cycles after the
initial draft. If it still does not approve, stop and report the unresolved notes.

If the decision is `approve`, proceed to blind exercise QA.

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
Chapter is QA-clear. Update `production/editorial-state.json` before continuing:

- append the chapter id to `accepted_chapter_refs`
- add concepts and canonical terms the reader can now rely on
- record how the shared running system changed
- record examples later chapters may reuse without re-explaining
- keep only still-open promises in `open_threads`

Then continue to the next chapter (or publish when all planned chapters are clear).

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

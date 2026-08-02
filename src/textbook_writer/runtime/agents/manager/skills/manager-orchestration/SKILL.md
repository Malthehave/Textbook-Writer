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
| `production/publication-report.json` | Measured page fit from the latest compile |
| `build/<slug>.pdf` | Measured PDF |

Before re-running a stage, `ls production/`. Resume from disk when a good artifact exists.
After any specialist writes a canonical JSON artifact, call
`validate-production-artifact` on that path before advancing. A validation failure belongs
to that producing stage: give the exact error back to the same specialist and validate its
correction. Never defer schema or figure-path validation until PDF publication.

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
The architect owns finding real sources. Validate `production/research.json`.

### C — Curriculum
`curriculum-architect` → `book-plan.json` (include `target_pages` from the agreed
scope). Inspect chapter order, total target words, exercise counts/assessment briefs, and
visual purposes before accepting it. If the plan is weak, edit the JSON or re-run the
architect with a short fix brief—no separate auditor/repair agents.
Validate `production/book-plan.json` before creating editorial state, then validate
`production/editorial-state.json`.

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
2. Validate the chapter JSON and referenced figure files
3. In one response, call `chapter-reviewer` and `independent-verifier`; the SDK runs both
   concurrently with a maximum tool concurrency of two.
4. Validate and open the review. Keep the blind answers speculative until editorial approval.
5. **Editorial gate (mandatory — never skip)**.
6. On approval, freeze prose/figures and update `production/editorial-state.json`.
7. In one response, call `solution-comparator` for this chapter and, if another chapter
   remains, `chapter-writer` for the next chapter. They touch different files and run
   concurrently.
8. Validate and open the verification JSON; apply the exercise QA gate.

Never call two chapter writers concurrently. The next writer may start only after the
previous chapter is editorially approved and recorded in editorial state.

#### Editorial gate

The reviewer is evidence, not the decision-maker. Inspect `decision`, `summary`, and every
note. Confirm the draft fits the full plan and accepted book, not only its own chapter brief.

If the decision is `revise`, discard the speculative answers and do not compare them. Call
`chapter-writer` with the
chapter id and instruct it to read the existing chapter JSON and its `.review.json` from the
shared filesystem, revise the chapter in place, and preserve everything unaffected by the
notes. The review file is the canonical brief. Re-run reviewer and blind verifier together,
then reopen the review. Allow at most two editorial rewrite cycles after the initial draft.
If it still does not approve, stop and report the unresolved notes.

If the decision is `approve`, freeze prose and figures. Immediately update editorial state:

- append the chapter id to `accepted_chapter_refs`
- add concepts and canonical terms the reader can now rely on
- record how the shared running system changed
- record examples later chapters may reuse without re-explaining
- keep only still-open promises in `open_threads`

The next chapter may now be drafted while this chapter's comparator runs.

#### If any verdict is `reject` or `revise`
Do not publish, but an already-running next-chapter draft may finish because it depends only
on frozen editorial content.

1. Open the verification file and confirm every non-`approve` verdict is actionable.
2. Call `chapter-writer` with the chapter id and exact existing chapter and
   `.verification.json` paths. Tell it to modify only exercises, answers, and reasoning;
   frozen prose, sections, figures, terminology, and bridges must remain unchanged.
3. Re-run `independent-verifier` (fresh answers file).
4. Re-run `solution-comparator`.
5. Re-open `.verification.json`. Repeat the gate.

**Cap:** at most **two** rewrite cycles per chapter after the first compare (initial write +
up to two fix passes). If still not all-`approve`, stop and tell the learner which exercises
failed and why (quote `notes`) — do not publish that chapter’s broken exercises.

#### If every verdict is `approve`
Chapter is QA-clear. Continue reviewing the next draft or publish when every planned chapter
has both editorial approval and an all-approve verification file.

Never treat a comparator tool status line as proof of approval — only the verification JSON
on disk counts.

### E — Publish
Only after **every** planned chapter has an all-`approve` `.verification.json` on disk.
Call `build-textbook-pdf`. It writes the PDF and `production/publication-report.json`.

The requested page count is a target, not an exact hard limit. Accept any actual page count
inside the report's inclusive 15%-tolerance range. This range uses whole-page outward
rounding, so a six-page target accepts five through seven pages.

If the measured result is outside the range:

1. Keep the compiled PDF; it remains a usable artifact while fit is corrected.
2. Read `production/publication-report.json` and identify the smallest scope correction.
3. Call the affected `chapter-writer` with the existing chapter path and report path. Ask
   for a targeted in-place length revision, preserving approved substance and figures.
4. Re-run editorial review and blind exercise QA for every changed chapter, update
   editorial state, and compile again.

Allow at most two publication-fit correction cycles. If the PDF still falls outside the
range, stop revising, give the learner the latest PDF, and report its measured page count
and deviation honestly. Never withhold an already compiled PDF solely because it missed
the target.

Do not estimate page consumption from PNG pixels, HTML dimensions, word-count arithmetic,
or a reviewer's visual guess. Only the measured publication report determines page fit.

## Error recovery

- **missing sources / bad source_refs** → architect put URLs in `source_refs`. Retry with:
  “Use source_id strings in source_refs; put URLs only on sources[].url.”
- **two independent hosts** → need a second hostname, not a second path on the same site.
- **missing production/X** → prior stage not on disk; run the prior step, don’t invent JSON.

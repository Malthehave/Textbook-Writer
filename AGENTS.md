# Textbook Writer agent guide

Manager-led compiler: one learner-facing OpenAI Agents SDK manager, specialists via
`Agent.as_tool()`. Agents use sandbox Shell + Filesystem (+ Skills). The manager and
research architect also get `WebSearchTool`; formal subject evidence still belongs in the
research architect's validated artifact. PDF compile is the manager FunctionTool
`build-textbook-pdf`.
This file is the only maintained product doc.

## Deployment model

**One chat = one book directory (kept).**

Compose mounts host `output/books` → `/books`. Each chat owns
`/books/<session-id>/` (created empty on **New book**, never wiped when you start
another). That path is the sandbox `manifest.root` for the chat — the agent only
sees that directory. The UI artifact tree labels it `/book`.

PDF: `/books/<session-id>/build/<title-slug>.pdf`. Default model: `gpt-5.6-luna`.

## Learner persona

A durable who-they-are profile lives at `output/learner/persona.md` (outside any book
session). Edit it in the UI under **Profile**, or interview the persona agent there
(web search + shared `output/learner/` sandbox). The interviewer builds a self-contained
360° dossier (synopsis, identity, work experience/CV, education, projects, strengths,
durable gaps, how they learn)—extracting substance from sources rather than link-dumping
so later agents need not re-search the learner. Not book goals, time horizons, or
curriculum. The manager loads that file for personalization; book topic, depth, length,
and learning goals are still agreed in each textbook chat.

## Entry

```bash
npm run build   # first time / Docker deps change
npm run dev     # day-to-day → http://localhost:3000 (API :8000, hot-reload)
```

Or without Docker: set `TEXTBOOK_BOOKS_ROOT=output/books`, then
`uv run uvicorn textbook_writer.api.app:app --reload --port 8000` and
`cd frontend && npm run dev`.

### Debug a failed UI run

When the chat banner is useless, inspect session logs (not the UI):

```bash
# latest sessions
curl -s localhost:8000/api/sessions | python -m json.tool | head

# stream + error tail for one session
curl -s localhost:8000/api/sessions/<session-id>/debug | python -m json.tool | less

# or files on disk
ls output/books/<session-id>/
docker compose logs api --tail 200
```

Prefer `docker compose logs api` for live runs.

## Pipeline (manager-ordered)

1. Chat → agree audience, depth, scope, length with the learner
2. `research-architect` → `production/research.json` (web search; real HTTPS sources)
3. `curriculum-architect` → book plan (`target_pages` from agreed scope)
4. Per chapter, use a bounded wavefront: chapter-writer → reviewer → manager editorial gate
   → blind verifier. Do not solve exercises for editorially rejected prose. Editorial
   approval freezes prose/figures and advances `production/editorial-state.json`; then the
   solution comparator for that chapter runs in parallel with the next chapter writer.
   Exercise QA may change only exercises/answers.
   Never run two chapter writers concurrently. Tool concurrency is capped at two.
5. `build-textbook-pdf` → assemble `book.json` + Typst PDF and write
   `production/publication-report.json`. Accept the requested page target within an
   inclusive ±15% measured tolerance (whole-page bounds round outward). If outside, make
   at most two targeted scope revisions, re-run gates for changed chapters, and compile
   again; never withhold the latest compiled PDF solely because fit still misses.

Manager tools: `build-textbook-pdf`, research-architect, curriculum-architect, chapter-writer,
chapter-reviewer, independent-verifier, solution-comparator, and
`validate-production-artifact`, plus hosted `web_search`. The manager validates each canonical JSON artifact
immediately after its producer returns, so PDF publication only assembles and compiles
already-valid state. The chapter-writer owns html-diagram-author as a nested tool (author +
illustrator); each figure uses one stable HTML path and one stable PNG path.
`production/chapters/<id>.answers.json` validates against `BlindAnswers`, not
`ProductChapter`. Plans targeting 6 pages or fewer are capped at 1 chapter, 3 exercises,
and 1 visual; 7–8 page plans are capped at 2 chapters, 6 exercises, and 2 visuals.
Web discovery uses hosted `WebSearchTool` on the research architect only.

Specialists are `Agent.as_tool()` calls: each invocation is a **fresh nested run** with the
tool’s `input` string as the user message (no prior specialist chat history). Shared
memory is that chat’s book directory plus whatever brief the manager puts in `input`.
Only one manager run may be active per chat so overlapping requests cannot race on those
shared files.

Nested specialist streams are captured through `Agent.as_tool(on_stream=...)`. Visible
assistant text, reasoning summaries, and nested tool calls/results are streamed into the
parent chat UI, persisted in the sessions database by outer tool-call ID, and restored into
the expandable tool row on history load. Raw events are available at
`/api/sessions/<session-id>/subagent-events`.

## Non-negotiable rules

1. Treat a book as a compiled artifact, not one long model response.
2. Agree scope with the learner in chat before research.
3. One manager owns the learner conversation; specialists are tools, never handoffs.
4. Keep research, prose, verification, and publishing as separate stages with files on disk.
5. Canonical book state is `output/books/<session-id>/` (one directory per chat; kept).
6. Ground facts in real researched sources (`source_refs` on `research.json`)—do not invent URLs.
7. Personalize path/examples/depth—not factual standards.
8. Author semantic content; no visual styling instructions in manuscript JSON.
9. Publishing is deterministic (Typst). Figures are HTML→PNG only—no Typst diagram graphs, no GPT Image.
10. Verify exercises without exposing the proposed solution on the first pass.
11. Prefer explicit schemas over embeddings as source of truth.
12. Do not expand the component catalogue without a documented need.
13. Model memory is never evidence of curriculum completeness—research externally.
14. Curriculum must cover the agreed scope; do not invent a complete plan from model memory.
15. Page counts come only from the measured publication report.
16. Runtime skills live under each agent’s `skills/` dir; they are not subject evidence.
17. Manager instructions enforce a mandatory phase order (goal → research →
 curriculum → per-chapter write/diagram/editorial-review/exercise-verify → publish). Skills never expand
 phase permissions.

## Skills

Each agent owns `runtime/agents/<role>/skills/<name>/SKILL.md`. Attach only that agent’s
skills via the SDK `Skills` capability (not a shared skills tree). Nested `as_tool()` runs
use the same session book directory as the manager.

| Agent | Skill | Nested tools |
|---|---|---|
| manager | `manager-orchestration` | research, curriculum, chapter-writer, chapter-reviewer, exercise QA, PDF |
| research-architect | `research` | — |
| curriculum-architect | _(none)_ | — |
| chapter-writer | `textbook-prose` | `html-diagram-author` |
| chapter-reviewer | _(none)_ | — |
| html-diagram-author | `technical-html-diagram` | — |
| independent-verifier | `exercise-verification` | — |
| solution-comparator | `exercise-verification` | — |

## Layout

| Path | Role |
|---|---|
| `src/textbook_writer/api/` | FastAPI routes (`app.py`) + store / history / stream helpers |
| `frontend/` | Vite React + Tailwind + `@ai-sdk/react` chat UI |
| `runtime/agents/<role>/` | One folder per agent: `prompt.md`, `agent.py`, optional `skills/` |
| `runtime/agents/manager/` | Learner-facing manager (`prompt.md`, wiring) |
| `runtime/workspace_tools.py` | FunctionTool `build-textbook-pdf` |
| `runtime/pdf.py` + `textbook.typ` | Typst render + compile |
| `models/` | Plain Pydantic models (research, plan, chapter, book) |
| `docker-compose.yml` | `api` + `frontend` (`output/books` → `/books`) |

```bash
uv run pytest
```

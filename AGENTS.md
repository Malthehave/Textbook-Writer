# Textbook Writer agent guide

Manager-led compiler: one learner-facing OpenAI Agents SDK manager, specialists via
`Agent.as_tool()`. Agents use sandbox Shell + Filesystem (+ Skills). The manager and
research architect also get `WebSearchTool`; formal subject evidence still belongs in the
research architect's validated artifact. PDF compile is the manager FunctionTool
`build-textbook-pdf`.
This is the canonical product/runtime document. `README.md` is the operator quickstart,
`DESIGN.md` is the UI design reference, and `frontend/README.md` contains frontend-only
development notes; when they disagree with this file, this file wins.

## Deployment model

**One chat = one book directory (kept).**

Compose mounts host `output/books` → `/books`. Each chat owns
`/books/<session-id>/` (created empty on **New book**, never wiped when you start
another). That path is the sandbox `manifest.root` for the chat — the agent only
sees that directory. New books start with `input/`, `state/`, `build/`, and
`production/`. The UI artifact tree labels the session root `/book`.

PDF: `/books/<session-id>/build/<title-slug>.pdf`; separate solution mode also writes
`<title-slug>-solutions.pdf`. All agents default to `gpt-6-astra`, including the
persona interviewer. Reasoning is medium for the manager, diagrams, and persona interview;
high for research, curriculum, lead authorship, reader-experience editing, exercise QA,
and compiled-publication review. Routing uses the selected base model throughout;
explicit overrides use `TEXTBOOK_MODEL_<ROLE>`. The legacy `TEXTBOOK_MODEL_ROUTING`
setting no longer changes routing.

Chat history is split deliberately: the global session index and nested-agent event log
live in `output/ui-sessions.sqlite`, while each manager conversation lives in
`output/books/<session-id>/state/product-sessions.sqlite`. Per-book token and estimated
API cost data is written to `state/usage.json`. Only one run may be active for a given
session in the current API process.

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

Put `OPENAI_API_KEY` in `.env` (copy `.env.example`; never commit `.env`). Then:

```bash
npm run build   # first time / Docker deps change
npm run dev     # day-to-day → http://localhost:3000 (API :8000, hot-reload)
```

Or without Docker: install the Typst version pinned by `Dockerfile.api`, then run
`uv sync`, `uv run playwright install chromium`, set
`TEXTBOOK_BOOKS_ROOT=output/books`, and start
`uv run uvicorn textbook_writer.api.app:app --reload --port 8000`. In another shell run
`cd frontend && npm install && npm run dev`.

### Debug a failed UI run

When the chat banner is useless, inspect session logs (not the UI):

```bash
# latest sessions
curl -s localhost:8000/api/sessions | python -m json.tool | head

# session metadata + persisted error tail
curl -s localhost:8000/api/sessions/<session-id>/debug | python -m json.tool | less

# canonical pipeline progress and per-book API usage
curl -s localhost:8000/api/sessions/<session-id>/progress | python -m json.tool
curl -s localhost:8000/api/sessions/<session-id>/usage | python -m json.tool

# or files on disk
ls output/books/<session-id>/
docker compose logs api --tail 200
```

Prefer `docker compose logs api` for live runs.

## Pipeline (manager-ordered)

1. Chat → agree audience, starting point, depth, scope, capability, length, and mode.
   Recommend `quality-slice` for iteration: one 1,500–2,200 word chapter, 2–3 exercises,
   at most one visual, and 8–10 target pages. `short-book` is 2–3 chapters, 5,000–8,000
   words, and 18–28 target pages. `prototype` is a legacy-resume mode.
2. `research-architect` → `production/research.json` (web search; real HTTPS sources)
3. `lead-author` owns learning architecture and prose in one run, writing
   `production/book-plan.json` plus every chapter. Modern plan slices specify the reader's
   starting point, conceptual obstacle, intuition bridge, worked-example progression,
   mechanisms, misconceptions, concrete demonstration, and progressive practice.
4. `html-diagram-author` separately attaches each planned HTML/PNG figure after prose.
5. `reader-experience-editor` reads the complete learner-visible manuscript and writes
   `production/manuscript.review.json`. Narrative coherence, explanatory depth, paragraph
   flow, sentence rhythm, concept scaffolding, example continuity, practice progression,
   and voice consistency must each score at least 4/5 before prose freezes.
6. For frozen chapters: independent-verifier → `.answers.json` → solution-comparator →
   `.verification.json`. Blind answers are the canonical publication key; chapter draft
   answers exist only for comparison. Different chapters may use two tool slots concurrently.
7. `build-textbook-pdf` → assemble `book.json`, compile Typst, and write
   `production/publication-report.json` with measured page fit plus deterministic checks for
   placeholders, missing answers, blank pages, and title defects. Accept only the inclusive
   ±15% range and `quality_passed`; separate solution mode emits a companion PDF.
8. `publication-reviewer` visually inspects every compiled page image once and writes
   `production/publication.review.json`. Material defects route back to the owning stage.

Manager tools: `inspect-pipeline-state`, `forecast-textbook-pages`, `build-textbook-pdf`,
research-architect, lead-author, html-diagram-author, reader-experience-editor,
independent-verifier, solution-comparator, publication-reviewer, and
`validate-production-artifact`, plus hosted `web_search`. Code derives phase state and exact
next actions from disk rather than asking the manager to reconstruct them from chat. The
manager validates each canonical JSON artifact immediately after its producer returns.
Diagram authoring is a separate manager tool and atomically attaches one stable HTML/PNG
pair after chapter prose commits.
`production/chapters/<id>.answers.json` validates against `BlindAnswers`, not
`ProductChapter`. Every mode uses one complete-manuscript reader gate rather than
per-chapter reviews and `editorial-state.json`; existing unscored manuscripts return to the
reader-experience editor once before publication.
The manager may use hosted `web_search` to inspect learner-provided URLs, clarify current
context, or answer a quick learner-facing question. Subject discovery and all evidence
eligible for the book belong to the research architect and validated `research.json`.

Specialists are `Agent.as_tool()` calls: each invocation is a **fresh nested run** with the
tool’s `input` string as the user message (no prior specialist chat history). JSON producers
own format and normally make one `commit-production-artifact` call; that call validates and
includes compact schema help in any `invalid=` response. The manager gates with
`validate-production-artifact` and
keeps re-invoking specialists on failure—it does not edit schemas and must not abandon a
chapter/book after one failed rewrite. Shared memory is that chat’s book directory plus
whatever brief the manager puts in `input`. Only one manager run may be active per chat so
overlapping requests cannot race on those shared files.

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
11. Publish only independently solved answers; never render the author's draft key.
12. Prefer explicit schemas over embeddings as source of truth.
13. Do not expand the component catalogue without a documented need.
14. Model memory is never evidence of curriculum completeness—research externally.
15. Curriculum must cover the agreed scope; do not invent a complete plan from model memory.
16. Forecasts are early warnings; final page counts come only from the measured report.
17. Runtime skills live under each agent’s `skills/` dir; they are not subject evidence.
18. Manager instructions enforce a mandatory phase order (goal → research → lead-author
 manuscript → diagram attachment → reader-experience review → exercise QA → publish →
 compiled review). Skills never expand
 phase permissions.

## Teaching lessons from learner feedback

Teach unfamiliar representations before using them: label relevant order, direction,
place values, units, and symbols; explain a worked transformation and a plausible novice
misreading. Correct notation alone is not sufficient explanation. Prefer examples that
expose ambiguities, and use labelled tables or diagrams where they improve understanding.
Authorship and editorial review both enforce this through their role skills.

## Skills

Each agent owns
`src/textbook_writer/runtime/agents/<role>/skills/<name>/SKILL.md`. Attach only that
agent’s skills via the SDK `Skills` capability (not a shared skills tree). Nested
`as_tool()` runs use the same session book directory as the manager.

| Agent | Skill | Nested tools |
|---|---|---|
| manager | `manager-orchestration` | research, lead-author, diagram, reader review, exercise QA, PDF |
| research-architect | `research` | — |
| curriculum-architect (unregistered compatibility module) | `narrative-architecture` | — |
| chapter-writer (`lead-author` tool) | `textbook-prose` | — |
| chapter-reviewer (`reader-experience-editor` tool) | `editorial-review` | — |
| html-diagram-author | `technical-html-diagram` | — |
| independent-verifier | `exercise-verification` | — |
| solution-comparator | `exercise-verification` | — |
| publication-reviewer | — | render publication preview |

## Layout

| Path | Role |
|---|---|
| `src/textbook_writer/api/` | FastAPI routes (`app.py`) + store / history / stream helpers |
| `frontend/` | Vite React + Tailwind + `@ai-sdk/react` chat UI |
| `src/textbook_writer/runtime/agents/<role>/` | One folder per agent: `prompt.md`, `agent.py`, optional `skills/` |
| `src/textbook_writer/runtime/agents/manager/` | Learner-facing manager (`prompt.md`, wiring) |
| `src/textbook_writer/runtime/workspace_tools.py` | Production artifact contracts, validation gates, and PDF FunctionTool |
| `src/textbook_writer/runtime/pdf.py` + `textbook.typ` | Typst render + compile |
| `src/textbook_writer/runtime/quality.py` | Component forecast + deterministic compiled-PDF QA |
| `src/textbook_writer/runtime/model_routing.py` | Per-role model selection and overrides |
| `src/textbook_writer/runtime/usage_ledger.py` | Per-book token and estimated API-cost ledger |
| `src/textbook_writer/models/` | Pydantic contracts for research and production artifacts |
| `output/ui-sessions.sqlite` | Global UI session index and persisted nested-agent events |
| `output/learner/` | Durable learner persona, outside book sessions |
| `output/books/<session-id>/` | Canonical retained state for one book chat |
| `docker-compose.yml` | `api` + `frontend` (`output/books` → `/books`) |

```bash
npm test                 # wrapper for uv run pytest
uv run --frozen pytest   # direct, lockfile-respecting run
cd frontend && npm run build
```

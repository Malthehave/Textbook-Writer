# Textbook Writer agent guide

Manager-led compiler: one learner-facing OpenAI Agents SDK manager, specialists via `Agent.as_tool()`, deterministic acquire/assemble/publish. Canonical state lives in the book workspace, not chat history. This file is the only maintained product doc.

## Entry

```bash
npm run build   # first time / Docker deps change
npm run dev     # day-to-day → http://localhost:3000 (API :8000, hot-reload)
```

Or without Docker: `uv run uvicorn textbook_writer.api.app:app --reload --port 8000` and `cd frontend && npm run dev`.

### Debug a failed UI run

When the chat banner is useless, inspect session logs (not the UI):

```bash
# latest sessions
curl -s localhost:8000/api/sessions | python -m json.tool | head

# stream + error tail for one session
curl -s localhost:8000/api/sessions/<session-id>/debug | python -m json.tool | less

# or files on disk
ls output/books/draft-*/state/ui-stream.jsonl output/books/draft-*/state/ui-errors.log
docker compose logs api --tail 200
```

`state/ui-stream.jsonl` = SSE events we emitted; `state/ui-errors.log` = tracebacks.

Creates `output/books/draft-<hash>/`, learns the goal in chat, renames to `output/books/<title-slug>/` on publish. PDF: `build/<title-slug>.pdf`. Default model: `gpt-5.6-luna`.

## Pipeline (manager-ordered)

1. Chat → approved `ProductionBrief`
2. Research dossier + research audit
3. `acquire_and_freeze` → immutable archive + source packets
4. Curriculum plan + coverage audit
5. Chapter write + HTML diagram author (PNG assets only)
6. Independent exercise verify + continuity
7. `assemble_book` (quality gates + citation ledger)
8. `publish_book` (Typst PDF; measured page counts only)

Web discovery uses the SDK hosted `WebSearchTool` in the research scout only. Leads are not evidence—evidence exists only after HTTPS acquire/freeze/extract.

## Non-negotiable rules

1. Treat a book as a compiled artifact, not one long model response.
2. Discover curriculum with the learner before freezing a production brief.
3. One manager owns the learner conversation; specialists are tools, never handoffs.
4. Keep research, prose, verification, and publishing as separate stages with typed I/O.
5. Canonical book state is versioned workspace artifacts under `output/books/`.
6. Ground facts in frozen sources; keep claim-to-source provenance.
7. Personalize path/examples/depth—not factual standards.
8. Author semantic content; no visual styling instructions in manuscript JSON.
9. Publishing is deterministic (Typst). Figures are HTML→PNG only—no Typst diagram graphs, no GPT Image.
10. Verify exercises without exposing the proposed solution on the first pass.
11. Prefer explicit schemas over embeddings as source of truth.
12. Do not expand the component catalogue without a documented need.
13. Model memory is never evidence of curriculum completeness—research externally.
14. Audit coverage/omissions before approving a production plan.
15. Page/link/figure counts come only from the measured publication report.
16. Runtime skills are pinned markdown under `skills/`; they are not subject evidence.
17. Manager instructions enforce a mandatory phase order (goal → brief → research/freeze →
    curriculum → per-chapter write/diagram/verify → assemble → publish). Skills never expand
    phase permissions.

## Skills

Pinned `skills/<name>/SKILL.md` trees attach via the Agents SDK `Skills` capability on
`SandboxAgent` init (not by inlining markdown into `instructions`). Nested `as_tool()` runs
pass a sandbox `RunConfig` (`UnixLocalSandboxClient`) so the capability materializes.

| Skill | Used by | Basis |
|---|---|---|
| `textbook-prose` | chapter-writer | Google Technical Writing One + developer-tutorial craft |
| `exercise-verification` | independent-verifier, solution-comparator | Answer-hidden solve + fair grading |
| `technical-html-diagram` | html-diagram-author | Sparse print-legible HTML figures |

## Layout

| Path | Role |
|---|---|
| `api/` | FastAPI: sessions, artifacts, PDF, Agents SDK → AI SDK UI stream |
| `frontend/` | Vite React + Tailwind + `@ai-sdk/react` chat UI |
| `runtime/agents/<role>/` | One folder per agent: `prompt.md` + `agent.py` |
| `runtime/agents/manager/` | Learner-facing manager (`prompt.md`, wiring, session) |
| `runtime/workspace_tools.py` | Acquire / assemble / publish |
| `models/` | Plain Pydantic models (dossier, plan, chapter, book, acquire) |
| `research/` | HTTPS acquire → freeze → extract → packets |
| `publishing/` | `ProductBook` → Typst → measured PDF |
| `skills/` | Pinned craft skills (`SKILL.md`) for SandboxAgent capabilities |
| `docker-compose.yml` | `api` + `frontend` |

```bash
uv run pytest
```

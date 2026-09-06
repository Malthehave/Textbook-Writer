# Textbook Writer

Textbook Writer is a manager-led textbook compiler. A learner-facing OpenAI Agents SDK
manager commissions research, a single lead author, reader-experience editing,
exercise-verification, diagram, and compiled-publication specialists, then publishes a
measured Typst PDF. The default fast path is a quality slice: one substantial 1,500–2,200
word chapter with a complete teaching progression, 2–3 exercises, at most one visual, and
an 8–10 page target. It is short enough to iterate on without collapsing into an outline.

Each chat owns a retained directory under `output/books/<session-id>/`. Research,
curriculum, chapters, reviews, blind answers, verification results, publication reports,
and the compiled PDF are files on disk rather than claims held only in chat history.

See [AGENTS.md](AGENTS.md) for the authoritative pipeline, artifact contracts, and
non-negotiable production rules. See [DESIGN.md](DESIGN.md) for the UI design reference.

## Run (hot reload)

Requirements: Docker with Compose and `OPENAI_API_KEY` in `.env` (copy `.env.example`;
never commit the populated file). Typst, Chromium, and PDF tooling ship in the API image.

```bash
npm run build   # first time / when Docker deps change
npm run dev     # day-to-day (hot reload)
```

- UI: http://localhost:3000 (Vite HMR)
- API: http://localhost:8000 (uvicorn `--reload`)

Also: `npm run down`, `npm run logs`, `npm test`. Edit `frontend/` or `src/` locally; containers pick up changes.

Creating **New book** makes an empty `input/`, `state/`, `build/`, and `production/`
workspace. Starting another book does not delete earlier sessions. The UI provides the
manager chat, production progress, live nested-specialist activity, an artifact browser,
PDF preview, per-book usage estimates, and the durable learner profile editor/interview.

All agents default to GPT-6 Astra (`gpt-6-astra`), including the learner persona
interviewer. Reasoning is medium for the manager, diagrams, and persona interview;
research, authorship, manuscript/publication review, and exercise QA use high.
Routing uses the selected base model throughout. Explicit per-role overrides remain
available as `TEXTBOOK_MODEL_<ROLE>` (for example, `TEXTBOOK_MODEL_WRITER=gpt-6-astra`).
The legacy `TEXTBOOK_MODEL_ROUTING` setting is no longer needed; it does not change routing.

### Without Docker

PDF publish needs `typst` (match `TYPST_VERSION` in `Dockerfile.api`). Prefer Docker so
`/books` matches the deployment model in `AGENTS.md`.

```bash
brew install typst poppler
uv sync
uv run playwright install chromium
TEXTBOOK_BOOKS_ROOT=output/books uv run uvicorn textbook_writer.api.app:app --reload --port 8000

cd frontend && npm install && npm run dev
```

Vite proxies `/api` → `:8000`.

## State and outputs

| Path | Contents |
|---|---|
| `output/ui-sessions.sqlite` | Session index and persisted nested-agent events |
| `output/learner/persona.md` | Cross-book learner profile |
| `output/books/<session-id>/production/` | Canonical validated book artifacts |
| `output/books/<session-id>/state/` | Manager chat history and usage ledger |
| `output/books/<session-id>/build/` | Latest learner PDF and optional solution manual |

The API exposes read-only session endpoints for messages, artifacts, progress, usage,
debug information, and the current PDF. The browser consumes these endpoints directly.

## Debugging

```bash
npm run debug
curl -s localhost:8000/api/sessions | python -m json.tool
curl -s localhost:8000/api/sessions/<session-id>/debug | python -m json.tool
curl -s localhost:8000/api/sessions/<session-id>/progress | python -m json.tool
```

A run interrupted by an API reload or dropped browser stream may still have valid work in
the session directory. Inspect canonical artifacts and progress before rerunning a stage.

## Verification

```bash
npm test
cd frontend && npm run build
```

## Layout

| Path | Role |
|---|---|
| `src/textbook_writer/api/` | FastAPI + Agents SDK → AI SDK stream |
| `frontend/` | Vite React + Tailwind + `@ai-sdk/react` |
| `src/textbook_writer/runtime/agents/` | Manager, specialists, prompts, and role-local skills |
| `src/textbook_writer/runtime/workspace_tools.py` | Artifact validation and PDF publication tools |
| `src/textbook_writer/runtime/pdf.py` | Typst assembly and PDF compile |
| `src/textbook_writer/runtime/quality.py` | Page forecast and compiled-artifact checks |
| `src/textbook_writer/runtime/model_routing.py` | Role-specific model routing |
| `src/textbook_writer/models/` | Research and production Pydantic contracts |
| `docker-compose.yml` | Dev API + frontend with live reload |

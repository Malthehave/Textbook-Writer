# Textbook Writer

One manager agent compiles a source-grounded textbook: specialists via `Agent.as_tool()`,
plus a deterministic `build-textbook-pdf` tool. Each chat keeps its own directory under
`output/books/<session-id>/` (never wiped when you start another).

## Run (hot reload)

Needs `OPENAI_API_KEY` in `.env` (see `.env.example`). Typst ships in the API image.

```bash
npm run build   # first time / when Docker deps change
npm run dev     # day-to-day (hot reload)
```

- UI: http://localhost:3000 (Vite HMR)
- API: http://localhost:8000 (uvicorn `--reload`)

Also: `npm run down`, `npm run logs`, `npm test`. Edit `frontend/` or `src/` locally; containers pick up changes.

### Without Docker

PDF publish needs `typst` (match `TYPST_VERSION` in `Dockerfile.api`). Prefer Docker so
`/books` matches the deployment model in `AGENTS.md`.

```bash
brew install typst
uv sync
TEXTBOOK_BOOKS_ROOT=output/books uv run uvicorn textbook_writer.api.app:app --reload --port 8000

cd frontend && npm install && npm run dev
```

Vite proxies `/api` → `:8000`.

## Layout

| Path | Role |
|---|---|
| `src/textbook_writer/api/` | FastAPI + Agents SDK → AI SDK stream |
| `frontend/` | Vite React + Tailwind + `@ai-sdk/react` |
| `runtime/agents/` | Manager + specialists |
| `runtime/pdf.py` | Typst PDF compile |
| `docker-compose.yml` | Dev API + frontend with live reload |

See `AGENTS.md` for the pipeline. Run tests with `uv run pytest`.

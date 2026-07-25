# Textbook Writer

One manager agent compiles a source-grounded textbook: specialists via `Agent.as_tool()`, deterministic acquire/assemble/publish tools.

## Run (hot reload)

Needs `OPENAI_API_KEY` in `.env` (see `.env.example`). Typst and poppler ship in the API image, so PDF publish works out of the box.

```bash
npm run build   # first time / when Docker deps change
npm run dev     # day-to-day (hot reload)
```

- UI: http://localhost:3000 (Vite HMR)
- API: http://localhost:8000 (uvicorn `--reload`)

Also: `npm run down`, `npm run logs`, `npm test`. Edit `frontend/` or `src/` locally; containers pick up changes.

### Without Docker

PDF publish shells out to `typst` and `pdftoppm`, so install them first — match the
image's pinned Typst (`TYPST_VERSION` in `Dockerfile.api`) to keep output identical:

```bash
brew install typst poppler
```

```bash
uv sync
uv run uvicorn textbook_writer.api.app:app --reload --port 8000

cd frontend && npm install && npm run dev
```

Vite proxies `/api` → `:8000`.

## Layout

| Path | Role |
|---|---|
| `src/textbook_writer/api/` | FastAPI + Agents SDK → AI SDK stream |
| `frontend/` | Vite React + Tailwind + `@ai-sdk/react` |
| `runtime/agents/` | Manager + specialists |
| `docker-compose.yml` | Dev API + frontend with live reload |

```bash
uv run pytest
```

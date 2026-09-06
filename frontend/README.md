# Textbook Writer frontend

The frontend is the compile console for Textbook Writer. It is a React 19, TypeScript,
Vite, Tailwind CSS, and AI SDK UI that talks to the FastAPI backend through `/api`.

Product and pipeline behavior is documented in [`../AGENTS.md`](../AGENTS.md). The visual
system is documented in [`../DESIGN.md`](../DESIGN.md).

## Development

From the repository root, the normal development path is:

```bash
npm run dev
```

This starts both Docker services and serves the UI at http://localhost:3000. Source files
under `frontend/` are mounted into the container and update through Vite HMR.

To run only the frontend against an API already listening on port 8000:

```bash
cd frontend
npm install
npm run dev
```

`VITE_API_PROXY` controls the proxy target and defaults to `http://localhost:8000` outside
Compose. Compose sets it to `http://api:8000`.

## Checks

```bash
npm run lint
npm run build
```

The production build runs TypeScript project compilation before Vite bundling.

## UI responsibilities

- List and create retained book sessions.
- Restore manager chat history and nested specialist transcripts.
- Stream assistant text, reasoning summaries, tool calls, errors, and cost updates.
- Poll canonical production progress while a run is active.
- Browse text and image artifacts and preview the latest PDF.
- Edit or interview the durable cross-book learner persona.

The backend remains authoritative for session state, artifacts, progress, and publication.
Do not infer completion or page counts solely from transient stream state.

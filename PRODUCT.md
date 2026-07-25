# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary user: a self-directed learner teaching themselves a subject. They open a book session, chat with one manager agent to discover and approve a production brief, then receive a personalized textbook PDF for their own study path.

## Product Purpose

Textbook Writer compiles a source-grounded textbook through an interactive chat with a single manager agent. Success means the learner gets a published PDF whose facts are grounded in frozen sources, with exercises independently verified, and with measured publication metrics—not an ungrounded long-form chat reply.

## Positioning

A book is a compiled artifact: research leads become evidence only after HTTPS acquire/freeze/extract; specialists run as tools under one manager (never handoffs); assemble and publish are deterministic (Typst PDF; HTML→PNG figures only). Neighboring “chat writes a book” products cannot truthfully claim the same provenance, staged verification, and measured publish path.

## Operating Context

- Entry: web UI via `docker compose up` (Vite React + FastAPI streaming, hot reload)
- Session creates `output/books/draft-<hash>/`, renames to `output/books/<title-slug>/` on publish; PDF at `build/<title-slug>.pdf`
- Pipeline (manager-ordered): production brief → research + audit → acquire/freeze → curriculum + coverage audit → chapter write + diagram author → independent exercise verify + continuity → assemble → publish
- Web UI surfaces: sessions list, streaming chat (text / reasoning / tools), artifact browser, PDF preview split-pane
- Canonical state lives in versioned workspace artifacts under `output/books/`, not chat history
- Product engineering doc: `AGENTS.md`

## Capabilities and Constraints

Confirmed:

- One learner-facing manager; specialists via `Agent.as_tool()`
- Typed stage I/O; explicit schemas over embeddings as source of truth
- Claim-to-source provenance; personalize path/examples/depth—not factual standards
- No visual styling instructions in manuscript JSON; publishing is deterministic Typst
- Figures are HTML→PNG only (no Typst diagram graphs, no GPT Image)
- Exercise verification without exposing the proposed solution on the first pass
- Page/link/figure counts come only from the measured publication report
- Runtime skills are pinned under `skills/`; they are not subject evidence
- Requires OpenAI API key; Typst and Poppler for local PDF tooling

Open / undecided:

- No product-specific accessibility standard yet
- No public branding system beyond the product name
- Scope of multi-user / hosted product vs local personal tool not decided beyond current local web+CLI deployment

## Brand Commitments

- Product name: **Textbook Writer**
- No logo, wordmark, or binding visual brand system yet
- Voice in product docs is direct, technical, and process-precise (manager / compile / freeze / assemble / publish)

## Evidence on Hand

- Runnable web UI and CLI; agent pipeline and tests in-repo
- Example / draft book workspaces under `output/books/` when present
- Do not invent customers, testimonials, benchmarks, pricing, or press

## Product Principles

1. Compile, don’t improvise — a textbook is a staged, typed artifact with quality gates.
2. Evidence before claims — leads are not sources until acquire/freeze/extract.
3. One conversation owner — the manager owns the learner; specialists never take the mic.
4. Personalize the path, not the facts — depth and examples adapt; standards stay grounded.
5. Measure what you claim — publication counts come from the build report, never model estimates.

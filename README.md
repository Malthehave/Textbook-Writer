# Textbook Writer

Make books with Codex. Open this repository, describe what you want to learn, and ask
Codex to use the `write-textbook` skill. Codex writes and researches the book, delegates
specialist reviews, and uses local tools to publish a reviewed PDF.

There is no web application, OpenAI Agents SDK, API key, or model-calling Python service.
Use your normal Codex subscription sign-in; book work consumes its available usage.

## Setup

Install Python 3.12+, uv, Typst 0.15.1, and Poppler (`pdftoppm`). On macOS, Typst and
Poppler are available through Homebrew. Then:

```sh
uv sync --frozen
uv run playwright install chromium
uv run textbook doctor
```

Math conversion uses the pinned MiTeX package emitted by md2typst. The first math build
may need internet access to populate Typst's package cache. HTML figures must be
self-contained: network and external local resource requests are blocked.

## Make a book

In Codex, ask:

> Use write-textbook to create a five-page introduction to how an AI chip computes a
> weighted sum. I am a hardware beginner. Use labelled diagrams and worked examples,
> explain notation before using it, and include two exercises with verified answers.

Codex confirms the scope, creates a retained book folder, researches, writes, illustrates,
reviews, verifies exercises, compiles, and visually reviews all pages. One author owns the
narrative; specialist subagents get bounded assignments. See [AGENTS.md](AGENTS.md).

The blind solver receives an answer-free question packet in a fresh subagent context,
without inherited author conversation, and is instructed to read only that packet.
Shared-workspace subagents do not enforce filesystem isolation; use a restricted workspace
when available. This is a review protocol, not a security guarantee. Any solve exposed to
the author's draft answers must be discarded and repeated.

## Local commands

```sh
uv run textbook init --book output/books/my-book
uv run textbook status --book output/books/my-book
uv run textbook render-figure --book output/books/my-book --id figure-id
uv run textbook verification-packet --book output/books/my-book --destination /tmp/my-book-solver
uv run textbook record-review --book output/books/my-book --stage reader --review /tmp/reader.json
uv run textbook build --book output/books/my-book
uv run textbook preview --book output/books/my-book
uv run textbook validate --book output/books/my-book
uv run --frozen pytest
```

`status` reports the next required stage and review hashes; it is useful during partial
work. `validate` returns a nonzero exit code until the entire book is ready for delivery.
Reviewers must return the hash of the inputs they inspected. Changes to manuscript,
answers, PDF or preview images invalidate the affected approvals. `build` requires fresh
reader and answer-comparison approvals; `preview` renders all candidate pages. A final
publication review is still required after compilation.

Outputs: `build/book.pdf`, optional `build/book-solutions.pdf`, `build/report.json`, and
page images under `build/previews/`. Page targets include companion pages when separate
solutions are selected. A five-page target with ±15% tolerance requires five measured pages.

## Repository

- `.agents/skills/write-textbook/`: discoverable workflow and teaching guidance.
- `src/textbook_writer/cli.py`: local commands.
- `src/textbook_writer/workflow.py`: artifact validation and review freshness.
- `src/textbook_writer/publishing.py`: Markdown/Typst, HTML/PNG and PDF previews.
- `output/books/`: retained books, ignored by Git.
- `output/learner/persona.md`: optional learner context, ignored by Git.

Existing books from the old application are preserved but use a different artifact format.
Do not run the new CLI on an old book directory. The old application is recoverable from
Git checkpoint `0bf1ce6`. See [the rebuild plan](docs/codex-rebuild-plan.md) for rationale.

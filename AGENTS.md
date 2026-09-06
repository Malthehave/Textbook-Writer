# Textbook Writer — Codex workflow

This repository is a local book workshop. Codex owns the learner conversation and writes
books directly with its tools and subagents. There is no OpenAI API key, Agents SDK,
server, frontend, or programmatic model client in the book workflow.

## When the user asks for a book

Read `.agents/skills/write-textbook/SKILL.md`. Agree the learning promise before research,
using information already provided. Create one retained `output/books/<book-id>/` directory.
Load `output/learner/persona.md` if present; book goals belong in the book brief.
Use `uv run textbook status --book <path>` to recover from disk and follow the next action.
Never overwrite another book or interpret old application artifacts as the new format.

## Delegation

Use Codex subagents for research, diagrams, complete-manuscript reader review, blind
exercise solving, answer comparison, and compiled-page review. One author owns the
manuscript; the primary Codex agent may author it directly. Fresh specialist briefs contain
explicit inputs, output paths, learner context and acceptance criteria. Do not give an
independent reviewer the author's conclusions as instructions. Parallelize only independent
work with disjoint outputs; never allow two agents to write the same artifact.

Blind solvers receive only an answer-free packet in a fresh context (no inherited
conversation), with instructions to read only that packet. Never expose proposed answers
on the first pass. Shared-workspace subagents are NOT filesystem-isolated; do not claim
this is a security boundary. Use a separate restricted workspace when available. If the
solver reads draft answers, discard that solve and rerun with a fresh context.

## Gates and evidence

Order: brief → researched evidence → plan/manuscript → figures → reader review → independent
answers → comparison → compile → visual publication review → delivery.
Use local CLI validation and content hashes. Reviews must name the input hash they actually
reviewed. Never stamp stale approval onto changed content, invent independent approval,
or mark publication approved merely because compilation succeeded.
Subject claims need real researched sources. Model memory is not curriculum evidence.
Publish independently solved answers only, never the author's proposed answer key.
Render every final page for visual review and approve the exact PDF revision.

## Teaching

Explain unfamiliar representations before relying on them. Label relevant directions,
place values, units, axes, indices and symbols. Walk through transformations and address a
plausible novice interpretation when it changes the result. Choose examples that reveal
ambiguities instead of hiding them through symmetry. Introduce concrete meaning before
formal notation; keep one worked example progressing through the book.
Plan illustrations around conceptual obstacles, with no arbitrary one-figure chapter cap.
Captions and prose must explain what to notice. Review clarity separately from accuracy.

## Local tooling

- `uv sync --frozen` installs local publishing dependencies.
- `uv run textbook --help` lists commands and `uv run textbook doctor` checks dependencies.
- `uv run --frozen pytest` runs tests.
- Typst 0.15.1, Poppler (`pdftoppm`), and Playwright Chromium are publishing dependencies.
- Run `uv run playwright install chromium` once after setup when necessary.
- All Python tooling does local deterministic processing, never model calls.
- Keep generated books, credentials and machine state out of Git. Track repository skills.

The previous application is preserved on remote main at `0bf1ce6`. The rebuild plan in
`docs/codex-rebuild-plan.md` records rationale; this file and the live CLI define the new workflow.

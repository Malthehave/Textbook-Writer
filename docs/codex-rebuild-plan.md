# Codex-only Textbook Writer rebuild

Status: initial Codex-only implementation completed on `codex/codex-only-workflow`.
This document preserves the original proposal; AGENTS.md, the skill and CLI define current behavior.
The live implementation uses fresh-context, packet-only blind solving as a review protocol;
it explicitly does not claim filesystem-enforced isolation. A learner-reviewed pilot is still pending.
Checkpoint: `c888539` preserves the API-based application and current teaching lessons.

## Product and boundaries

Open this repository in Codex and ask for a book. The current Codex conversation owns
scope, decisions, writing coordination, feedback, and delivery. Codex writes the book
using local files and its available tools, with fresh subagents for specialist work.
There is no application server, custom chat UI, OpenAI Agents SDK, model API client,
API key, or script that launches a hidden model service. Subscription authentication
belongs to Codex; its ordinary usage limits still apply.

Rebuild the application structure from scratch in this repository. Port only useful,
tested publishing logic and lessons into the new structure; do not preserve runtime
abstractions merely for compatibility. Retain existing output directories untouched.
The checkpoint remains the recovery path for old code and old artifact support.

## Proposed repository

- `AGENTS.md`: concise product contract, delegation rules, stage order, book isolation,
  evidence standards, publication gates, and commands.
- `.agents/skills/write-textbook/SKILL.md`: discoverable end-to-end book workflow.
- Skill references: scoped research, authorship, illustration, reader review,
  exercise verification, and publication briefs loaded only when needed.
- `src/textbook_writer/`: fresh local CLI, artifact contracts, state/gate logic,
  HTML diagram rendering, Typst compilation, and PDF inspection helpers.
- `templates/`: Typst publication templates and local diagram resources.
- `tests/`: meaningful contract, stale-state, answer-isolation, and publishing tests.
- `output/books/<book-id>/`: retained book workspaces.
- `output/learner/persona.md`: optional durable learner profile, loaded by Codex.
- `README.md`: local dependency installation and how to request/resume a book.

Narrow `.gitignore` so repository skill sources are tracked while local tooling state,
secrets, caches, and generated books remain ignored. No new frontend is required.

## Book artifacts

Use a small versioned manifest and readable manuscript files instead of one giant chat
response. Proposed per-book layout:

- `brief.json`: confirmed audience, prerequisites, scope, page target, answer mode.
- `research.json`: validated evidence, source IDs, URLs, supported claims and gaps.
- `plan.json`: learning progression, chapter IDs, objectives, example continuity,
  expected misconceptions, illustrations and approximate page allocations.
- `chapters/<id>.md`: prose with a documented minimal set of semantic references.
- `exercises/<id>.json`: questions, stable IDs, dependencies, and author draft answers.
- `figures/`: HTML/PNG pairs, captions, alt text and attachment metadata.
- `reviews/`: reader, answer-comparison, and compiled-page reviews.
- `verification/`: exported answer-free inputs and independently produced answers.
- `build/`: assembled Typst, PDF, preview images, measured publication report.

Finalize Markdown-to-Typst handling in the first vertical slice. Preserve math, tables,
references and figures without allowing visual styling directives into teaching prose.
Do not rebuild a large component catalogue or generic content-management framework.

## Local commands (proposed, not implemented)

Use `uv run textbook <command> --book <path>` as the common interface:

- `init`: create a unique book directory without overwriting an existing book.
- `validate`: validate a named artifact and cross-file references.
- `status`: derive the next permissible actions and stale gates from files.
- `verification-packet`: export questions plus only necessary definitions/data.
- `render-figure`: turn authored HTML into PNG, with local math/fonts available.
- `build`: enforce gates, compile Typst, and measure output quality/page fit.
- `preview`: render every compiled page for visual review.

Commands do deterministic local work only. They never request model completions.
Compilation may produce a candidate PDF for inspection; delivery additionally requires
approval tied to that exact PDF hash. Changing upstream content invalidates downstream
approvals through input hashes, not timestamps or conversational promises.

## Codex and subagent responsibilities

1. Codex confirms the learning promise and records the brief. Avoid repeating questions
   already answered. Use a stable book ID, not a dependency on Codex task metadata.
2. Research subagent gathers primary sources with available search/browsing tools and
   records claim-level evidence. Validate before authorship. Report inaccessible or
   insufficient evidence rather than filling gaps from memory.
3. One lead author owns the plan and entire manuscript for coherence. Codex can author
   directly or delegate this bounded stage. Do not split simultaneous prose authorship
   across chapters by default.
4. Diagram subagent authors purposeful illustrations after relevant prose exists.
   Independent figures may run in parallel with disjoint output ownership.
5. Reader-review subagent checks the complete manuscript against the learner's actual
   starting knowledge. It returns precise repairs under the existing eight-dimension
   scorecard; all dimensions must reach 4/5 before freezing the manuscript.
6. Blind solver receives a fresh context and an answer-free packet. A separate comparison
   pass receives both answer sets. Publish only the independently produced answers.
7. Codex runs deterministic compilation and quality checks, then a publication reviewer
   visually inspects every rendered page. Material defects return to their owner.
8. Codex delivers the reviewed PDF and a short explanation of scope and any limitations.

Stage permissions belong to the orchestrator and CLI gates. A subagent cannot approve
its own output as a substitute for a required independent review. Use bounded briefs,
explicit input/output paths, and no two writers to the same artifact concurrently.

### Blind verification is a real implementation requirement

Do not fork the author's conversation into the solver. Do not give the solver the full
book directory containing draft answers. Export a separate temporary workspace containing
only the questions and indispensable context, and start a fresh-context solver there.
Validate the export for answer leakage. Establish whether the chosen Codex subagent
surface can enforce filesystem isolation; a prompt alone is not an access boundary.
If it cannot, use a supported fresh Codex invocation with restricted workspace permissions
and subscription sign-in for this stage. Do not claim enforced blindness until tested.
This is the only potential extra invocation, not a replacement application orchestrator.

## Teaching changes carried forward

- Introduce unfamiliar representations before using them: label direction, place values,
  units, axes, symbols and indices as relevant to the learner.
- Explain transformations, including why each step is valid. Address a plausible novice
  interpretation when it would change the result. Choose examples that expose ambiguity.
- Start with concrete meaning, then formal notation, then application to the running example.
- Plan visuals around conceptual obstacles. A five-page pilot can contain several compact
  illustrations; remove the global one-figure-per-chapter assumption in the new contracts.
- Review every illustration for a teaching purpose, labels, integration and legibility.
- Keep one coherent example progressing through the work. Exercises should test transfer,
  not demand prerequisites first explained in their solutions.

The binary incident is an acceptance example: 010 is symmetrical and hides reversed
place values; 011 versus 110 reveals them. A beginner should see labelled columns before
being expected to decode either representation. Do not inject binary lessons into other subjects.

## Implementation sequence and acceptance

1. Establish the fresh CLI, artifact contracts, minimal skill and AGENTS.md on a new
   `codex/` branch. Explicitly replace the old SDK orchestration requirements.
2. Port the Typst/HTML rendering logic into SDK-free modules. Keep the local fonts and
   math assets needed for reproducible rendering. Pin dependencies and document setup.
3. Implement status, validation, content hashes, verification packet export and gates.
4. Add role briefs and Codex delegation workflow, then remove the old API/UI application,
   Docker startup path and model billing code once the new vertical slice is functional.
5. Regenerate “How an AI Chip Computes One Neuron” as a five-page pilot with the new
   explanatory standard and several purposeful compact illustrations. Scope this run
   explicitly before generation. Preserve the original PDF for comparison.
6. Verify every stage left valid artifacts, stale approvals block delivery, the author's
   key never enters the solver packet or final PDF, and every final page was reviewed.
7. Confirm local tools and book generation require no `OPENAI_API_KEY` and have no
   `openai`/`openai-agents` dependency. Confirm model work occurs through Codex.
8. Have the learner compare clarity and visuals. Then exercise multi-chapter continuity
   and optional separate solutions before commissioning the long Qwen book.

Page targets remain measured goals. At a five-page target, the existing inclusive ±15%
rule accepts exactly five integer pages; revise content/layout rather than silently
claiming six pages fits. Reconsider page tolerance separately if learner feedback warrants it.

## Validation strategy

Carry forward useful deterministic tests; remove tests specific to the retired UI/API.
Test actual parsing, compilation, references, missing answers, stale approvals, and
workspace isolation rather than matching prose strings. Run the small real book as the
behavioral acceptance test: valid JSON alone cannot prove intuitive teaching.

## Official capability references

- Subscription versus API authentication: https://learn.chatgpt.com/docs/auth
- Repository skills and scripts: https://learn.chatgpt.com/docs/build-skills
- Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents

These establish the available building blocks. The layout, commands and migration
sequence above are this project's proposed design, not claims about built-in Codex APIs.

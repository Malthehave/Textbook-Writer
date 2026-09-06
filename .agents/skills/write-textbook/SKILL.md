---
name: write-textbook
description: Create or revise a source-grounded textbook in this repository using Codex authorship, specialist subagents, and local PDF tools. Use for book requests and retained-book revisions, not ordinary subject questions.
---

# Write a textbook with Codex

You own the learner conversation and may write the manuscript yourself. Use Codex tools
and subagents for research, authorship and judgment. Python only validates and publishes
local artifacts. No API key, Agents SDK, or replacement model-calling script is needed.

Read [artifact contracts](references/artifacts.md) before authoring files and
[teaching guidance](references/teaching.md) for planning, writing and reader review.

1. Agree audience, starting knowledge, desired capability, scope, length and solution
   mode from the conversation. Do not ask again for already provided information.
2. Run `uv run textbook init --book output/books/<unique-id>` and record brief.json.
3. Delegate primary-source research. Require opened sources and claim-level evidence,
   not invented URLs or curriculum from memory. Validate before writing.
4. One author owns the plan, complete manuscript and exercises. Delegate planned HTML
   illustrations with disjoint output paths, render them, and inspect their PNGs.
5. Run status. Give a fresh reader-review subagent the learner brief, teaching guidance,
   complete manuscript/figures and current reader hash. Require all eight scores ≥4.
   Record approval with record-review; repair concrete issues and repeat when necessary.
6. Export verification-packet outside the book. Delegate only that packet to a fresh
   solver context with no inherited author chat. Instruct it to read only the packet,
   solve independently, and report missing context. Shared-workspace subagents are not
   filesystem-isolated: this is a review protocol, not a security guarantee. Prefer a
   restricted workspace when available; discard any solve exposed to draft answers.
7. Import independent answers into verification/answers.json. Delegate comparison against
   the questions and author draft answers, then record review with its comparison hash.
8. Run build and preview. Have a publication-review subagent inspect every page image,
   including companion solutions if present. Record the exact publication input hash,
   decision, notes and inspected page numbers. Text extraction is not visual inspection.
9. Run status again and deliver only when ready. Link the reviewed PDF and retain files.

Give specialists explicit input/output paths, the learner's starting point, acceptance
criteria and current hash. Independent work can run concurrently; two authors cannot edit
one artifact. Reviews belong to the version actually inspected: never attach old approval
to a freshly calculated hash. Blind answers are the sole publication answer key.

Use `uv run textbook --help` for local commands. Status derives next actions from disk.
A successful compile is a candidate, not permission to deliver. At five target pages,
the inclusive ±15% measured fit gate accepts exactly five integer pages. Narrow scope to
save time; do not skip stages or compress away prerequisite explanations.

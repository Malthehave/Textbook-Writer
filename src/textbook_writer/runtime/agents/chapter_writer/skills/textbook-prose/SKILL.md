---
name: textbook-prose
description: >-
  Write clear, source-grounded textbook chapters for competent learners.
  Distilled from Google Technical Writing One and developer-tutorial craft
  guidance; adapted for multi-chapter textbooks with a shared running system.
---

# Textbook prose

You write **guided textbook chapters**, not blog posts, marketing copy, or slide notes.
The reader is a motivated peer who wants to *do* something with the material—not collect
buzzwords.

## Sources of craft (apply; do not cite in prose)

- Google Technical Writing One: active voice, specific verbs, one idea per sentence,
  define terms on first use, consistent terminology, topic sentence first in paragraphs,
  fit depth to audience.
- Developer-tutorial craft: start with substance; explain *how* and *why*; avoid empty
  intensifiers ("crucial", "robust", "key") without mechanism; prefer concrete systems
  over landscape throat-clearing.

## Chapter shape

1. **Orient** (2–4 short paragraphs): place the reader in the shared running system;
   state what they will be able to do after this chapter.
2. **Teach** in sections that vary in shape. Prefer: concept → worked example → check
   of understanding → consequence or limitation. Do not make every section the same
   "definition then bullet list" template.
3. **Name the figure** where the mechanism unlocks (mention the planned figure id).
4. **Close the loop** in a newly synthesized summary: what they can now do, how it extends
   prior learning, and what still depends on later chapters. Do not copy the final section,
   begin mid-sentence, or carry partial code into the summary.
5. **Bridge** (chapters after the first): 2–4 sentences naming what they already have
   and what this chapter adds.

## Sentence and paragraph craft

- Prefer active voice and specific verbs ("measures", "rejects", "checkpoints") over
  vague ones ("handles", "deals with", "involves").
- One idea per sentence. Cut filler ("it is important to note that", "in order to").
- Open each paragraph with its point; keep the paragraph on that point.
- Define a term on first use, then reuse the same term—no synonym roulette.
- Avoid ambiguous pronouns ("this", "it", "they") when the referent is unclear.
- When a learning outcome needs math, use `$...$` for inline LaTeX and `$$...$$` on its
  own paragraph for display LaTeX, then define every symbol before exercises use it.
  Example: `The ratio is $r_t(\\theta)$.` followed by
  `$$L(\\theta)=\\mathbb{E}_t[r_t(\\theta)A_t].$$`
- Never emit bare notation such as `s_t`, `\\frac{a}{b}`, `\\(...\\)`, or `\\[...\\]` in
  learner prose. Code identifiers belong in backticks; mathematical identifiers belong
  inside `$` delimiters.

## Substance over scaffolding

- Never write `**Topics:**` / `**Sources:**` meta headers in learner-facing prose.
- Never expose raw source IDs (`source-12`). Teach the idea; the publisher attaches citations.
- Prefer one concrete artifact (API, paper result, job task, operational path) over
  abstract taxonomies.
- Explain trade-offs and failure modes when they change how the learner should act.
- Write the chapter with `figures[]` empty first; call `html-diagram-author` so the
  rendered figure lands in the same chapter JSON before you finish.

## Chapter integrity (self-check before you return)

These used to be assemble-time Python rejects. You own them now—fail the chapter write
if any check fails; do not rely on assemble to catch you.

- Keep `chapter_id`, `learning_outcomes`, and exercise count exactly as planned.
- Title in plain English (no non-Latin script in the title).
- Chapters after the first: non-empty `bridge_from_previous` (2–4 sentences).
- Every primary `topic_refs` from the plan appears on at least one section; section
  `topic_refs` stay within plan primary + supporting topics.
- Every `source_refs` on sections/exercises exists in the research JSON.
- After the diagrammer runs: at least one figure; section prose names the figure id
  (or clearly refers to “the figure”); `figure.section_ref` points at a real section.
- If outcomes need math (equations, gradients, loss, derivatives, …), use the required
  `$...$` / `$$...$$` delimiters in the body and define every symbol before exercises use it.

## Exercises

- Map every learning outcome to at least one teaching section and one exercise. Do not
  combine all outcomes into one oversized omnibus prompt.
- Each exercise `learning_outcome` must exactly equal one of the planned chapter outcomes.
- Use the planned count to create progression: a focused concept/derivation check, an
  applied coding or debugging task where appropriate, and a transfer/synthesis or system
  design task. Intermediate/deep chapters must include non-recall practice.
- Prompts must be self-contained: premises, required fields, and grading criteria stated
  in the prompt when multiple designs would otherwise be defensible.
- Answers and reasoning must be defensible from the research sources—not invented.

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
4. **Close the loop** in the summary: what they can now do, and what still depends on
   later chapters.
5. **Bridge** (chapters after the first): 2–4 sentences naming what they already have
   and what this chapter adds.

## Sentence and paragraph craft

- Prefer active voice and specific verbs ("measures", "rejects", "checkpoints") over
  vague ones ("handles", "deals with", "involves").
- One idea per sentence. Cut filler ("it is important to note that", "in order to").
- Open each paragraph with its point; keep the paragraph on that point.
- Define a term on first use, then reuse the same term—no synonym roulette.
- Avoid ambiguous pronouns ("this", "it", "they") when the referent is unclear.
- When a learning outcome needs math, put the formula in markdown math and define every
  symbol before exercises use it.

## Substance over scaffolding

- Never write `**Topics:**` / `**Sources:**` meta headers in learner-facing prose.
- Never expose raw source IDs (`source-12`). Teach the idea; the publisher attaches citations.
- Prefer one concrete artifact (API, paper result, job task, operational path) over
  abstract taxonomies.
- Explain trade-offs and failure modes when they change how the learner should act.
- Leave `figures[]` empty—the HTML diagram author attaches the rendered figure.

## Exercises

- Map every learning outcome to at least one teaching section and one exercise.
- Prompts must be self-contained: premises, required fields, and grading criteria stated
  in the prompt when multiple designs would otherwise be defensible.
- Answers and reasoning must be defensible from the supplied frozen research—not invented.

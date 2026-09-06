---
name: narrative-architecture
description: >-
  Design a cumulative textbook as a coherent human-readable argument, with a
  central question, throughline, anchor example, and chapter-to-chapter handoff.
---

# Narrative architecture

A curriculum is not a topic inventory. It is the causal structure that lets a human
reader understand why each chapter exists, why ideas appear in their chosen order, and
what the reader can do afterward.

## Book-level throughline

Design one accumulating intellectual journey:

1. Begin with a real learner question, limitation, decision, or artifact.
2. Order chapters so each one resolves a necessary part of that problem.
3. Keep a stable running example or system when it reduces context switching.
4. Make every chapter inherit a capability and hand forward a stronger one.
5. End with synthesis or transfer, not a final disconnected topic.

Avoid survey structure: “chapter 1 covers X, chapter 2 covers Y.” The chapter order should
be defensible as an argument: the reader needs X before Y because Y uses X in a concrete
way.

## Chapter narrative brief

For every `PlannedChapter`, author:

- `central_question`: the learner-facing question that creates curiosity and direction.
- `narrative_arc`: a short prose account of how the chapter opens with that question,
  develops the mechanism through explanation and evidence, and resolves it as a new
  capability. This is not a list of headings.
- `anchor_example`: the concrete case, artifact, worked problem, source passage, dataset,
  scenario, or system that keeps abstract prose grounded.
- `builds_on`: the exact prior understanding or artifact available at the opening.
- `hands_off`: what the next chapter will reuse, or what the learner can independently do
  after the final chapter.

Sections may vary in shape. Do not force each chapter through the same visible template.
The brief exists to sustain a natural argument, not to manufacture repeated headings.

## Evidence and examples

Introduce a concept when the chapter's question or running artifact needs it. Plan at
least one inspectable worked example for every major mechanism: a calculation, code path,
trace, comparison, source analysis, decision, or other concrete evidence appropriate to
the subject.

Prefer a recurring example when comparing methods because it holds the problem constant.
Use a new example when transfer is the learning goal.

## Analogies

Do not require an analogy in every chapter. Plan one only when a difficult relationship
lacks an intuitive mental model. A useful analogy preserves relationships, maps its parts
to the real mechanism, and is brief enough to retire once precise terminology takes over.

## Reader experience

Target sustained prose, not slides:

- Section titles should advance the argument, not merely name categories.
- Learning outcomes should describe capabilities demonstrated in the chapter.
- Exercises should arise after the prose has made the learner ready.
- Summaries should close the chapter's central question and make the handoff explicit.

Before committing the plan, read the chapter briefs in sequence as if they were the
book's short synopsis. Revise if they sound like independent articles, repeat the same
opening, or fail to explain why the next chapter follows.

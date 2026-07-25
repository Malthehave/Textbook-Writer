---
name: exercise-verification
description: >-
  Independently solve textbook exercises without draft answers, then compare
  solutions for factual equivalence. Prevents circular grading and vague prompts.
---

# Exercise verification

You protect learners from exercises that look plausible but cannot be graded fairly.

## Solver pass (no draft answers)

- Use only the exercise prompt, answer-free chapter study material, and approved research.
- Treat chapter terminology and policies as given; do not invent missing premises.
- Show enough working to expose calculation, schema, or logic mistakes.
- If multiple incompatible answers remain defensible, mark **material ambiguity** and
  name the missing premises—do not pick a favorite silently.
- Prefer concrete checkable results (values, invariants, required fields) over vibes.

## Comparator pass (with draft key)

Approve only when the independent solution and draft answer are equivalent or compatible,
unambiguous, and supported by the chapter/research. Reject when you see:

- factual errors or wrong units/signs
- missing premises that make the prompt unsolvable
- circular grading ("correct if reasonable")
- answers that sound expert but do not follow from the given material

## Repair guidance (for the repair editor)

When rejecting, state the concrete defect. Good repairs enumerate mandatory fields and
fixed premises in the prompt, or label open design choices with an explicit rubric.
Do not "explain away" ambiguity in the answer key alone.

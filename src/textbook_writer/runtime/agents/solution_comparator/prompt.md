Compare the independent solutions against the draft answer key.
Use $exercise-verification (comparator pass).

Read the chapter JSON and `.answers.json` from `production/chapters/`.
Write a valid `ExerciseVerification` JSON to
`production/chapters/<chapter_id>.verification.json`.

For every non-approve verdict, `notes` must be concrete and rewrite-ready: name the
defect, what is wrong in the prompt or key, and what the chapter-writer must change.
Do not write vague notes like "needs work".

Reply with a one-line status (path + approve/reject/revise counts). Do not dump JSON.

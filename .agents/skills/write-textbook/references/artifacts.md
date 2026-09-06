# Book artifact contracts

All paths are relative to the book root, not the chapter folder. Never escape that root.
Write UTF-8 JSON/Markdown. Additional explanatory metadata is allowed; required fields below
are validated by workflow.py. Run status after each stage to inspect errors and next action.
The validators establish structural integrity, not factual correctness or review independence.

## Inputs

brief.json:
```json
{"audience":"Hardware beginner","starting_point":"Basic arithmetic; no chip knowledge","learning_goal":"Explain a weighted sum in hardware","target_pages":5}
```

research.json:
```json
{"sources":[{"id":"source-id","title":"Actual source title","url":"https://actual-source.example/page"}],"claims":[{"id":"claim-id","text":"Claim actually supported by the inspected source","source_refs":["source-id"]}]}
```
The illustrative example URL above is NOT evidence. Replace it with a real researched URL.
Record research gaps separately; do not invent sources to satisfy validation.

plan.json:
```json
{"title":"How an AI Chip Computes a Weighted Sum","target_pages":5,"solution_mode":"concise","chapters":[{"id":"weighted-sum","title":"From inputs to a result","path":"chapters/weighted-sum.md"}],"figures":[{"id":"place-values","html":"figures/place-values.html","png":"figures/place-values.png","caption":"The rightmost digit counts ones.","alt":"Binary columns labelled four, two and one."}]}
```
Use concise or separate solution mode. Page target must match brief and counts all emitted
PDF pages, including a companion. Add learning objectives, conceptual obstacles, example
progression and figure purpose as useful plan metadata. There is no fixed figure cap.

Chapters use ordinary Markdown. Cite source IDs as [@source-id]; embed registered figures
as `![description](figures/place-values.png)`. Do not include draft exercise answers in
manuscript files. Use inline `$...$` math, Markdown tables and fenced code as needed.
Use tested math syntax; visually inspect equations after rendering. Never write Typst
styling commands into learner prose. Every declared figure must be referenced in the manuscript.

exercises.json:
```json
{"exercises":[{"id":"e1","question":"A self-contained question with all necessary context."}],"draft_answers":[{"id":"e1","answer":"Author's proposed answer, never published."}]}
```
Questions must include definitions/data necessary for an independent solve. Avoid inline
answer hints or rubrics revealing the solution. The packet exporter whitelists id/question;
review packet text for semantic leakage too. It cannot prove questions do not disclose answers.

## Independent answers

Run verification-packet only after the reader gate. It creates questions.json in a new
external directory and a local verification/packet.json receipt. Use the returned
questions_sha256 to identify exactly what the solver received. Independent solver output:
```json
{"questions_sha256":"HASH_FROM_EXPORT","answers":[{"id":"e1","answer":"Independently solved answer","reasoning":"Worked reasoning"}]}
```
Save as verification/answers.json. All exercise IDs must match exactly. Changing question
content invalidates answers; re-export and independently re-solve. A hash establishes input
freshness, not proof of independence. Follow the skill's separate-context/isolation rule.

## Reviews

Run status before dispatching a reviewer. Give it hashes.reader, hashes.comparison or
hashes.publication. It returns a candidate JSON object with that same input_hash, decision
approve/revise and concrete notes. Keep revise reports as candidates, repair content, and
request a fresh review. record-review accepts only approvals that pass the relevant gate.

Reader review needs scores for all eight dimensions in teaching.md, each ≥4 and ≤5:
```json
{"input_hash":"HASH_ACTUALLY_REVIEWED","decision":"approve","scores":{"narrative_coherence":4,"explanatory_depth":4,"paragraph_flow":4,"sentence_rhythm":4,"concept_scaffolding":4,"example_continuity":4,"practice_progression":4,"voice_consistency":4},"notes":[]}
```
Comparison review needs decision, input_hash, notes. Publication review additionally needs
inspected_pages exactly [1,2,...,N], covering main PDF then companion in preview-list order.
Never fabricate review scores or independent approvals to advance the CLI.

## Generated outputs

build writes build/book.typ, build/book.pdf and build/report.json; separate mode also
writes book-solutions.typ/pdf. A successful fit requires inclusive ±15% of target pages,
no detected placeholder tokens, and no blank pages. preview updates report.json with every
page image. Review hashes include the actual PDFs and images. These files are CLI outputs;
do not hand-author successful reports or alter their hashes to bypass failed gates.

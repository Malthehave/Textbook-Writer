---
name: research
description: >-
  How to author source-grounded research JSON for a textbook. Use when searching
  the web, proposing topics, or building Research JSON. Covers ID vs URL rules
  and two-host grounding.
---

# Research

You produce **grounded research**, not textbook prose. Search the web. Never invent URLs.
Call `describe-production-artifact` if you need the field contract. Persist only via
`commit-production-artifact` and repair until it returns `valid=`.

## Schema contract

Top-level fields only:

- `research_id` (string)
- `title` (string)
- `audience` (string — not an object)
- `learning_goal` (string)
- `sources` (array of ProductSource)
- `topics` (array of ResearchedTopic)
- `exclusions` (array of string)
- `unresolved` (array of string)

`ProductSource`: `source_id`, `title`, `url` (https), `authority`
(`primary|official|review|canonical|practitioner`), `credibility_rationale`,
`publication_year` (int or null).

`ResearchedTopic`: `topic_id`, `title`, `rationale` (string or null), `learning_outcomes`,
`source_refs` (source_ids only), `claims`.

`GroundedClaim`: `claim_id`, `statement`, `source_refs`, `limitation` (string or null).

No extra keys. Do not wrap audience/persona details in nested objects.

## Hard rules (enforced by commit/validate)

1. **IDs ≠ URLs.** Every `source` has a short `source_id` and a separate `url`.
   Topic and claim `source_refs` list **only those `source_id` values**.
2. **Two independent hosts per topic.** Cited sources must resolve to at least two
   different hostnames. Two paths on the same host count as one host.
3. **Practice signal.** Among each topic’s `source_refs`, at least one source must have
   `authority` of `official` or `practitioner`.
4. **Claim closure.** Every claim’s `source_refs` must be a non-empty subset of that
   topic’s `source_refs`.
5. **HTTPS only.** All source URLs must be `https://`.
6. **At least two sources per topic.**

## Walkthrough

1. Read any prior `production/research.json` from disk and revise from it when present.
2. Web-search the learner goal, artifact URLs, official docs, and practice sources.
   For targets of 8 pages or fewer, research only the few topics that fit the compact
   primer and record adjacent breadth in `exclusions` instead of expanding `topics[]`.
3. Build `sources[]` first.
4. Build `topics[]` with ID-only `source_refs` and grounded `claims[]`.
5. Self-check every topic against the hard rules, then
   `commit-production-artifact(path="production/research.json", content=<json>)`.
6. On `invalid=`, fix and recommit until `valid=`. Put residual uncertainty in
   `unresolved` / `exclusions`—never invent evidence.

## Anti-patterns

- Putting URLs in `source_refs`
- Citing only path variants on one host as “two sources”
- Inventing URLs or treating vague search snippets as enough — open and verify real pages
- Emitting `audience` as an object, or adding `schema_version` / `kind` / other extras
- Returning to the manager before `commit-production-artifact` returns `valid=`

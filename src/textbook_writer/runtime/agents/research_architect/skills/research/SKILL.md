---
name: research
description: >-
  How to author source-grounded research JSON for a textbook. Use when searching
  the web, proposing topics, or building Research JSON. Covers ID vs URL rules
  and two-host grounding.
---

# Research

You produce **grounded research**, not textbook prose. Search the web. Never invent URLs.

## Hard rules (you enforce — no Python gate)

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

## Walkthrough (`Research`)

1. Read any prior `production/research.json` from disk and revise in place when present.
2. Web-search the learner goal, artifact URLs, official docs, and practice sources.
   For targets of 8 pages or fewer, research only the few topics that fit the compact
   primer and record adjacent breadth in `exclusions` instead of expanding `topics[]`.
3. Build `sources[]` first (`source_id`, `title`, `url`, `authority`, `credibility_rationale`).
4. Build `topics[]` with ID-only `source_refs` and grounded `claims[]`.
5. Self-check every topic against the hard rules, then **write** `production/research.json`.
6. Put residual uncertainty in `unresolved` / `exclusions`—never invent evidence.
7. Reply with a one-line status only—do not paste the research JSON into the tool return.

## Anti-patterns

- Putting URLs in `source_refs`
- Citing only path variants on one host as “two sources”
- Inventing URLs or treating vague search snippets as enough — open and verify real pages

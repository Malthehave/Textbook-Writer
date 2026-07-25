---
name: technical-html-diagram
description: >-
  Author sparse, print-legible pedagogical HTML diagrams for textbooks
  (self-contained HTML with inline CSS, optional LaTeX, screenshot target
  #diagram). Use when building architecture, process-flow, or mechanism
  figures for chapter publication—not decorative art or full system maps.
---

# Technical HTML diagram

You author **self-contained HTML diagrams** for textbooks. The figure teaches one hard idea—not a full system dump and not page decoration.

There is no catalogue of typed diagram kinds. Choose the simplest visual form that fits the learning purpose (flow, layered architecture, sequence of hops, spatial math intuition, etc.).

Keep the figure sparse enough to read at print size: plan entities → place sparsely → label briefly → validate fit.

## Instructions

### Output contract

Return one complete HTML document:

- Inline `<style>` only (no external CSS, fonts, CDNs, images, or JS).
- Wrap the entire figure in `<div id="diagram">…</div>` (required). The rasterizer screenshots that node at a fixed width (~840px).
- Base CSS must include:
  - `html, body { margin: 0; padding: 0; }`
  - `#diagram { width: 100%; max-width: 840px; padding: 16px 20px 20px; box-sizing: border-box; overflow: visible; }`
  - All boxes/labels: `box-sizing: border-box; overflow-wrap: anywhere; word-break: break-word;`
  - Never set `overflow: hidden` on `#diagram` or on boxes that contain labels.
- Prefer system font stack: `ui-sans-serif, system-ui, -apple-system, Segoe UI, Helvetica, Arial, sans-serif`.
- Print-friendly: base font 13–15px; box labels ≤12–14px; borders ≥1.5px; high contrast (dark text on light fills).
- **Math must be LaTeX** in HTML text nodes (`$...$` / `$$...$$` or `\(...\)` / `\[...\]`). Never put LaTeX inside SVG `<text>`. Do not load KaTeX yourself—the renderer injects it. No `<script>`, no external URLs.

### Workflow

1. **One claim** — From the learning purpose, name one claim the figure must make. Drop everything else into prose.
2. **Few entities** — List only the 3–7 nodes (or tiers) necessary for that claim. Prefer fewer. Optional: one short title (≤8 words) inside `#diagram`. No legend unless a symbol would be ambiguous without it.
3. **Plan layout** — One clear reading direction (left→right or top→bottom). Prefer CSS flex/grid or nested panels over absolute positioning. Gaps ≥16px. Stay inside the 840px stage; if content will not fit without shrinking text below 12px, remove content.
4. **Build sparse HTML** — Labels ≤3 words per box when possible; never a sentence inside a node. Optional semantic fills (keep to 1–2 accents): primary `#dae8fc`/`#6c8ebf`, success `#d5e8d4`/`#82b366`, warning `#fff2cc`/`#d6b656`, neutral `#f5f5f5`/`#666666`. No gradients, shadows, emoji, icon packs, or fake chrome.
5. **Connect only when the connection is the lesson** — Arrows are optional. Hierarchy, containment, and sequence can be layout alone. Do not wire every box. When drawing an edge: one clean path, optional short label, no crossings if a simpler layout exists.
6. **Validate fit** — Fail closed before finishing (checklist below).

### Validation checklist

- [ ] One claim only; ≤7 labeled boxes
- [ ] Every label fully visible—no clipping, ellipsis, or overflow outside its box
- [ ] No text smaller than 12px used to “make it fit”
- [ ] No `overflow: hidden` on the stage or label containers
- [ ] Gaps remain readable; boxes do not collide
- [ ] Self-critique names what you omitted on purpose and any remaining crowding risk

## Anti-patterns

- Encyclopedia diagrams: every component, every API, every failure mode on one figure
- Walls of prose, multi-line essays, or bullet lists inside boxes
- Mandatory “connect everything” graphs that turn a simple idea into spaghetti
- Tiny fonts, squeezed gaps, or `overflow: hidden` to hide overflow
- Absolute-positioned sticker piles that break when labels wrap
- External resources, JavaScript, decorative hero spacing
- LaTeX in SVG `<text>`; Unicode-only stand-ins for real identities when LaTeX belongs
- Omitting `#diagram`

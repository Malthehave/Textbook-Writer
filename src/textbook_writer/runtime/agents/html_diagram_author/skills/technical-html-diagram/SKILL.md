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

There is no catalogue of typed diagram kinds. Choose the visual encoding that fits the
learning purpose: curve/axes, timeline, tensor map, state transition, containment,
before/after comparison, annotated mechanism, or a genuinely relational flow.

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
2. **Choose an encoding** — The figure must teach through at least one of position,
   direction, scale, axes, sequence, containment, or state change. A row/grid of rounded
   text cards is not a diagram. For example: plot the PPO clipping plateau on axes; show
   queue depth over time beside actor/learner rates; map tensor regions to devices; place
   recovery events on a timeline with the durable-state boundary.
3. **Few entities** — Keep only the labels and marks needed for that claim. Optional: one
   short title (≤8 words) inside `#diagram`. No legend unless a visual symbol needs it.
4. **Plan layout** — One clear reading direction. Use inline SVG when geometry, curves,
   axes, or precise arrows carry meaning; use CSS grid/flex for containment and labeled
   regions. Keep DOM overlays for LaTeX rather than putting LaTeX in SVG `<text>`.
   Gaps ≥16px. Stay inside the 840px stage; remove content rather than shrinking below 12px.
5. **Build sparse HTML** — Labels should be fragments, not prose. Use at most 1–2 semantic
   accents and high-contrast neutral structure. No gradients, shadows, emoji, icon packs,
   fake chrome, or repeated card components as the primary visual language.
6. **Connect only when the connection is the lesson** — Use direction, placement, and
   boundaries deliberately. Edge labels should explain what crosses a boundary; avoid
   decorative arrows and crossings.
7. **Rasterize + visually inspect** — call `rasterize-html-diagram` with `figure_id` +
   the full HTML. It returns the actual high-resolution PNG that will become the figure.
   Treat those rendered pixels as the source of truth: do not infer success from the HTML.
   Scan the image from top to bottom and inspect every title, label, box, line, arrowhead,
   axis, legend, annotation, and equation. Look specifically for text touching or crossing
   another object, labels clipped or wrapped awkwardly, obscured arrowheads, crowded gaps,
   tiny type, broken math, and ambiguous reading order. If defects are visible, simplify the
   design and make one corrective re-rasterization. Treat that second render as final rather
   than entering an open-ended polish loop. Do not attach a figure until you have inspected
   the final render.
8. **Attach** — use the returned `png=` path as `asset_path`, then write the chapter JSON.
   The renderer uses one stable HTML and PNG path per figure and replaces them on revision.

### Validation checklist (HTML plan + returned PNG)

- [ ] One claim only; ≤7 labeled boxes
- [ ] Visual meaning comes from position/direction/scale/axes/sequence/containment/state
- [ ] Not a generic row or grid of rounded text cards
- [ ] Every label fully visible—no clipping, ellipsis, or overflow outside its box
- [ ] No text overlaps, touches, or is crossed by another label, line, arrow, or boundary
- [ ] No objects unintentionally overlap or obscure each other
- [ ] No text smaller than 12px used to “make it fit”
- [ ] No `overflow: hidden` on the stage or label containers
- [ ] Gaps remain readable; boxes do not collide
- [ ] Math (if any) renders cleanly in the PNG
- [ ] The final returned PNG—not merely the HTML—was visually inspected after the last edit
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

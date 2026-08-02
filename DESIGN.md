---
name: Textbook Writer
description: Compile console — chat builds a source-grounded textbook
colors:
  ink: "#141414"
  paper: "#F7F7F5"
  panel: "#EFEFEE"
  mist: "#8A8A86"
  live: "#2F6FED"
  ok: "#1F8A4C"
  danger: "#C23B2A"
  warn: "#B86E12"
  surface: "#FFFFFF"
typography:
  ui:
    fontFamily: "Geist Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 450
    lineHeight: 1.45
    letterSpacing: "-0.01em"
  caption:
    fontFamily: "Geist Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 450
    lineHeight: 1.35
    letterSpacing: "-0.01em"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "0"
rounded:
  sm: "6px"
  md: "10px"
  lg: "14px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
  run-live:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  tool-chip:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
---

## Overview

Textbook Writer’s UI is an **operate** surface: a compile console where one manager conversation owns the book. Sessions and artifacts hang on perimeter rails; the chat floor holds the work. Visual language borrows the status grammar of Beautiful UI (loading with elapsed time, thinking traces, compact tool chips, task rows) without turning the product into a demo gallery.

## Colors

Restrained cool paper under daylight. Ink for structure and primary actions. **Live blue** only for in-flight stream state. Semantic green / amber / red for completed / stalled / failed — never as decoration.

## Typography

One UI family (Geist Variable) at a tight product scale. Mono is reserved for book ids, artifact paths, and tool codes — not costume “technical” labels.

## Layout

Three columns: sessions rail · chat floor · artifacts rail. The chat floor owns attention. Status and errors sit above the composer so they stay in the action zone while content scrolls.

## Elevation & Depth

Quiet panels (`paper` / `panel`), hairline separation, soft offset shadows only on the active session/artifact. No glass, glow, or nested cards.

## Shapes

Medium radii (`10–14px`) on rails and the chat well; smaller radii on chips and controls. Prefer flat fills over bordered card stacks.

## Components

- **Loading state** — label + elapsed time + stop while the run is submitted/streaming.
- **Thinking** — collapsible reasoning that auto-opens while streaming.
- **Tool chips** — compact tool calls; expand for input/output/errors.
- **Task rows** — specialist agents as live rows (running / failed / done) with nested reasoning/text.
- **Error strip** — sticky above the composer; names the failure and the recovery.

## Do's and Don'ts

**Do** keep stream progress and errors next to the composer.  
**Do** show specialist work as task rows, not raw JSON dumps by default.  
**Do** use measured publication artifacts in the right rail — never invent page counts in chat chrome.

**Don’t** use cream + terracotta “AI book” skinning.  
**Don’t** bury run failures in scroll history.  
**Don’t** decorate idle surfaces with accent color.

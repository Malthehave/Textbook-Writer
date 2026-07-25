#let ink = rgb("#172126")
#let muted = rgb("#5D6A70")
#let accent = rgb("#087E6A")
#let accent-soft = rgb("#E8F4F0")
#let blue-soft = rgb("#EDF3F8")
#let amber-soft = rgb("#FFF4DD")
#let border = rgb("#CBD8D4")

#set page(
  paper: "a4",
  margin: (top: 21mm, bottom: 20mm, left: 23mm, right: 23mm),
  numbering: "1",
  number-align: center,
)
#set text(font: "Libertinus Serif", size: 10.5pt, fill: ink)
// Spacing must clearly exceed leading, or paragraph breaks read as soft wraps.
#set par(justify: true, leading: 0.74em, spacing: 1.35em)
#set heading(numbering: "1.1")
#set outline(indent: 1.2em)
// Display math: textbook style — centered block with equation numbers. Inline
// `#mi(...)` stays in the text flow and is not numbered.
#set math.equation(numbering: "(1)", number-align: end + horizon)
#show math.equation.where(block: true): it => {
  set align(center)
  block(width: 100%, above: 1.15em, below: 1.15em, it)
}

#show heading.where(level: 1): it => block(above: 1.8em, below: 1.1em)[
  #text(font: "Avenir Next", size: 23pt, weight: "semibold", fill: ink)[#it.body]
  #v(4pt)
  #line(length: 100%, stroke: 1.2pt + accent)
]
#show heading.where(level: 2): it => block(above: 1.4em, below: 0.7em)[
  #text(font: "Avenir Next", size: 15pt, weight: "semibold", fill: ink)[#it.body]
]
#show heading.where(level: 3): it => block(above: 1em, below: 0.5em)[
  #text(font: "Avenir Next", size: 12pt, weight: "semibold", fill: ink)[#it.body]
]

#let title-page(title, purpose) = [
  #set align(center)
  #set par(justify: false)
  #v(1fr)
  #text(font: "Avenir Next", size: 10pt, weight: "semibold", fill: accent, tracking: 1.4pt)[TEXTBOOK WRITER]
  #v(16pt)
  #text(font: "Avenir Next", size: 30pt, weight: "semibold", fill: ink)[#title]
  #v(12pt)
  #block(width: 78%)[#text(size: 13pt, fill: muted)[#purpose]]
  #v(1fr)
  #text(size: 9pt, fill: muted)[Source-grounded · semantically authored · independently verified]
]

#let objective-box(items) = block(
  width: 100%,
  fill: accent-soft,
  stroke: 0.7pt + border,
  radius: 5pt,
  inset: 13pt,
  above: 6pt,
  below: 12pt,
)[
  #text(font: "Avenir Next", weight: "semibold", fill: accent)[Learning objectives]
  #v(6pt)
  #for item in items [
    #grid(columns: (12pt, 1fr), column-gutter: 5pt, [#text(fill: accent)[✓]], [#item])
    #v(3pt)
  ]
]

#let prerequisite-box(items) = block(
  width: 100%, fill: blue-soft, radius: 4pt, inset: 10pt, below: 11pt,
)[
  #text(font: "Avenir Next", size: 9pt, weight: "semibold", fill: muted)[PREREQUISITES]
  #h(8pt)
  #items.join(" · ")
]

#let provenance(ids) = if ids.len() > 0 {
  block(above: 4pt, below: 2pt)[
    #text(font: "Avenir Next", size: 7.5pt, fill: muted)[Evidence: #ids.join(", ")]
  ]
}

#let prose(body, claims) = {
  // Product publishing prefers Typst content blocks (paragraphs + lists).
  // Keep a string fallback for short literal bodies.
  if type(body) == str {
    let paragraphs = body.split(regex("\n\n+")).filter(paragraph => paragraph.trim() != "")
    for (index, paragraph) in paragraphs.enumerate() {
      if index > 0 { parbreak() }
      paragraph
    }
  } else {
    body
  }
  provenance(claims)
}

#let definition(term, body, claims) = block(
  width: 100%,
  stroke: (left: 3pt + accent),
  fill: rgb("#F7FAF9"),
  inset: (left: 12pt, right: 10pt, top: 9pt, bottom: 9pt),
  above: 8pt,
  below: 10pt,
)[
  #text(font: "Avenir Next", weight: "semibold", fill: accent)[#term]
  #h(5pt)
  #body
  #provenance(claims)
]

#let callout(title, kind, body, claims) = block(
  width: 100%,
  fill: if kind == "warning" { amber-soft } else { blue-soft },
  stroke: 0.6pt + border,
  radius: 4pt,
  inset: 11pt,
  above: 8pt,
  below: 10pt,
)[
  #text(font: "Avenir Next", size: 9pt, weight: "semibold", fill: muted)[#title]
  #v(4pt)
  #if type(body) == str {
    let paragraphs = body.split(regex("\n\n+")).filter(paragraph => paragraph.trim() != "")
    paragraphs.join(parbreak())
  } else {
    body
  }
  #provenance(claims)
]

#let node-box(label) = box(
  fill: white,
  stroke: 0.8pt + accent,
  radius: 4pt,
  inset: (x: 9pt, y: 8pt),
  width: 32mm,
)[
  #set text(hyphenate: false)
  #set par(justify: false, leading: 1.05em)
  #align(center + horizon)[
    #text(font: "Avenir Next", size: 7.5pt, weight: "semibold")[#label]
  ]
]

#let code-block(language, source) = block(
  width: 100%, fill: rgb("#F3F5F5"), radius: 4pt, inset: 10pt, above: 6pt, below: 10pt,
)[
  #text(font: "Avenir Next", size: 7pt, fill: muted)[#upper(language)]
  #v(5pt)
  #raw(source, lang: language, block: true)
]

#let exercise-box(number, prompt, solution-label) = block(
  width: 100%, stroke: 0.8pt + border, radius: 4pt, inset: 11pt, above: 6pt, below: 9pt,
)[
  #text(font: "Avenir Next", weight: "semibold", fill: accent)[Exercise #number]
  #v(4pt)
  #prompt
  #v(5pt)
  #link(solution-label)[#text(size: 8pt, fill: accent)[Jump to answer →]]
]

#let solution-box(number, answer, reasoning, exercise-label) = block(
  width: 100%, fill: rgb("#F7FAF9"), stroke: 0.7pt + border, radius: 4pt,
  inset: 11pt, above: 6pt, below: 10pt,
)[
  #text(font: "Avenir Next", weight: "semibold", fill: accent)[Answer #number]
  #v(4pt)
  #answer
  #v(5pt)
  #text(style: "italic", fill: muted)[#reasoning]
  #v(5pt)
  #link(exercise-label)[#text(size: 8pt, fill: accent)[← Back to exercise]]
]

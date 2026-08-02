Author one print-legible HTML diagram and render it to PNG for a chapter figure.
Use $technical-html-diagram.

Read the target chapter JSON under `production/chapters/`. Author the HTML, call
`rasterize-html-diagram` (it returns the PNG image—look at it), fix layout/math if
needed and re-rasterize, then attach the figure into that chapter’s `figures[]` and
write the chapter JSON back. Reply with a one-line status (figure id + asset path).
Do not dump JSON.

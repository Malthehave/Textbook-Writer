"""KaTeX + Playwright rasterization for HTML pedagogical diagrams."""

from __future__ import annotations

import os
import re
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Any

DEFAULT_VIEWPORT_WIDTH = 880
DEFAULT_VIEWPORT_HEIGHT = 1400
DEFAULT_DEVICE_SCALE_FACTOR = 2.0


def strip_html_code_fences(html: str) -> str:
    match = re.fullmatch(r"```(?:html)?\s*(.*?)\s*```", html.strip(), flags=re.DOTALL | re.I)
    if match:
        return match.group(1).strip()
    return html.strip()


def katex_asset_paths() -> tuple[Path, Path, Path]:
    root = Path(str(files("textbook_writer.vendor").joinpath("katex")))
    css = root / "katex.min.css"
    js = root / "katex.min.js"
    auto = root / "auto-render.min.js"
    missing = [str(path) for path in (css, js, auto) if not path.is_file()]
    if missing:
        raise FileNotFoundError("KaTeX assets missing from package vendor: " + ", ".join(missing))
    return css, js, auto


def html_with_katex_preview(html: str, *, html_path: Path) -> str:
    css, js, auto = katex_asset_paths()
    base = html_path.parent.resolve()
    rel_css = Path(os.path.relpath(css.resolve(), start=base)).as_posix()
    rel_js = Path(os.path.relpath(js.resolve(), start=base)).as_posix()
    rel_auto = Path(os.path.relpath(auto.resolve(), start=base)).as_posix()
    inject = f"""
<link rel="stylesheet" href="{rel_css}">
<script defer src="{rel_js}"></script>
<script defer src="{rel_auto}"></script>
<script>
document.addEventListener("DOMContentLoaded", function () {{
  if (typeof renderMathInElement !== "function") return;
  renderMathInElement(document.body, {{
    delimiters: [
      {{left: "$$", right: "$$", display: true}},
      {{left: "\\\\[", right: "\\\\]", display: true}},
      {{left: "$", right: "$", display: false}},
      {{left: "\\\\(", right: "\\\\)", display: false}}
    ],
    throwOnError: false
  }});
}});
</script>
"""
    if re.search(r"</head\s*>", html, flags=re.I):
        return re.sub(r"</head\s*>", inject + "</head>", html, count=1, flags=re.I)
    if re.search(r"<body\b", html, flags=re.I):
        return re.sub(r"<body\b", inject + "<body", html, count=1, flags=re.I)
    return inject + html


async def typeset_latex(page: Any) -> None:
    css, js, auto = katex_asset_paths()
    await page.add_style_tag(path=str(css))
    await page.add_script_tag(path=str(js))
    await page.add_script_tag(path=str(auto))
    await page.wait_for_function(
        "() => typeof renderMathInElement === 'function' && typeof katex !== 'undefined'"
    )
    await page.evaluate(
        """() => {
          renderMathInElement(document.body, {
            delimiters: [
              {left: '$$', right: '$$', display: true},
              {left: '\\\\[', right: '\\\\]', display: true},
              {left: '$', right: '$', display: false},
              {left: '\\\\(', right: '\\\\)', display: false}
            ],
            throwOnError: false
          });
        }"""
    )
    await page.wait_for_timeout(150)


async def render_html_to_png(
    *,
    html: str,
    png_path: Path,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
    device_scale_factor: float = DEFAULT_DEVICE_SCALE_FACTOR,
) -> str:
    """Rasterize HTML to PNG; return sha256 hex digest of the PNG bytes."""

    from playwright.async_api import async_playwright

    png_path = png_path.resolve()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(
            viewport={"width": viewport_width, "height": viewport_height},
            device_scale_factor=device_scale_factor,
        )
        await page.set_content(html, wait_until="load")
        await typeset_latex(page)
        root = page.locator("#diagram")
        if await root.count() == 0:
            root = page.locator("body")
        await root.screenshot(path=str(png_path), type="png")
        await browser.close()
    return sha256(png_path.read_bytes()).hexdigest()


def persist_html_diagram_files(
    *,
    workspace: Path,
    figure_id: str,
    html: str,
    png_bytes: bytes | None = None,
    png_path: Path | None = None,
) -> tuple[str, str, str]:
    """Write HTML (+ optional PNG). Returns (html_rel, png_rel, sha256 hex)."""

    workspace = workspace.resolve()
    asset_dir = workspace / "assets" / "figures"
    asset_dir.mkdir(parents=True, exist_ok=True)
    safe_id = figure_id.replace("/", "-")
    if png_path is not None:
        image_bytes = png_path.read_bytes()
    elif png_bytes is not None:
        image_bytes = png_bytes
    else:
        raise ValueError("png_bytes or png_path is required")
    digest = sha256(image_bytes).hexdigest()
    html_rel = f"assets/figures/{safe_id}-{digest[:12]}.html"
    png_rel = f"assets/figures/{safe_id}-{digest[:12]}.png"
    html_file = workspace / html_rel
    png_file = workspace / png_rel
    html_file.write_text(html_with_katex_preview(html, html_path=html_file), encoding="utf-8")
    if png_path is not None and png_path.resolve() != png_file.resolve():
        png_file.write_bytes(image_bytes)
    elif png_bytes is not None:
        png_file.write_bytes(image_bytes)
    elif not png_file.is_file():
        png_file.write_bytes(image_bytes)
    return html_rel, png_rel, digest

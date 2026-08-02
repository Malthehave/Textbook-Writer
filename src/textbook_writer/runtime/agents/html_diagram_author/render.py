"""Playwright rasterization for HTML pedagogical diagrams."""

from __future__ import annotations

import asyncio
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


def _katex_assets() -> tuple[Path, Path, Path]:
    root = Path(str(files("textbook_writer.vendor").joinpath("katex")))
    css, js, auto = root / "katex.min.css", root / "katex.min.js", root / "auto-render.min.js"
    missing = [str(path) for path in (css, js, auto) if not path.is_file()]
    if missing:
        raise FileNotFoundError("KaTeX assets missing: " + ", ".join(missing))
    return css, js, auto


async def _typeset_latex(page: Any) -> None:
    css, js, auto = _katex_assets()
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


async def _render_html_to_png(html: str, png_path: Path) -> str:
    from playwright.async_api import async_playwright

    png_path = png_path.resolve()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(
            viewport={
                "width": DEFAULT_VIEWPORT_WIDTH,
                "height": DEFAULT_VIEWPORT_HEIGHT,
            },
            device_scale_factor=DEFAULT_DEVICE_SCALE_FACTOR,
        )
        await page.set_content(html, wait_until="load")
        await _typeset_latex(page)
        root = page.locator("#diagram")
        if await root.count() == 0:
            raise ValueError("diagram HTML must contain exactly one #diagram element")
        if await root.count() != 1:
            raise ValueError("diagram HTML must contain exactly one #diagram element")
        await root.screenshot(path=str(png_path), type="png")
        await browser.close()
    return sha256(png_path.read_bytes()).hexdigest()


def write_html_diagram(
    *, workspace: Path, figure_id: str, html: str
) -> tuple[str, str, str]:
    """Rasterize HTML → PNG, write both under assets/figures/.

    Returns (html_rel, png_rel, sha256 hex).
    """

    html = strip_html_code_fences(html)
    workspace = workspace.resolve()
    asset_dir = workspace / "assets" / "figures"
    asset_dir.mkdir(parents=True, exist_ok=True)
    tmp_png = asset_dir / f".tmp-{figure_id.replace('/', '-')}.png"
    digest = asyncio.run(_render_html_to_png(html, tmp_png))
    safe_id = figure_id.replace("/", "-")
    html_rel = f"assets/figures/{safe_id}-{digest[:12]}.html"
    png_rel = f"assets/figures/{safe_id}-{digest[:12]}.png"
    (workspace / html_rel).write_text(html, encoding="utf-8")
    (workspace / png_rel).write_bytes(tmp_png.read_bytes())
    tmp_png.unlink(missing_ok=True)
    return html_rel, png_rel, digest

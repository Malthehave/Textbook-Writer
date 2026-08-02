from __future__ import annotations

from importlib.resources import files
from pathlib import Path
import shutil

import pytest

from textbook_writer.runtime.pdf import (
    _plain as typst_plain,
    book_output_stem,
    compile_typst,
    markdown_to_typst_content,
)
from textbook_writer.runtime.agents.html_diagram_author.render import write_html_diagram


def test_book_output_stem_slugs_title() -> None:
    assert book_output_stem("Reliable Agent Evaluation") == "reliable-agent-evaluation"
    assert book_output_stem("  Foo / Bar: Baz!  ") == "foo-bar-baz"
    assert book_output_stem("???") == "textbook"


def test_plain_text_keeps_blank_line_paragraph_breaks() -> None:
    markdown = (
        "First idea with **emphasis** and a claim [@claim-one].\n\n"
        "Second idea continues\nacross a soft wrap.\n\n"
        "Third idea stands alone."
    )
    rendered = typst_plain(markdown)
    assert "\n\n" in rendered
    assert "First idea with emphasis" in rendered
    assert "Second idea continues across a soft wrap." in rendered
    assert "\nacross" not in rendered


def test_markdown_to_typst_content_handles_commonmark_and_math() -> None:
    markdown = (
        "Open with a short claim [@claim-one].\n\n"
        "- First invariant\n"
        "- Second invariant\n\n"
        "Inline math $a_i$ and **bold**.\n\n"
        "$$\\sum_i x_i = 1$$"
    )
    rendered, imports = markdown_to_typst_content(markdown)
    assert rendered.startswith("[")
    assert "- First invariant" in rendered
    assert "- Second invariant" in rendered
    assert "*bold*" in rendered
    assert "#mi(" in rendered
    assert "#mitex(" in rendered
    assert "claim-one" not in rendered
    assert any("mitex" in item for item in imports)


def test_markdown_to_typst_content_normalizes_mixed_math_delimiters() -> None:
    rendered, imports = markdown_to_typst_content(
        "Inline \\(r_t(\\theta)\\) and $A_t$.\n\n"
        "\\[\\frac{1}{N}\\sum_t r_t(\\theta)A_t\\]\n\n"
        "$$L(\\theta)=\\mathbb{E}_t[r_t(\\theta)A_t].$$"
    )
    assert rendered.count("#mi(") == 2
    assert rendered.count("#mitex(") == 2
    assert "\\[" not in rendered
    assert "$$" not in rendered
    assert any("mitex" in item for item in imports)


def test_mixed_math_compiles_with_typst(tmp_path: Path) -> None:
    if shutil.which("typst") is None:
        pytest.skip("Typst is not installed")
    rendered, imports = markdown_to_typst_content(
        "The ratio is $r_t(\\theta)$.\n\n"
        "$$\\frac{1}{N}\\sum_t r_t(\\theta)A_t$$"
    )
    source = "\n".join(
        [
            *imports,
            '#set math.equation(numbering: "(1)")',
            rendered,
        ]
    )
    output = compile_typst(source, tmp_path / "math.pdf")
    assert output.is_file()


def test_html_diagram_rasterizes_to_png(tmp_path: Path) -> None:
    html = """
    <!doctype html>
    <style>
      html, body { margin: 0; padding: 0; }
      #diagram { width: 840px; padding: 20px; box-sizing: border-box; }
      .track { height: 80px; border-left: 2px solid #172126; border-bottom: 2px solid #172126; }
      .line { width: 620px; height: 40px; border-bottom: 4px solid #087e6a; transform: skewY(-5deg); }
    </style>
    <div id="diagram">
      <h2>Queue depth over time</h2>
      <div class="track"><div class="line"></div></div>
      <p>Producer rate $R_a$ exceeds learner rate $R_l$.</p>
    </div>
    """
    html_rel, png_rel, digest = write_html_diagram(
        workspace=tmp_path,
        figure_id="queue-depth",
        html=html,
    )
    png = tmp_path / png_rel
    assert (tmp_path / html_rel).is_file()
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert png.stat().st_size > 2_000
    assert len(digest) == 64


def test_html_diagram_requires_diagram_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="#diagram"):
        write_html_diagram(
            workspace=tmp_path,
            figure_id="missing-root",
            html="<p>No diagram root</p>",
        )


def test_textbook_template_numbers_and_centers_display_equations() -> None:
    template = files("textbook_writer.runtime").joinpath("textbook.typ").read_text(
        encoding="utf-8"
    )
    assert 'math.equation(numbering: "(1)"' in template
    assert "number-align: end + horizon" in template
    assert "math.equation.where(block: true)" in template
    assert "size: 10.75pt" in template
    assert "leading: 0.82em, spacing: 1.4em" in template
    assert "above: 1.65em, below: 0.85em" in template

from __future__ import annotations

from importlib.resources import files

from textbook_writer.runtime.pdf import (
    _plain as typst_plain,
    book_output_stem,
    markdown_to_typst_content,
)


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


def test_textbook_template_numbers_and_centers_display_equations() -> None:
    template = files("textbook_writer.runtime").joinpath("textbook.typ").read_text(
        encoding="utf-8"
    )
    assert 'math.equation(numbering: "(1)"' in template
    assert "number-align: end + horizon" in template
    assert "math.equation.where(block: true)" in template

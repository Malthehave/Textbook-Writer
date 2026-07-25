from types import SimpleNamespace

from textbook_writer.api.stream import _reasoning_text


def test_reasoning_text_ignores_encrypted_only_item() -> None:
    item = SimpleNamespace(
        raw_item=SimpleNamespace(
            summary=[],
            content=[],
            encrypted_content="gAAAAABnot-real",
        )
    )
    assert _reasoning_text(item) == ""  # type: ignore[arg-type]


def test_reasoning_text_uses_summary_blocks() -> None:
    item = SimpleNamespace(
        raw_item=SimpleNamespace(
            summary=[SimpleNamespace(text="Check sources first.")],
            content=[],
            encrypted_content=None,
        )
    )
    assert _reasoning_text(item) == "Check sources first."  # type: ignore[arg-type]

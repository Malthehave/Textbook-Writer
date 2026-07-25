from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pydantic import BaseModel

from textbook_writer.runtime.stage_persist import (
    make_artifact_input_builder,
    make_persisting_extractor,
    persist_specialist_output,
    resolve_output_path,
    summarize_output,
)


class _Chapter(BaseModel):
    chapter_id: str
    title: str
    sections: list[str] = []
    exercises: list[str] = []
    figures: list[str] = []


class _Verification(BaseModel):
    chapter_ref: str
    verdicts: list[dict[str, str]]


def test_resolve_and_persist_fixed_and_chapter_paths(tmp_path: Path) -> None:
    dossier = {"title": "T", "topics": [1], "sources": [1, 2], "unresolved": []}
    saved = persist_specialist_output(
        workspace=tmp_path, tool_name="research-architect", output=dossier
    )
    assert saved == "research-dossier.json"
    assert (tmp_path / "production" / "research-dossier.json").is_file()

    chapter = _Chapter(chapter_id="ch-1", title="Intro")
    assert resolve_output_path("chapter-writer", chapter) == "chapters-v1/ch-1.json"
    saved_ch = persist_specialist_output(
        workspace=tmp_path, tool_name="chapter-writer", output=chapter
    )
    assert saved_ch == "chapters-v1/ch-1.json"
    assert (tmp_path / "production" / "chapters-v1" / "ch-1.json").is_file()

    verification = _Verification(
        chapter_ref="ch-1",
        verdicts=[{"exercise_ref": "ex-1", "decision": "approve"}],
    )
    assert (
        resolve_output_path("solution-comparator", verification)
        == "chapters-v1/ch-1.verification.json"
    )


def test_persisting_extractor_returns_compact_saved_summary(tmp_path: Path) -> None:
    class _Result:
        final_output = {"title": "Book", "topics": [{}], "sources": [{}, {}], "unresolved": []}

    extract = make_persisting_extractor(tmp_path, "research-architect")
    text = asyncio.run(extract(_Result()))
    payload = json.loads(text)
    assert payload["saved"] == "research-dossier.json"
    assert payload["summary"]["title"] == "Book"
    assert payload["bytes"] > 0


def test_artifact_input_builder_loads_disk(tmp_path: Path) -> None:
    stages = tmp_path / "production"
    stages.mkdir()
    (stages / "research-dossier.json").write_text('{"ok": true}\n', encoding="utf-8")
    build = make_artifact_input_builder(tmp_path, "research-dossier.json")
    text = asyncio.run(build({"params": {"input": "Audit this."}}))
    assert "Audit this." in text
    assert "production/research-dossier.json" in text
    assert '"ok": true' in text


def test_summarize_output_shapes() -> None:
    summary = summarize_output(
        "curriculum-architect",
        {
            "title": "X",
            "target_pages": 40,
            "chapters": [{"chapter_id": "c1", "title": "One"}],
        },
    )
    assert summary["chapters"][0]["chapter_id"] == "c1"

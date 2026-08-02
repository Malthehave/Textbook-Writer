from __future__ import annotations

from pathlib import Path

from agents.sandbox.capabilities import Filesystem, Shell, Skills

from textbook_writer.runtime.agents.manager import build_manager_agent
from textbook_writer.runtime.pdf import book_output_stem
from textbook_writer.runtime.workspace_tools import stages_dir


def test_manager_registers_lean_specialists(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    agent = build_manager_agent(model="gpt-5.6-luna", book_root=book)
    names = {
        getattr(tool, "name", None) or getattr(tool, "tool_name", None)
        for tool in agent.tools or []
    }
    assert names == {
        "build-textbook-pdf",
        "research-architect",
        "curriculum-architect",
        "chapter-writer",
        "independent-verifier",
        "solution-comparator",
    }
    kinds = {type(cap) for cap in agent.capabilities}
    assert {Shell, Filesystem, Skills} <= kinds


def test_book_output_stem_and_stages_dir(tmp_path: Path) -> None:
    assert book_output_stem("Reliable Agent Evaluation") == "reliable-agent-evaluation"
    assert stages_dir(tmp_path).name == "production"

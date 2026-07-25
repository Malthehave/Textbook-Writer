from __future__ import annotations

from pathlib import Path

from textbook_writer.publishing import book_output_stem
from textbook_writer.runtime.agents.manager import build_manager_agent, manager_tool_names
from textbook_writer.runtime.workspace_tools import stages_dir


def test_manager_registers_specialists_and_deterministic_tools(tmp_path: Path) -> None:
    agent = build_manager_agent(
        workspace=tmp_path, book_id="book-manager-test", model="gpt-5.6-luna"
    )
    names = set(manager_tool_names(agent))
    assert {
        "research-scout",
        "research-architect",
        "research-auditor",
        "curriculum-architect",
        "coverage-auditor",
        "curriculum-repair",
        "chapter-writer",
        "html-diagram-author",
        "independent-verifier",
        "solution-comparator",
        "acquire_and_freeze",
        "assemble_book",
        "publish_book",
        "save_stage_artifact",
        "approve_production_brief",
    }.issubset(names)
    assert "update_kickoff" not in names
    assert "read_kickoff" not in names


def test_book_output_stem_and_stages_dir(tmp_path: Path) -> None:
    assert book_output_stem("Reliable Agent Evaluation") == "reliable-agent-evaluation"
    assert stages_dir(tmp_path).name == "production"

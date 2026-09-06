from __future__ import annotations

from pathlib import Path

from agents.sandbox.capabilities import Filesystem, Shell, Skills

from textbook_writer.runtime.agents import sandbox_tool_run_config
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
        "web_search",
        "build-textbook-pdf",
        "forecast-textbook-pages",
        "inspect-pipeline-state",
        "validate-production-artifact",
        "research-architect",
        "lead-author",
        "reader-experience-editor",
        "independent-verifier",
        "solution-comparator",
        "html-diagram-author",
        "publication-reviewer",
    }
    kinds = {type(cap) for cap in agent.capabilities}
    assert {Shell, Filesystem, Skills} <= kinds
    assert agent.model_settings.parallel_tool_calls is True
    run_config = sandbox_tool_run_config(root=book)
    assert run_config.tool_execution is not None
    assert run_config.tool_execution.max_function_tool_concurrency == 2


def test_book_output_stem_and_stages_dir(tmp_path: Path) -> None:
    assert book_output_stem("Reliable Agent Evaluation") == "reliable-agent-evaluation"
    assert stages_dir(tmp_path).name == "production"


def test_manager_enforces_reader_experience_gate_and_shared_state(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    agent = build_manager_agent(model="gpt-5.6-luna", book_root=book)
    assert "reader-experience-editor" in agent.instructions
    assert "lead-author" in agent.instructions
    assert "quality-slice" in agent.instructions
    assert "scorecard" in agent.instructions
    assert "15%" in agent.instructions
    assert "latest compiled PDF" in agent.instructions
    assert "validate-production-artifact" in agent.instructions
    assert "Never run two lead-author calls concurrently" in agent.instructions
    assert "manuscript.review.json" in agent.instructions
    assert "inspect-pipeline-state" in agent.instructions
    assert "Formal subject evidence" in agent.instructions
    skill = (
        Path(__file__).resolve().parents[1]
        / "src/textbook_writer/runtime/agents/manager/skills/manager-orchestration/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "Reader-experience gate" in skill
    assert "every score at least 4" in skill
    assert "1,500–2,200 word chapter" in skill
    assert "Never start independent exercise QA" in skill
    assert "every PDF page as an individual preview" in skill
    assert "stop and report" not in skill.lower()

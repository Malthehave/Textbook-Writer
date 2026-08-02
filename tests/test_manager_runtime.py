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
        "validate-production-artifact",
        "research-architect",
        "curriculum-architect",
        "chapter-writer",
        "chapter-reviewer",
        "independent-verifier",
        "solution-comparator",
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


def test_manager_enforces_editorial_gate_and_shared_state(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    agent = build_manager_agent(model="gpt-5.6-luna", book_root=book)
    assert "chapter-reviewer" in agent.instructions
    assert "editorial-state.json" in agent.instructions
    assert "fresh run" in agent.instructions
    assert "self-contained `input`" in agent.instructions
    assert "book filesystem" in agent.instructions
    assert "copying their contents into `input`" in agent.instructions
    assert "15%-tolerance range" in agent.instructions
    assert "give the learner the latest PDF" in agent.instructions
    assert "must pass `validate-production-artifact`" in agent.instructions
    assert "Do not spend a blind-solver run" in agent.instructions
    assert "targets of 8 pages or fewer" in agent.instructions
    assert "Never run two chapter writers concurrently" in agent.instructions
    assert "You can use `web_search` directly" in agent.instructions
    assert "Formal subject research still belongs" in agent.instructions
    assert "Learner persona section" in agent.instructions
    skill = (
        Path(__file__).resolve().parents[1]
        / "src/textbook_writer/runtime/agents/manager/skills/manager-orchestration/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "allow one editorial rewrite after" in skill
    assert "The next chapter may now be drafted" in skill
    assert "The review file is the canonical brief" in skill
    assert "six-page target accepts five through seven pages" in skill
    assert "allow one publication-fit correction cycle" in skill
    assert "Do not estimate page consumption from PNG pixels" in skill
    assert "Never defer schema or figure-path validation" in skill
    assert "do not invoke the blind solver" in skill
    assert "6 pages or fewer" in skill
    assert "at most 3 exercises" in skill

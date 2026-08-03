from __future__ import annotations

from pathlib import Path

from agents.sandbox import SandboxAgent
from agents.sandbox.capabilities import Filesystem, Shell, Skills

from textbook_writer.runtime import build_manager_agent
from textbook_writer.runtime.agents import (
    build_chapter_reviewer_agent,
    build_chapter_writer_agent,
    build_curriculum_architect_agent,
    build_html_diagram_agent,
    build_independent_verifier_agent,
    build_research_architect_agent,
    build_solution_comparator_agent,
)
from textbook_writer.runtime.agents.manager import build_manager_agent as build_manager
from textbook_writer.runtime.agents import agent_capabilities


def _tool_names(agent: SandboxAgent) -> set[str]:
    return {
        getattr(tool, "name", None) or getattr(tool, "tool_name", None)
        for tool in agent.tools or []
    }


def test_production_entry_is_manager_agent() -> None:
    assert callable(build_manager_agent)


def test_each_agent_gets_only_its_own_skills(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    manager = build_manager(model="gpt-5.6-luna", book_root=book)
    research = build_research_architect_agent(model="gpt-5.6-luna", book_root=book)
    curriculum = build_curriculum_architect_agent(model="gpt-5.6-luna", book_root=book)
    writer = build_chapter_writer_agent(model="gpt-5.6-luna", book_root=book)
    reviewer = build_chapter_reviewer_agent(model="gpt-5.6-luna", book_root=book)
    visual = build_html_diagram_agent(model="gpt-5.6-luna", book_root=book)
    verifier = build_independent_verifier_agent(model="gpt-5.6-luna", book_root=book)
    comparator = build_solution_comparator_agent(model="gpt-5.6-luna", book_root=book)

    assert _skill_names(manager) == {"manager-orchestration"}
    assert _skill_names(research) == {"research"}
    assert _skill_names(curriculum) == set()
    assert _skill_names(writer) == {"textbook-prose"}
    assert _skill_names(reviewer) == set()
    assert _skill_names(visual) == {"technical-html-diagram"}
    assert _skill_names(verifier) == {"exercise-verification"}
    assert _skill_names(comparator) == {"exercise-verification"}
    for specialist in (
        research,
        curriculum,
        writer,
        reviewer,
        visual,
        verifier,
        comparator,
    ):
        assert specialist.model_settings.reasoning is not None
        assert specialist.model_settings.reasoning.summary == "auto"
        assert specialist.output_type is None

    assert _tool_names(writer) == {
        "describe-production-artifact",
        "commit-production-artifact",
        "validate-production-artifact",
        "html-diagram-author",
    }
    assert _tool_names(research) == {
        "web_search",
        "describe-production-artifact",
        "commit-production-artifact",
        "validate-production-artifact",
    }
    assert {
        "describe-production-artifact",
        "commit-production-artifact",
        "validate-production-artifact",
    } <= _tool_names(curriculum)
    manager_tools = _tool_names(manager)
    assert "html-diagram-author" not in manager_tools
    assert "chapter-writer" in manager_tools
    assert "chapter-reviewer" in manager_tools
    assert "commit-production-artifact" not in manager_tools

    prose = (
        Path(__file__).resolve().parents[1]
        / "src/textbook_writer/runtime/agents/chapter_writer/skills/textbook-prose/SKILL.md"
    )
    assert "Google Technical Writing" in prose.read_text(encoding="utf-8")
    assert "Google Technical Writing" not in writer.instructions
    assert "do not regenerate it from the plan" in writer.instructions
    assert "On a rewrite, preserve existing figures and assets" in writer.instructions
    assert "frozen during exercise QA" in writer.instructions
    assert "at most two `exec_command` calls" in writer.instructions
    assert "Never create or edit `.answers.json`" in writer.instructions
    assert "publication-fit length revision" in writer.instructions
    assert "do not call the" in writer.instructions
    assert "commit-production-artifact" in writer.instructions
    assert "Do not estimate final PDF page usage" in reviewer.instructions
    assert "only authority for page count" in reviewer.instructions
    assert "optional polish" in reviewer.instructions
    assert "at most one corrective rasterization" in visual.instructions
    assert "BlindAnswers" in verifier.instructions
    assert "commit-production-artifact" in verifier.instructions


def test_agent_capabilities_shell_filesystem_and_optional_skills() -> None:
    writer_caps = agent_capabilities(
        str(
            Path(__file__).resolve().parents[1]
            / "src/textbook_writer/runtime/agents/chapter_writer/agent.py"
        )
    )
    curriculum_caps = agent_capabilities(
        str(
            Path(__file__).resolve().parents[1]
            / "src/textbook_writer/runtime/agents/curriculum_architect/agent.py"
        )
    )
    assert {Shell, Filesystem, Skills} <= {type(c) for c in writer_caps}
    assert {Shell, Filesystem} <= {type(c) for c in curriculum_caps}
    assert Skills not in {type(c) for c in curriculum_caps}


def test_agent_prompts_load_from_markdown(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    writer = build_chapter_writer_agent(model="gpt-5.6-luna", book_root=book)
    assert isinstance(writer, SandboxAgent)
    assert writer.instructions.endswith("\n")
    assert "research.json" in writer.instructions
    assert "$textbook-prose" in writer.instructions


def test_every_agent_prompt_starts_with_persona_and_purpose() -> None:
    agents_dir = (
        Path(__file__).resolve().parents[1] / "src/textbook_writer/runtime/agents"
    )
    prompt_paths = sorted(agents_dir.glob("*/prompt.md"))
    assert prompt_paths
    for path in prompt_paths:
        first_paragraph = path.read_text(encoding="utf-8").split("\n\n", maxsplit=1)[0]
        assert first_paragraph.startswith("You are"), path
        assert "purpose" in first_paragraph.lower(), path


def _skill_names(agent: SandboxAgent) -> set[str]:
    names: set[str] = set()
    for capability in agent.capabilities:
        if isinstance(capability, Skills) and capability.lazy_from is not None:
            names.update(
                meta.name
                for meta in capability.lazy_from.list_skill_metadata(
                    skills_path=capability.skills_path
                )
            )
    return names

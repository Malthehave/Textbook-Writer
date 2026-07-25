from __future__ import annotations

from agents.sandbox import SandboxAgent
from agents.sandbox.capabilities import Skills

from textbook_writer.runtime import PRODUCTION_TEAM, build_manager_agent
from textbook_writer.runtime.agents import (
    build_chapter_writer_agent,
    build_html_diagram_agent,
    build_independent_verifier_agent,
    team_role_ids,
)
from textbook_writer.runtime.skills_runtime import packaged_skills_root, skills_capability


def test_production_entry_is_manager_agent() -> None:
    assert callable(build_manager_agent)


def test_production_team_covers_core_roles() -> None:
    roles = set(team_role_ids())
    assert {
        "manager",
        "research-architect",
        "research-auditor",
        "acquire-sources",
        "curriculum-architect",
        "coverage-auditor",
        "curriculum-repair",
        "chapter-writer",
        "html-diagram-author",
        "independent-verifier",
        "bind-citations",
        "publish",
    }.issubset(roles)
    assert any(role.kind == "tool" for role in PRODUCTION_TEAM)


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


def test_skilled_specialists_attach_sdk_skills() -> None:
    writer = build_chapter_writer_agent(model="gpt-5.6-luna")
    visual = build_html_diagram_agent(model="gpt-5.6-luna")
    verifier = build_independent_verifier_agent(model="gpt-5.6-luna")
    assert isinstance(writer, SandboxAgent)
    assert isinstance(visual, SandboxAgent)
    assert isinstance(verifier, SandboxAgent)
    assert writer.name == "Source-grounded textbook chapter writer"
    assert visual.name == "Technical HTML diagram author"
    assert "$textbook-prose" in writer.instructions
    assert "$technical-html-diagram" in visual.instructions
    packaged = _skill_names(writer)
    assert "textbook-prose" in packaged
    assert "technical-html-diagram" in packaged
    assert "exercise-verification" in packaged
    assert packaged == _skill_names(visual) == _skill_names(verifier)
    assert "Google Technical Writing" not in writer.instructions
    prose = packaged_skills_root() / "textbook-prose" / "SKILL.md"
    assert "Google Technical Writing" in prose.read_text(encoding="utf-8")
    assert skills_capability().lazy_from is not None


def test_agent_prompts_load_from_markdown() -> None:
    writer = build_chapter_writer_agent(model="gpt-5.6-luna")
    assert writer.instructions.endswith("\n")
    assert "frozen source passages" in writer.instructions

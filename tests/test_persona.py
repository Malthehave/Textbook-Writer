from __future__ import annotations

from pathlib import Path

from textbook_writer.runtime.agents.manager import build_manager_agent
from textbook_writer.runtime.agents.persona_interviewer import (
    build_persona_interviewer_agent,
)
from textbook_writer.runtime import persona as persona_module


def test_persona_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(persona_module, "PERSONA_DIR", tmp_path / "learner")
    assert persona_module.load_persona() == ""
    saved = persona_module.save_persona("## Identity\n\nMalthe\n")
    assert saved.endswith("\n")
    assert persona_module.load_persona() == "## Identity\n\nMalthe\n"
    assert "Learner persona" in persona_module.persona_section()
    persona_module.save_persona("")
    assert persona_module.load_persona() == ""
    assert persona_module.persona_section() == ""


def test_manager_injects_learner_persona(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    agent = build_manager_agent(
        model="gpt-5.6-luna",
        book_root=book,
        learner_persona="## Identity\n\nInterview candidate with RL systems gaps.\n",
    )
    lower = agent.instructions.lower()
    assert "learner persona" in lower
    assert "rl systems gaps" in lower
    assert "re-ask identity" in lower
    assert "self-contained" in lower
    assert "web_search" in lower


def test_persona_interviewer_has_web_search() -> None:
    agent = build_persona_interviewer_agent(model="gpt-5.6-luna")
    names = {
        getattr(tool, "name", None) or getattr(tool, "tool_name", None)
        for tool in agent.tools or []
    }
    assert "web_search" in names
    assert "persona.md" in agent.instructions
    assert agent.instructions.startswith("You are the learner-profile interviewer")
    lower = agent.instructions.lower()
    assert "out of scope" in lower
    assert "time horizon" in lower
    assert "learning goals" in lower
    assert "work experience" in lower
    assert "self-contained" in lower
    assert "link-dump" in lower or "bare urls" in lower

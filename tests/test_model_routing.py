from __future__ import annotations

from dataclasses import astuple

import pytest

from textbook_writer.runtime.model_registry import DEFAULT_MODEL
from textbook_writer.runtime.model_routing import PipelineModels


@pytest.mark.parametrize("legacy_mode", [None, "smart", "uniform"])
def test_default_routes_every_role_to_astra(monkeypatch, legacy_mode) -> None:
    for role in PipelineModels.__dataclass_fields__:
        monkeypatch.delenv(f"TEXTBOOK_MODEL_{role.upper()}", raising=False)
    if legacy_mode is None:
        monkeypatch.delenv("TEXTBOOK_MODEL_ROUTING", raising=False)
    else:
        monkeypatch.setenv("TEXTBOOK_MODEL_ROUTING", legacy_mode)
    assert DEFAULT_MODEL == "gpt-6-astra"
    assert set(astuple(PipelineModels.from_base(DEFAULT_MODEL))) == {"gpt-6-astra"}


def test_uniform_routing_and_role_override(monkeypatch) -> None:
    monkeypatch.setenv("TEXTBOOK_MODEL_SOLVER", "custom-solver")
    models = PipelineModels.from_base("base-model")
    assert models.writer == "base-model"
    assert models.solver == "custom-solver"


def test_default_manager_builds_astra_specialists(tmp_path, monkeypatch) -> None:
    from textbook_writer.runtime.agents.manager import agent as manager_module
    from textbook_writer.runtime.agents.persona_interviewer.agent import (
        build_persona_interviewer_agent,
    )

    expected = {
        "research_architect": "high",
        "chapter_writer": "high",
        "chapter_reviewer": "high",
        "independent_verifier": "high",
        "solution_comparator": "high",
        "html_diagram": "medium",
        "publication_reviewer": "high",
    }
    captured = []
    for role in PipelineModels.__dataclass_fields__:
        monkeypatch.delenv(f"TEXTBOOK_MODEL_{role.upper()}", raising=False)
    for role, effort in expected.items():
        name = f"build_{role}_agent"
        original = getattr(manager_module, name)

        def capture(*args, _original=original, _effort=effort, **kwargs):
            agent = _original(*args, **kwargs)
            assert agent.model == "gpt-6-astra"
            assert agent.model_settings.reasoning.effort == _effort
            captured.append(agent.name)
            return agent

        monkeypatch.setattr(manager_module, name, capture)
    manager = manager_module.build_manager_agent(book_root=tmp_path)
    assert manager.model == "gpt-6-astra"
    assert manager.model_settings.reasoning.effort == "medium"
    assert len(captured) == len(expected)
    from textbook_writer.runtime import persona as persona_module

    monkeypatch.setattr(persona_module, "PERSONA_DIR", tmp_path / "learner")
    persona = build_persona_interviewer_agent()
    assert persona.model == "gpt-6-astra"
    assert persona.model_settings.reasoning.effort == "medium"

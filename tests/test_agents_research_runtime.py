from __future__ import annotations

from pathlib import Path

from textbook_writer.runtime.agents.research_architect.agent import (
    build_research_architect_agent,
)


def test_research_architect_has_hosted_web_search_and_commit_tools(tmp_path: Path) -> None:
    agent = build_research_architect_agent(model="gpt-5.6-luna", book_root=tmp_path)

    assert agent.model == "gpt-5.6-luna"
    assert agent.output_type is None
    names = {
        getattr(tool, "name", None) or getattr(tool, "tool_name", None)
        for tool in agent.tools or []
    }
    assert names == {
        "web_search",
        "describe-production-artifact",
        "commit-production-artifact",
        "validate-production-artifact",
    }
    assert agent.model_settings.response_include == ["web_search_call.action.sources"]

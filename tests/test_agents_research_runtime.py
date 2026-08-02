from __future__ import annotations

from textbook_writer.runtime.agents.research_architect.agent import (
    build_research_architect_agent,
)


def test_research_architect_has_hosted_web_search() -> None:
    agent = build_research_architect_agent(model="gpt-5.6-luna")

    assert agent.model == "gpt-5.6-luna"
    assert [tool.name for tool in agent.tools] == ["web_search"]
    assert agent.output_type is None
    assert agent.model_settings.response_include == ["web_search_call.action.sources"]

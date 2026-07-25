from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from textbook_writer.models import (
    ResearchScoutOutput,
    ResearchScoutRun,
)
from textbook_writer.runtime.agents.research_scout import (
    build_research_scout_agent,
    collect_search_provenance,
    run_research_scout,
)


def _scout_output() -> ResearchScoutOutput:
    return ResearchScoutOutput.model_validate(
        {
            "scout_output_id": "scout-output-rl-systems-v001",
            "interpreted_goal": "Learn the systems foundations of distributed policy training.",
            "confirmed": ["The learner wants a source-grounded technical textbook."],
            "inferred": [
                {
                    "statement": "Distributed communication is a prerequisite area.",
                    "rationale": "The target capability includes distributed policy training.",
                    "confidence": "high"
                }
            ],
            "unresolved": ["The final page budget is not yet known."],
            "clarifying_questions": [],
            "research_questions": [
                {
                    "question_id": "question-distributed-communication",
                    "question": "Which communication primitives underpin distributed training?",
                    "required": True,
                    "freshness": "stable"
                },
                {
                    "question_id": "question-policy-loop",
                    "question": "Which stages make up a PPO training loop?",
                    "required": True,
                    "freshness": "stable"
                }
            ],
            "query_families": [
                {
                    "family_id": "family-target",
                    "purpose": "target-analysis",
                    "queries": ["distributed policy training role competencies"]
                },
                {
                    "family_id": "family-primary",
                    "purpose": "primary-official",
                    "queries": ["official distributed training documentation PPO paper"]
                },
                {
                    "family_id": "family-canonical",
                    "purpose": "canonical-coverage",
                    "queries": ["distributed training canonical course curriculum"]
                },
                {
                    "family_id": "family-omissions",
                    "purpose": "omission-challenge",
                    "queries": ["distributed RL infrastructure missing prerequisites"]
                }
            ],
            "source_leads": [
                {
                    "source_lead_id": "lead-pytorch-distributed",
                    "url": "https://docs.pytorch.org/tutorials/beginner/dist_overview.html",
                    "title": "PyTorch Distributed Overview",
                    "likely_authority": "official",
                    "query_family_refs": ["family-primary", "family-canonical"],
                    "question_refs": ["question-distributed-communication"],
                    "relevance": "Documents collective communication and parallelism APIs.",
                    "acquisition_reason": "Needed to reopen official implementation guidance."
                },
                {
                    "source_lead_id": "lead-ppo-paper",
                    "url": "https://arxiv.org/abs/1707.06347",
                    "title": "Proximal Policy Optimization Algorithms",
                    "likely_authority": "primary",
                    "query_family_refs": ["family-primary"],
                    "question_refs": ["question-policy-loop"],
                    "relevance": "Primary description of the PPO sampling and optimization loop.",
                    "acquisition_reason": "Needed for algorithm-level claims."
                },
                {
                    "source_lead_id": "lead-pytorch-ddp-paper",
                    "url": "https://arxiv.org/abs/2006.15704",
                    "title": "PyTorch Distributed: Experiences on Accelerating Data Parallel Training",
                    "likely_authority": "primary",
                    "query_family_refs": ["family-primary"],
                    "question_refs": ["question-distributed-communication"],
                    "relevance": "Primary systems account of PyTorch distributed data parallel training.",
                    "acquisition_reason": "Needed to corroborate the official implementation guidance."
                },
                {
                    "source_lead_id": "lead-ppo-implementation",
                    "url": "https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html",
                    "title": "Stable Baselines3 PPO Documentation",
                    "likely_authority": "official",
                    "query_family_refs": ["family-primary"],
                    "question_refs": ["question-policy-loop"],
                    "relevance": "Official implementation documentation demonstrating practical PPO use.",
                    "acquisition_reason": "Needed to corroborate the paper with an implementation signal."
                }
            ],
            "candidate_competencies": [
                {
                    "competency_id": "explain-distributed-communication",
                    "label": "Explain distributed communication primitives",
                    "priority": "required",
                    "rationale": "Foundational to synchronization and scaling behavior.",
                    "prerequisite_competencies": [],
                    "source_lead_refs": [
                        "lead-pytorch-distributed",
                        "lead-pytorch-ddp-paper"
                    ]
                },
                {
                    "competency_id": "explain-policy-training-loop",
                    "label": "Explain the policy-training loop",
                    "priority": "required",
                    "rationale": "Defines the stages the infrastructure must coordinate.",
                    "prerequisite_competencies": [],
                    "source_lead_refs": ["lead-ppo-paper", "lead-ppo-implementation"]
                }
            ],
            "considered_exclusions": [
                {
                    "topic": "cuda-kernel-authoring",
                    "decision": "deferred",
                    "rationale": "Lower relevance to the narrow kickoff."
                }
            ],
            "coverage_risks": ["The narrow scout has not yet compared multiple canonical curricula."],
            "stopping_reason": "Every required query family has at least one useful source lead."
        }
    )


def _raw_response() -> dict:
    urls = [
        "https://docs.pytorch.org/tutorials/beginner/dist_overview.html",
        "https://arxiv.org/abs/1707.06347",
        "https://arxiv.org/abs/2006.15704",
        "https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html",
    ]
    return {
        "response_id": "resp-scout-001",
        "output": [
            {
                "type": "web_search_call",
                "action": {
                    "sources": [{"type": "url", "url": url} for url in urls]
                },
            },
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url": urls[0],
                                "title": "PyTorch Distributed Overview",
                                "start_index": 0,
                                "end_index": 10,
                            },
                            {
                                "type": "url_citation",
                                "url": urls[1],
                                "title": "Proximal Policy Optimization Algorithms",
                                "start_index": 11,
                                "end_index": 20,
                            },
                        ],
                    }
                ],
            },
        ],
    }


def test_research_agent_has_only_hosted_web_search() -> None:
    agent = build_research_scout_agent()

    assert agent.model == "gpt-5.6-luna"
    assert [tool.name for tool in agent.tools] == ["web_search"]
    assert agent.output_type is ResearchScoutOutput
    assert agent.model_settings.response_include == ["web_search_call.action.sources"]


def test_native_search_sources_and_annotations_are_collected() -> None:
    citations, search_calls, response_ids = collect_search_provenance([_raw_response()])

    assert search_calls == 1
    assert response_ids == ["resp-scout-001"]
    assert {str(item.url) for item in citations} == {
        "https://arxiv.org/abs/1707.06347",
        "https://arxiv.org/abs/2006.15704",
        "https://docs.pytorch.org/tutorials/beginner/dist_overview.html",
        "https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html",
    }
    assert {item.title for item in citations} == {
        "Proximal Policy Optimization Algorithms",
        "PyTorch Distributed Overview",
        "https://arxiv.org/abs/2006.15704",
        "https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html",
    }


def test_scout_run_persists_typed_native_cited_output(tmp_path: Path) -> None:
    async def fake_runner(*args: object, **kwargs: object) -> SimpleNamespace:
        assert kwargs["max_turns"] == 12
        assert kwargs["session"] is not None
        return SimpleNamespace(
            final_output=_scout_output(),
            raw_responses=[_raw_response()],
        )

    output_path = tmp_path / "scout-run.json"
    run = asyncio.run(
        run_research_scout(
            "Teach me distributed policy training.",
            book_id="book-runtime-test",
            output_path=output_path,
            session_id="book-session-runtime-test",
            session_db_path=tmp_path / "sessions.sqlite",
            runner=fake_runner,
        )
    )

    assert run.web_search_calls == 1
    assert ResearchScoutRun.model_validate_json(output_path.read_text()) == run


def test_uncited_source_lead_is_rejected() -> None:
    output = _scout_output()
    with pytest.raises(ValidationError, match="lack native web-search citations"):
        ResearchScoutRun(
            scout_run_id="scout-run-uncited",
            book_ref="book-runtime-test",
            model="gpt-5.6",
            session_id="book-session-runtime-test",
            response_ids=["resp-scout-001"],
            web_search_calls=1,
            citations=[
                {
                    "citation_id": "citation-one",
                    "response_id": "resp-scout-001",
                    "url": "https://docs.pytorch.org/tutorials/beginner/dist_overview.html",
                    "title": "PyTorch Distributed Overview",
                }
            ],
            output=output,
        )


from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from textbook_writer.models import ProductionBrief


def test_production_brief_draft_and_approval_shapes() -> None:
    draft = ProductionBrief.model_validate(
        {
            "brief_id": "brief-agentic-rl",
            "book_id": "book-agentic-rl",
            "confirmed": ["Learner wants rollout-focused material."],
            "target_pages": 40,
            "chapter_sketch": [
                {
                    "chapter_id": "chapter-01",
                    "title": "Rollout loops",
                    "purpose": "Establish the shared system.",
                }
            ],
            "scope_summary": "A compact field guide.",
            "approved": False,
        }
    )
    assert draft.approved is False
    approved = draft.model_copy(
        update={"approved": True, "approved_at": datetime.now(UTC)}
    )
    assert approved.approved is True


def test_production_brief_rejects_approval_without_timestamp() -> None:
    with pytest.raises(ValidationError, match="approved_at"):
        ProductionBrief.model_validate(
            {
                "brief_id": "brief-bad",
                "book_id": "book-agentic-rl",
                "target_pages": 40,
                "chapter_sketch": [
                    {
                        "chapter_id": "chapter-01",
                        "title": "One",
                        "purpose": "Teach one idea.",
                    }
                ],
                "scope_summary": "Incomplete approval metadata.",
                "approved": True,
            }
        )

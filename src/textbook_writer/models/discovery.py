"""Production-brief models for manager-led discovery."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from textbook_writer.models.base import Model
from textbook_writer.models.enums import Confidence


class Inference(Model):
    statement: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    confidence: Confidence


class ChapterSketch(Model):
    """Lightweight chapter intent for discovery—not a full production plan."""

    chapter_id: str
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)


class ProductionBrief(Model):
    """Learner-approved scope gate before production writing."""

    brief_id: str
    book_id: str
    confirmed: list[str] = Field(default_factory=list)
    inferred: list[Inference] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)
    target_pages: int = Field(ge=1)
    page_tolerance: int | None = Field(default=None, ge=0)
    chapter_sketch: list[ChapterSketch] = Field(min_length=1)
    scope_summary: str = Field(min_length=1)
    approved: bool = False
    approved_at: datetime | None = None

    @model_validator(mode="after")
    def validate_approval_and_tolerance(self) -> "ProductionBrief":
        if self.page_tolerance is not None and self.page_tolerance >= self.target_pages:
            raise ValueError("page_tolerance must be smaller than target_pages")
        if self.approved and self.approved_at is None:
            raise ValueError("approved production brief requires approved_at")
        if not self.approved and self.approved_at is not None:
            raise ValueError("approved_at is set only when the brief is approved")
        return self


class ConsideredExclusion(Model):
    topic: str
    decision: str = Field(pattern=r"^(included|deferred|excluded)$")
    rationale: str = Field(min_length=1)

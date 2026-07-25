"""Source records used by acquisition / freeze (not LLM claim graphs)."""

from datetime import date
from enum import StrEnum

from pydantic import Field

from textbook_writer.models.base import HttpsUrl, Model


class SourceAuthority(StrEnum):
    PRIMARY = "primary"
    OFFICIAL = "official"
    REVIEW = "review"
    CANONICAL = "canonical"
    PRACTITIONER = "practitioner"
    ANECDOTAL = "anecdotal"
    UNKNOWN = "unknown"


class SourceRecord(Model):
    source_id: str
    source_type: str
    title: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1000, le=9999)
    url: HttpsUrl
    accessed_at: date
    authority: SourceAuthority
    license_note: str | None = None

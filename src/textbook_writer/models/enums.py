"""Shared enums used by discovery models."""

from enum import StrEnum


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

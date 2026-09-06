"""Uniform model routing with explicit per-role overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PipelineModels:
    manager: str
    research: str
    curriculum: str
    writer: str
    reviewer: str
    solver: str
    comparator: str
    diagram: str
    publication_reviewer: str

    @classmethod
    def from_base(cls, base_model: str) -> "PipelineModels":
        """Use the selected model throughout, unless a role is explicitly overridden."""

        defaults = {field: base_model for field in cls.__dataclass_fields__}
        for role in defaults:
            override = os.environ.get(f"TEXTBOOK_MODEL_{role.upper()}")
            if override:
                defaults[role] = override
        return cls(**defaults)

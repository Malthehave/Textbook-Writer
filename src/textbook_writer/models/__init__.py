"""Plain pydantic models for the textbook pipeline."""

from textbook_writer.models.discovery import ChapterSketch, ProductionBrief
from textbook_writer.models.evidence import SourceAuthority, SourceRecord
from textbook_writer.models.product import (
    ContentEvidenceCitation,
    ContinuityAudit,
    ExerciseVerification,
    FrozenEvidenceChunk,
    IndependentAnswerSet,
    PlanAudit,
    ProductBook,
    ProductBookPlan,
    ProductChapter,
    ResearchAudit,
    ResearchDossier,
)
from textbook_writer.models.research import (
    AcquisitionBatch,
    AcquisitionFailure,
    AcquisitionManifest,
    AcquisitionRecord,
    ResearchScoutOutput,
    ResearchScoutRun,
    SearchCitation,
    SourceEvidencePacket,
    SourceTextChunk,
)

__all__ = [
    "AcquisitionBatch",
    "AcquisitionFailure",
    "AcquisitionManifest",
    "AcquisitionRecord",
    "ChapterSketch",
    "ContentEvidenceCitation",
    "ContinuityAudit",
    "ExerciseVerification",
    "FrozenEvidenceChunk",
    "IndependentAnswerSet",
    "PlanAudit",
    "ProductBook",
    "ProductBookPlan",
    "ProductChapter",
    "ProductionBrief",
    "ResearchAudit",
    "ResearchDossier",
    "ResearchScoutOutput",
    "ResearchScoutRun",
    "SearchCitation",
    "SourceAuthority",
    "SourceEvidencePacket",
    "SourceRecord",
    "SourceTextChunk",
]

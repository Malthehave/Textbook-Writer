"""Contracts for reproducible research acquisition and evidence-pack assembly."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from textbook_writer.models.base import HttpsUrl, Model
from textbook_writer.models.discovery import ConsideredExclusion, Inference
from textbook_writer.models.evidence import SourceRecord


class ResearchQuestion(Model):
    question_id: str
    question: str = Field(min_length=1)
    required: bool = True
    freshness: str = Field(default="stable", pattern=r"^(stable|current)$")


class QueryFamily(Model):
    family_id: str
    purpose: str = Field(
        pattern=r"^(target-analysis|primary-official|canonical-coverage|current-research|omission-challenge|implementation-context)$"
    )
    queries: list[str] = Field(min_length=1)


class SourceFixture(Model):
    """A reviewed source plus a frozen local snapshot used by reproducible builds."""

    source: SourceRecord
    snapshot_path: str = Field(min_length=1)
    media_type: str = Field(
        pattern=r"^(text/plain|text/html|application/xhtml\+xml|application/pdf)$"
    )


class LiveSourceRequest(Model):
    source: SourceRecord
    accepted_media_types: list[str] = Field(min_length=1)
    max_bytes: int = Field(default=25_000_000, ge=1, le=100_000_000)


class AcquisitionManifest(Model):
    acquisition_manifest_id: str
    acquired_by_run: str
    allowed_hosts: list[str] = Field(min_length=1)
    sources: list[LiveSourceRequest] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_sources_and_hosts(self) -> "AcquisitionManifest":
        source_ids = [item.source.source_id for item in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("duplicate live source IDs are not allowed")
        normalized_hosts = [item.strip().lower().rstrip(".") for item in self.allowed_hosts]
        if any(not item for item in normalized_hosts):
            raise ValueError("allowed hosts cannot be empty")
        if len(normalized_hosts) != len(set(normalized_hosts)):
            raise ValueError("duplicate allowed hosts are not allowed")
        return self


class AcquisitionFailure(Model):
    """A reviewed source URL that could not be frozen for evidence use."""

    source_id: str
    requested_url: HttpsUrl
    error: str = Field(min_length=1)


class AcquisitionRecord(Model):
    acquisition_id: str
    source_id: str
    requested_url: HttpsUrl
    resolved_url: HttpsUrl
    retrieved_at: datetime
    media_type: str = Field(min_length=1)
    content_hash: str
    byte_length: int = Field(ge=1)
    extractor_version: str = Field(min_length=1)
    snapshot_path: str = Field(min_length=1)
    treated_as_untrusted: bool = True

    @model_validator(mode="after")
    def require_untrusted_boundary(self) -> "AcquisitionRecord":
        if not self.treated_as_untrusted:
            raise ValueError("retrieved source content must be treated as untrusted")
        return self


class AcquisitionBatch(Model):
    acquisition_batch_id: str
    manifest_ref: str
    acquired_by_run: str
    acquisitions: list[AcquisitionRecord] = Field(min_length=1)
    source_fixtures: list[SourceFixture] = Field(min_length=1)

    @model_validator(mode="after")
    def require_matching_sources(self) -> "AcquisitionBatch":
        acquired = {item.source_id for item in self.acquisitions}
        frozen = {item.source.source_id for item in self.source_fixtures}
        if acquired != frozen:
            raise ValueError("acquisition records and frozen source fixtures must match")
        return self


class SourceTextChunk(Model):
    chunk_id: str
    source_ref: str
    page: int | None = Field(default=None, ge=1)
    text: str = Field(min_length=1, max_length=12_000)
    content_hash: str


class SourceEvidencePacket(Model):
    packet_id: str
    acquisition_ref: str
    source: SourceRecord
    question_refs: list[str] = Field(min_length=1)
    chunks: list[SourceTextChunk] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_chunks(self) -> "SourceEvidencePacket":
        chunk_ids = [chunk.chunk_id for chunk in self.chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("source evidence packet chunk IDs must be unique")
        if any(chunk.source_ref != self.source.source_id for chunk in self.chunks):
            raise ValueError("source evidence packet chunks must match the packet source")
        return self


class SearchCitation(Model):
    citation_id: str
    response_id: str | None = None
    url: HttpsUrl
    title: str = Field(min_length=1)
    start_index: int | None = Field(default=None, ge=0)
    end_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_span(self) -> "SearchCitation":
        if (self.start_index is None) != (self.end_index is None):
            raise ValueError("search citation indices must be both present or both absent")
        if (
            self.start_index is not None
            and self.end_index is not None
            and self.start_index > self.end_index
        ):
            raise ValueError("search citation start_index cannot exceed end_index")
        return self


class SourceLead(Model):
    source_lead_id: str
    url: HttpsUrl
    title: str = Field(min_length=1)
    likely_authority: str = Field(
        pattern=r"^(primary|official|review|canonical|practitioner|anecdotal|unknown)$"
    )
    query_family_refs: list[str] = Field(min_length=1)
    question_refs: list[str] = Field(min_length=1)
    relevance: str = Field(min_length=1)
    acquisition_reason: str = Field(min_length=1)


class CandidateCompetency(Model):
    competency_id: str
    label: str = Field(min_length=1)
    priority: str = Field(pattern=r"^(required|high|supporting|deferred)$")
    rationale: str = Field(min_length=1)
    prerequisite_competencies: list[str] = Field(default_factory=list)
    source_lead_refs: list[str] = Field(min_length=1)


class ResearchScoutOutput(Model):
    scout_output_id: str
    interpreted_goal: str = Field(min_length=1)
    confirmed: list[str] = Field(min_length=1)
    inferred: list[Inference] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    research_questions: list[ResearchQuestion] = Field(min_length=1)
    query_families: list[QueryFamily] = Field(min_length=1)
    source_leads: list[SourceLead] = Field(min_length=1)
    candidate_competencies: list[CandidateCompetency] = Field(min_length=1)
    considered_exclusions: list[ConsideredExclusion] = Field(default_factory=list)
    coverage_risks: list[str] = Field(min_length=1)
    stopping_reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_candidate_graph(self) -> "ResearchScoutOutput":
        question_ids = _unique_values(
            "research question", [item.question_id for item in self.research_questions]
        )
        family_ids = _unique_values(
            "query family", [item.family_id for item in self.query_families]
        )
        lead_ids = _unique_values(
            "source lead", [item.source_lead_id for item in self.source_leads]
        )
        competency_ids = _unique_values(
            "candidate competency",
            [item.competency_id for item in self.candidate_competencies],
        )
        required_purposes = {
            "target-analysis",
            "primary-official",
            "canonical-coverage",
            "omission-challenge",
        }
        if any(
            item.required and item.freshness == "current"
            for item in self.research_questions
        ):
            required_purposes.add("current-research")
        present_purposes = {item.purpose for item in self.query_families}
        missing_purposes = required_purposes - present_purposes
        if missing_purposes:
            raise ValueError(
                f"research scout lacks required query purposes: {sorted(missing_purposes)}"
            )
        for lead in self.source_leads:
            _require_known(
                f"source lead {lead.source_lead_id} query families",
                lead.query_family_refs,
                family_ids,
            )
            _require_known(
                f"source lead {lead.source_lead_id} questions",
                lead.question_refs,
                question_ids,
            )
        for competency in self.candidate_competencies:
            _require_known(
                f"candidate competency {competency.competency_id} prerequisites",
                competency.prerequisite_competencies,
                competency_ids,
            )
            _require_known(
                f"candidate competency {competency.competency_id} source leads",
                competency.source_lead_refs,
                lead_ids,
            )
            if competency.priority not in {"required", "high"}:
                continue
            if len(set(competency.source_lead_refs)) < 2:
                raise ValueError(
                    f"candidate competency {competency.competency_id} requires at least two independent source leads"
                )
            referenced = [
                lead
                for lead in self.source_leads
                if lead.source_lead_id in competency.source_lead_refs
            ]
            weak = {
                lead.source_lead_id
                for lead in referenced
                if lead.likely_authority in {"anecdotal", "unknown"}
            }
            if weak:
                raise ValueError(
                    f"candidate competency {competency.competency_id} relies on non-credible leads: {sorted(weak)}"
                )
            if not any(
                lead.likely_authority in {"official", "practitioner"}
                for lead in referenced
            ):
                raise ValueError(
                    f"candidate competency {competency.competency_id} lacks an official or practitioner usage signal"
                )
        return self


class ResearchScoutRun(Model):
    scout_run_id: str
    book_ref: str
    model: str = Field(min_length=1)
    session_id: str
    response_ids: list[str] = Field(min_length=1)
    web_search_calls: int = Field(ge=1)
    citations: list[SearchCitation] = Field(min_length=1)
    output: ResearchScoutOutput

    @model_validator(mode="after")
    def require_native_citations_for_every_lead(self) -> "ResearchScoutRun":
        non_https = {
            str(item.url)
            for item in self.output.source_leads
            if urlsplit(str(item.url)).scheme.lower() != "https"
        }
        if non_https:
            raise ValueError(
                f"research scout source leads must use HTTPS: {sorted(non_https)}"
            )
        cited_urls = {str(item.url) for item in self.citations}
        uncited = {
            str(item.url) for item in self.output.source_leads
        } - cited_urls
        if uncited:
            raise ValueError(
                f"research scout source leads lack native web-search citations: {sorted(uncited)}"
            )
        return self


def _unique_values(kind: str, values: list[str]) -> set[str]:
    result = set(values)
    if len(result) != len(values):
        raise ValueError(f"duplicate {kind} IDs are not allowed")
    return result


def _require_known(label: str, requested: list[str], available: set[str]) -> None:
    missing = set(requested) - available
    if missing:
        raise ValueError(f"{label} contain missing IDs: {sorted(missing)}")

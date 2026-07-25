"""Production book models."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from textbook_writer.models.base import HttpsUrl, Model
from textbook_writer.models.research import AcquisitionBatch


PRACTICE_AUTHORITIES = {"official", "practitioner"}


class ProductSource(Model):
    source_id: str
    title: str = Field(min_length=1)
    url: HttpsUrl
    authority: str = Field(
        pattern=r"^(primary|official|review|canonical|practitioner)$"
    )
    credibility_rationale: str = Field(min_length=1)
    publication_year: int | None = Field(default=None, ge=1000, le=9999)


class GroundedClaim(Model):
    claim_id: str
    statement: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    limitation: str | None = None


class ResearchedTopic(Model):
    topic_id: str
    title: str = Field(min_length=1)
    why_required: str = Field(min_length=1)
    real_world_use: str = Field(min_length=1)
    learning_outcomes: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(min_length=2)
    practice_source_refs: list[str] = Field(min_length=1)
    claims: list[GroundedClaim] = Field(min_length=1)
    teaching_brief: str = Field(min_length=120)


def attach_claim_sources_to_topics(data: object) -> object:
    """Promote claim citations onto the owning topic before grounding checks."""

    if not isinstance(data, dict):
        return data
    sources = data.get("sources")
    topics = data.get("topics")
    if not isinstance(sources, list) or not isinstance(topics, list):
        return data
    source_ids = {
        item.get("source_id")
        for item in sources
        if isinstance(item, dict) and isinstance(item.get("source_id"), str)
    }
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        source_refs = topic.get("source_refs")
        practice_refs = topic.get("practice_source_refs")
        claims = topic.get("claims")
        if not isinstance(source_refs, list) or not isinstance(claims, list):
            continue
        known = {
            ref
            for ref in source_refs + (practice_refs if isinstance(practice_refs, list) else [])
            if isinstance(ref, str)
        }
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            claim_refs = claim.get("source_refs")
            if not isinstance(claim_refs, list):
                continue
            for ref in claim_refs:
                if isinstance(ref, str) and ref in source_ids and ref not in known:
                    source_refs.append(ref)
                    known.add(ref)
        topic["source_refs"] = source_refs
    return data


class ResearchDossier(Model):
    dossier_id: str
    title: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    learning_goal: str = Field(min_length=1)
    sources: list[ProductSource] = Field(min_length=2)
    topics: list[ResearchedTopic] = Field(min_length=1)
    exclusions: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def attach_claim_sources_to_topics(cls, data: object) -> object:
        return attach_claim_sources_to_topics(data)

    @model_validator(mode="after")
    def validate_grounding(self) -> "ResearchDossier":
        source_by_id = {item.source_id: item for item in self.sources}
        if len(source_by_id) != len(self.sources):
            raise ValueError("research dossier source IDs must be unique")
        topic_ids = {item.topic_id for item in self.topics}
        if len(topic_ids) != len(self.topics):
            raise ValueError("research dossier topic IDs must be unique")
        for topic in self.topics:
            refs = set(topic.source_refs)
            practice = set(topic.practice_source_refs)
            all_refs = refs | practice
            missing = all_refs - set(source_by_id)
            if missing:
                raise ValueError(
                    f"topic {topic.topic_id} references missing sources: {sorted(missing)}"
                )
            if len(all_refs) < 2:
                raise ValueError(f"topic {topic.topic_id} requires two credible sources")
            hosts = {
                urlsplit(str(source_by_id[ref].url)).hostname for ref in all_refs
            }
            if None in hosts or len(hosts) < 2:
                raise ValueError(
                    f"topic {topic.topic_id} requires sources from two independent hosts"
                )
            if not any(source_by_id[ref].authority in PRACTICE_AUTHORITIES for ref in practice):
                raise ValueError(
                    f"topic {topic.topic_id} lacks an official or practitioner practice signal"
                )
            for claim in topic.claims:
                claim_refs = set(claim.source_refs)
                if not claim_refs or not claim_refs.issubset(all_refs):
                    raise ValueError(
                        f"claim {claim.claim_id} must reference its topic's sources"
                    )
        return self


class TopicAudit(Model):
    topic_ref: str
    source_refs_checked: list[str] = Field(min_length=2)
    relevance: str = Field(pattern=r"^(confirmed|weak|unsupported)$")
    accuracy: str = Field(pattern=r"^(confirmed|qualified|contradicted)$")
    practice_signal: str = Field(pattern=r"^(confirmed|weak|missing)$")
    notes: str = Field(min_length=1)


class ResearchAudit(Model):
    dossier_ref: str
    topic_audits: list[TopicAudit] = Field(min_length=1)
    missing_topics: list[str] = Field(default_factory=list)
    low_value_topics: list[str] = Field(default_factory=list)
    decision: str = Field(pattern=r"^(approve|revise|reject)$")


class PlannedVisual(Model):
    """One required pedagogical diagram slot for a planned chapter (HTML figure)."""

    visual_id: str
    diagram_type: str = Field(pattern=r"^(architecture|process-flow)$")
    learning_purpose: str = Field(min_length=1)
    caption: str = Field(min_length=1)


class RunningSystemComponent(Model):
    """Glossary entry for a named component in the shared running system."""

    component_id: str
    name: str = Field(min_length=1)
    definition: str = Field(min_length=20)
    first_chapter_ref: str


class PlannedChapter(Model):
    chapter_id: str
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    topic_refs: list[str] = Field(min_length=1)
    supporting_topic_refs: list[str] = Field(default_factory=list)
    learning_outcomes: list[str] = Field(min_length=1)
    target_words: int = Field(ge=250)
    exercise_count: int = Field(ge=1, le=20)
    assessment_brief: str | None = Field(default=None, min_length=40)
    visual: PlannedVisual | None = None


class ProductBookPlan(Model):
    plan_id: str
    title: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    learning_goal: str = Field(min_length=1)
    target_pages: int = Field(ge=1)
    running_system: str = Field(
        default="",
        description=(
            "Shared protagonist system that chapters evolve together "
            "(e.g. a rollout worker plus trainer and checkpoint path)."
        ),
    )
    glossary: list[RunningSystemComponent] = Field(default_factory=list)
    chapters: list[PlannedChapter] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan(self) -> "ProductBookPlan":
        chapter_ids = {item.chapter_id for item in self.chapters}
        if len(chapter_ids) != len(self.chapters):
            raise ValueError("product book plan chapter IDs must be unique")
        return self


class PlanAudit(Model):
    plan_ref: str
    missing_topic_refs: list[str] = Field(default_factory=list)
    ordering_issues: list[str] = Field(default_factory=list)
    outcome_issues: list[str] = Field(default_factory=list)
    padding_risks: list[str] = Field(default_factory=list)
    decision: str = Field(pattern=r"^(approve|revise|reject)$")


class ProductSection(Model):
    section_id: str
    title: str = Field(min_length=1)
    markdown: str = Field(min_length=1)
    topic_refs: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)


class ProductExercise(Model):
    exercise_id: str
    learning_outcome: str = Field(min_length=1)
    exercise_type: str = Field(
        pattern=r"^(recall|conceptual|derivation|coding|applied|synthesis|debugging|system-design)$"
    )
    difficulty: str = Field(pattern=r"^(introductory|intermediate|advanced|challenge)$")
    prompt: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    source_refs: list[str] = Field(default_factory=list)


class ProductFigure(Model):
    """Chapter figure: skill-authored HTML diagram rendered to a PNG asset."""

    figure_id: str
    caption: str = Field(min_length=1)
    learning_purpose: str = Field(min_length=1)
    section_ref: str | None = None
    html: str = Field(min_length=1)
    asset_path: str = Field(min_length=1)
    content_sha256: str

    @model_validator(mode="after")
    def validate_figure_payload(self) -> "ProductFigure":
        path = PurePosixPath(self.asset_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("figure asset_path must be a safe workspace-relative path")
        return self


class ProductChapter(Model):
    chapter_id: str
    title: str = Field(min_length=1)
    introduction: str = Field(min_length=1)
    learning_outcomes: list[str] = Field(min_length=1)
    sections: list[ProductSection] = Field(min_length=1)
    figures: list[ProductFigure] = Field(default_factory=list)
    bridge_from_previous: str = ""
    exercises: list[ProductExercise] = Field(min_length=1)
    summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ids(self) -> "ProductChapter":
        section_ids = {item.section_id for item in self.sections}
        exercise_ids = {item.exercise_id for item in self.exercises}
        figure_ids = {item.figure_id for item in self.figures}
        if len(section_ids) != len(self.sections):
            raise ValueError("chapter section IDs must be unique")
        if len(exercise_ids) != len(self.exercises):
            raise ValueError("chapter exercise IDs must be unique")
        if len(figure_ids) != len(self.figures):
            raise ValueError("chapter figure IDs must be unique")
        for figure in self.figures:
            if figure.section_ref is not None and figure.section_ref not in section_ids:
                raise ValueError(
                    f"figure {figure.figure_id} references unknown section {figure.section_ref}"
                )
        return self


class IndependentAnswer(Model):
    exercise_ref: str
    answer: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    ambiguity: str = Field(pattern=r"^(none|minor|material)$")
    source_refs: list[str] = Field(default_factory=list)


class IndependentAnswerSet(Model):
    chapter_ref: str
    answers: list[IndependentAnswer] = Field(min_length=1)


class ExerciseVerdict(Model):
    exercise_ref: str
    result: str = Field(pattern=r"^(equivalent|compatible|different)$")
    ambiguity: str = Field(pattern=r"^(none|minor|material)$")
    source_support: str = Field(pattern=r"^(sufficient|insufficient|not-required)$")
    notes: str = Field(min_length=1)
    decision: str = Field(pattern=r"^(approve|revise|reject)$")


class ExerciseVerification(Model):
    chapter_ref: str
    verdicts: list[ExerciseVerdict] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_verdicts(self) -> "ExerciseVerification":
        refs = {item.exercise_ref for item in self.verdicts}
        if len(refs) != len(self.verdicts):
            raise ValueError("exercise verification refs must be unique")
        return self


class ContinuityAudit(Model):
    chapter_refs: list[str] = Field(min_length=1)
    concept_order_issues: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    repetition_issues: list[str] = Field(default_factory=list)
    missing_connections: list[str] = Field(default_factory=list)
    decision: str = Field(pattern=r"^(approve|revise|reject)$")


class FrozenEvidenceChunk(Model):
    packet_ref: str
    chunk_ref: str
    source_ref: str
    page: int | None = Field(default=None, ge=1)
    content_hash: str


class ContentEvidenceCitation(Model):
    content_ref: str
    source_ref: str
    chunk_ref: str
    lexical_score: float = Field(ge=0, le=1)


class ProductBook(Model):
    book_id: str
    dossier: ResearchDossier
    research_audit: ResearchAudit
    plan: ProductBookPlan
    plan_audit: PlanAudit
    chapters: list[ProductChapter] = Field(min_length=1)
    exercise_verifications: list[ExerciseVerification] = Field(min_length=1)
    continuity_audit: ContinuityAudit
    source_archive: AcquisitionBatch
    evidence_index: list[FrozenEvidenceChunk] = Field(min_length=1)
    citation_ledger: list[ContentEvidenceCitation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_book(self) -> "ProductBook":
        chapter_ids = {item.chapter_id for item in self.chapters}
        if len(chapter_ids) != len(self.chapters):
            raise ValueError("product book chapter IDs must be unique")
        plan_ids = {item.chapter_id for item in self.plan.chapters}
        if chapter_ids != plan_ids:
            raise ValueError("product book chapters must match the approved plan")
        source_ids = {item.source_id for item in self.dossier.sources}
        acquired = {item.source_id for item in self.source_archive.acquisitions}
        if source_ids - acquired:
            raise ValueError(
                f"product book missing acquired sources: {sorted(source_ids - acquired)}"
            )
        chunk_ids = {item.chunk_ref for item in self.evidence_index}
        if len(chunk_ids) != len(self.evidence_index):
            raise ValueError("evidence index chunk IDs must be unique")
        for citation in self.citation_ledger:
            if citation.source_ref not in source_ids:
                raise ValueError(
                    f"citation references missing source: {citation.source_ref}"
                )
            if citation.chunk_ref not in chunk_ids:
                raise ValueError(
                    f"citation references missing chunk: {citation.chunk_ref}"
                )
        verification_chapters = {
            item.chapter_ref for item in self.exercise_verifications
        }
        if verification_chapters != chapter_ids:
            raise ValueError("exercise verifications must cover every chapter exactly once")
        required_pairs = {
            (claim.claim_id, source_ref)
            for topic in self.dossier.topics
            for claim in topic.claims
            for source_ref in claim.source_refs
        }
        required_pairs.update(
            (section.section_id, source_ref)
            for chapter in self.chapters
            for section in chapter.sections
            for source_ref in section.source_refs
        )
        required_pairs.update(
            (exercise.exercise_id, source_ref)
            for chapter in self.chapters
            for exercise in chapter.exercises
            for source_ref in exercise.source_refs
        )
        present_pairs = {
            (item.content_ref, item.source_ref) for item in self.citation_ledger
        }
        missing_pairs = required_pairs - present_pairs
        if missing_pairs:
            raise ValueError(
                "researched claims, teaching sections, and exercises require exact "
                f"frozen evidence citations: {sorted(missing_pairs)}"
            )
        return self

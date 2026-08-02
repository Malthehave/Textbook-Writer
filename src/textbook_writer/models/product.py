"""Book pipeline models."""

from __future__ import annotations

from pathlib import PurePosixPath

from pydantic import Field, model_validator

from textbook_writer.models.base import HttpsUrl, Model


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
    rationale: str | None = None
    learning_outcomes: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    claims: list[GroundedClaim] = Field(min_length=1)


class Research(Model):
    """Sources + topics written by the research architect."""

    research_id: str
    title: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    learning_goal: str = Field(min_length=1)
    sources: list[ProductSource] = Field(min_length=1)
    topics: list[ResearchedTopic] = Field(min_length=1)
    exclusions: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ids(self) -> "Research":
        source_ids = {item.source_id for item in self.sources}
        if len(source_ids) != len(self.sources):
            raise ValueError("research source IDs must be unique")
        topic_ids = {item.topic_id for item in self.topics}
        if len(topic_ids) != len(self.topics):
            raise ValueError("research topic IDs must be unique")
        return self


class PlannedVisual(Model):
    visual_id: str
    diagram_type: str = Field(pattern=r"^(architecture|process-flow)$")
    learning_purpose: str = Field(min_length=1)
    caption: str = Field(min_length=1)


class RunningSystemComponent(Model):
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
    running_system: str = Field(default="")
    glossary: list[RunningSystemComponent] = Field(default_factory=list)
    chapters: list[PlannedChapter] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan(self) -> "ProductBookPlan":
        chapter_ids = {item.chapter_id for item in self.chapters}
        if len(chapter_ids) != len(self.chapters):
            raise ValueError("book plan chapter IDs must be unique")
        return self


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


class ProductBook(Model):
    """Assembled book: stage JSON glued together for PDF publish."""

    book_id: str
    research: Research
    plan: ProductBookPlan
    chapters: list[ProductChapter] = Field(min_length=1)
    exercise_verifications: list[ExerciseVerification] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_book(self) -> "ProductBook":
        chapter_ids = {item.chapter_id for item in self.chapters}
        if len(chapter_ids) != len(self.chapters):
            raise ValueError("product book chapter IDs must be unique")
        plan_ids = {item.chapter_id for item in self.plan.chapters}
        if chapter_ids != plan_ids:
            raise ValueError("product book chapters must match the approved plan")
        verification_chapters = {
            item.chapter_ref for item in self.exercise_verifications
        }
        if verification_chapters != chapter_ids:
            raise ValueError("exercise verifications must cover every chapter exactly once")
        return self

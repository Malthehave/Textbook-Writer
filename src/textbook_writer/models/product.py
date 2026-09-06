"""Book pipeline models."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import PurePosixPath
from urllib.parse import urlsplit

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
    authors: list[str] = Field(default_factory=list)
    accessed_date: str | None = None


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
    title: str = Field(
        min_length=1,
        description=(
            "Working title for the eventual textbook: specific to the subject and "
            "learner goal; used as the seed for the published book title."
        ),
    )
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
        sources_by_id = {item.source_id: item for item in self.sources}
        for topic in self.topics:
            refs = set(topic.source_refs)
            if not refs <= source_ids:
                raise ValueError(f"{topic.topic_id} references unknown research sources")
            if len(refs) < 2:
                raise ValueError(f"{topic.topic_id} needs at least two sources")
            hosts = {urlsplit(sources_by_id[ref].url).hostname for ref in refs}
            if len(hosts) < 2:
                raise ValueError(f"{topic.topic_id} needs sources from two independent hosts")
            if not any(
                sources_by_id[ref].authority in {"official", "practitioner"}
                for ref in refs
            ):
                raise ValueError(
                    f"{topic.topic_id} needs an official or practitioner source"
                )
            for claim in topic.claims:
                if not set(claim.source_refs) <= refs:
                    raise ValueError(
                        f"{claim.claim_id} source refs must belong to {topic.topic_id}"
                    )
        return self


class PlannedVisual(Model):
    visual_id: str
    diagram_type: str = Field(min_length=1)
    learning_purpose: str = Field(min_length=1)
    caption: str = Field(min_length=1)


class RunningSystemComponent(Model):
    component_id: str
    name: str = Field(min_length=1)
    definition: str = Field(min_length=20)
    first_chapter_ref: str


class PublicationPageBudget(Model):
    """Whole-book page allocation authored before expensive chapter generation."""

    front_matter: int = Field(ge=0)
    chapter_prose: int = Field(ge=1)
    figures: int = Field(ge=0)
    exercises: int = Field(ge=0)
    solutions: int = Field(ge=0)
    bibliography: int = Field(ge=0)

    @property
    def total(self) -> int:
        return (
            self.front_matter
            + self.chapter_prose
            + self.figures
            + self.exercises
            + self.solutions
            + self.bibliography
        )


class PlannedChapter(Model):
    chapter_id: str
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    central_question: str = Field(
        min_length=1,
        description=(
            "The single learner-facing question that gives the chapter narrative direction."
        ),
    )
    narrative_arc: str = Field(
        min_length=1,
        description=(
            "A prose brief for how the chapter moves from the opening problem through "
            "explanation and evidence to a resolved capability; not a topic list."
        ),
    )
    anchor_example: str = Field(
        min_length=1,
        description=(
            "The concrete example, case, or artifact threaded through the chapter so "
            "abstract ideas have a stable referent."
        ),
    )
    builds_on: str = Field(
        min_length=1,
        description=(
            "What the reader already understands or has built before this chapter begins."
        ),
    )
    hands_off: str = Field(
        min_length=1,
        description=(
            "The capability, artifact, or unresolved question this chapter gives the next "
            "chapter or the learner after the final chapter."
        ),
    )
    topic_refs: list[str] = Field(min_length=1)
    supporting_topic_refs: list[str] = Field(default_factory=list)
    learning_outcomes: list[str] = Field(min_length=1)
    target_words: int = Field(ge=250)
    exercise_count: int = Field(ge=1, le=20)
    assessment_brief: str = Field(min_length=40)
    visual: PlannedVisual | None = None
    personalization_brief: str = Field(min_length=40)
    project_milestone: str = Field(min_length=40)
    practice_brief: str = Field(min_length=40)
    reader_starting_point: str = ""
    conceptual_obstacle: str = ""
    intuition_bridge: str = ""
    worked_example_progression: str = ""
    mechanisms_to_explain: list[str] = Field(default_factory=list)
    likely_misconceptions: list[str] = Field(default_factory=list)
    evidence_or_demonstration: str = ""
    practice_progression: str = ""


class ProductBookPlan(Model):
    plan_id: str
    title: str = Field(
        min_length=1,
        description=(
            "Published book title for the cover, table of contents, and PDF filename. "
            "Must name the subject for the learner; never a tool/status/reply string."
        ),
    )
    audience: str = Field(min_length=1)
    learning_goal: str = Field(min_length=1)
    target_pages: int = Field(ge=1)
    iteration_mode: str = Field(
        default="production",
        pattern=r"^(prototype|quality-slice|short-book|production)$",
    )
    solution_mode: str = Field(
        default="concise", pattern=r"^(concise|full|separate)$"
    )
    page_budget: PublicationPageBudget
    study_path: str = ""
    implementation_project: str = ""
    personalization_strategy: str = Field(min_length=40)
    running_system: str = Field(default="")
    glossary: list[RunningSystemComponent] = Field(default_factory=list)
    chapters: list[PlannedChapter] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan(self) -> "ProductBookPlan":
        normalized_title = re.sub(r"[^a-z0-9]+", " ", self.title.lower()).strip()
        status_titles = {
            "book plan created",
            "book plan complete",
            "textbook created",
            "textbook complete",
            "plan created",
            "plan complete",
        }
        if normalized_title in status_titles:
            raise ValueError("book title must name the subject, not report pipeline status")
        if abs(self.page_budget.total - self.target_pages) > 1:
            raise ValueError("page budget components must sum to the target pages within one page")
        chapter_ids = {item.chapter_id for item in self.chapters}
        if len(chapter_ids) != len(self.chapters):
            raise ValueError("book plan chapter IDs must be unique")
        for chapter in self.chapters:
            if (
                self.iteration_mode == "production"
                and chapter.exercise_count < len(chapter.learning_outcomes)
            ):
                raise ValueError(
                    f"{chapter.chapter_id} needs at least one exercise per learning outcome"
                )
        if self.iteration_mode == "prototype":
            if any(chapter.target_words > 750 for chapter in self.chapters):
                raise ValueError("prototype chapters may target at most 750 words")
            if any(chapter.exercise_count > 1 for chapter in self.chapters):
                raise ValueError("prototype chapters may have at most one exercise")
            if any(len(chapter.learning_outcomes) > 1 for chapter in self.chapters):
                raise ValueError("prototype chapters may have at most one composite outcome")
            if sum(chapter.visual is not None for chapter in self.chapters) > 2:
                raise ValueError("prototype books may have at most two visuals")
        if self.iteration_mode in {"quality-slice", "short-book"}:
            required_experience_fields = {
                "reader_starting_point": lambda chapter: chapter.reader_starting_point,
                "conceptual_obstacle": lambda chapter: chapter.conceptual_obstacle,
                "intuition_bridge": lambda chapter: chapter.intuition_bridge,
                "worked_example_progression": lambda chapter: chapter.worked_example_progression,
                "mechanisms_to_explain": lambda chapter: chapter.mechanisms_to_explain,
                "likely_misconceptions": lambda chapter: chapter.likely_misconceptions,
                "evidence_or_demonstration": lambda chapter: chapter.evidence_or_demonstration,
                "practice_progression": lambda chapter: chapter.practice_progression,
            }
            for chapter in self.chapters:
                missing = [
                    name
                    for name, getter in required_experience_fields.items()
                    if not getter(chapter)
                ]
                if missing:
                    raise ValueError(
                        f"{chapter.chapter_id} is missing reader-experience briefs: "
                        + ", ".join(missing)
                    )
                if chapter.exercise_count < len(chapter.learning_outcomes):
                    raise ValueError(
                        f"{chapter.chapter_id} needs at least one exercise per learning outcome"
                    )
        if self.iteration_mode == "quality-slice":
            if not 8 <= self.target_pages <= 10:
                raise ValueError("quality-slice books must target 8 to 10 pages")
            if len(self.chapters) != 1:
                raise ValueError("quality-slice books must contain exactly one chapter")
            chapter = self.chapters[0]
            if not 1500 <= chapter.target_words <= 2200:
                raise ValueError("a quality-slice chapter must target 1500 to 2200 words")
            if not 2 <= len(chapter.learning_outcomes) <= 3:
                raise ValueError("a quality-slice chapter needs 2 to 3 learning outcomes")
            if not 2 <= chapter.exercise_count <= 3:
                raise ValueError("a quality-slice chapter needs 2 to 3 progressive exercises")
            if sum(item.visual is not None for item in self.chapters) > 1:
                raise ValueError("quality-slice books may have at most one visual")
        if self.iteration_mode == "short-book":
            if not 18 <= self.target_pages <= 28:
                raise ValueError("short books must target 18 to 28 pages")
            if not 2 <= len(self.chapters) <= 3:
                raise ValueError("short books must contain 2 to 3 chapters")
            total_words = sum(chapter.target_words for chapter in self.chapters)
            if not 5000 <= total_words <= 8000:
                raise ValueError("short books must target 5000 to 8000 words in total")
            if any(not 2 <= chapter.exercise_count <= 4 for chapter in self.chapters):
                raise ValueError("each short-book chapter needs 2 to 4 exercises")
        if self.target_pages <= 6:
            if len(self.chapters) > 1:
                raise ValueError("books of 6 pages or fewer may have at most 1 chapter")
            if sum(chapter.exercise_count for chapter in self.chapters) > 3:
                raise ValueError("books of 6 pages or fewer may have at most 3 exercises")
            if sum(chapter.visual is not None for chapter in self.chapters) > 1:
                raise ValueError("books of 6 pages or fewer may have at most 1 visual")
        elif self.target_pages <= 8:
            if len(self.chapters) > 2:
                raise ValueError("books of 8 pages or fewer may have at most 2 chapters")
            if sum(chapter.exercise_count for chapter in self.chapters) > 6:
                raise ValueError("books of 8 pages or fewer may have at most 6 exercises")
            if sum(chapter.visual is not None for chapter in self.chapters) > 2:
                raise ValueError("books of 8 pages or fewer may have at most 2 visuals")
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

    @model_validator(mode="after")
    def validate_draft_key(self) -> "ProductExercise":
        for label, value in (("answer", self.answer), ("reasoning", self.reasoning)):
            normalized = " ".join(value.lower().split())
            if _is_placeholder_text(normalized):
                raise ValueError(f"exercise {label} cannot be a learner-response placeholder")
        return self


class ProductFigure(Model):
    figure_id: str
    caption: str = Field(min_length=1)
    learning_purpose: str = Field(min_length=1)
    section_ref: str | None = None
    html: str = Field(min_length=1)
    asset_path: str = Field(min_length=1)

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
        intro = _normalized_prose(self.introduction)
        first = _normalized_prose(self.sections[0].markdown)
        if intro and (
            intro == first
            or (
                min(len(intro.split()), len(first.split())) >= 50
                and SequenceMatcher(None, intro, first).ratio() >= 0.92
            )
        ):
            raise ValueError("chapter introduction duplicates the first section")
        return self


class EditorialReviewNote(Model):
    category: str = Field(
        pattern=(
            r"^(continuity|scope|terminology|progression|pedagogy|summary|visual|exercise|"
            r"narrative|prose|analogy)$"
        )
    )
    evidence: str = Field(min_length=1)
    requested_change: str = Field(min_length=1)


class ChapterReview(Model):
    chapter_ref: str
    decision: str = Field(pattern=r"^(approve|revise)$")
    summary: str = Field(min_length=1)
    notes: list[EditorialReviewNote] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_decision_notes(self) -> "ChapterReview":
        if self.decision == "revise" and not self.notes:
            raise ValueError("a revise decision requires concrete review notes")
        return self


class ManuscriptReviewNote(Model):
    chapter_ref: str
    category: str = Field(
        pattern=(
            r"^(narrative|prose|continuity|repetition|voice|analogy|explanatory-depth|"
            r"paragraph-flow|sentence-rhythm|concept-scaffolding|example-continuity|"
            r"practice-progression|personalization)$"
        )
    )
    evidence: str = Field(min_length=1)
    requested_change: str = Field(min_length=1)


class ReaderExperienceScorecard(Model):
    narrative_coherence: int = Field(ge=1, le=5)
    explanatory_depth: int = Field(ge=1, le=5)
    paragraph_flow: int = Field(ge=1, le=5)
    sentence_rhythm: int = Field(ge=1, le=5)
    concept_scaffolding: int = Field(ge=1, le=5)
    example_continuity: int = Field(ge=1, le=5)
    practice_progression: int = Field(ge=1, le=5)
    voice_consistency: int = Field(ge=1, le=5)

    @property
    def minimum(self) -> int:
        return min(
            self.narrative_coherence,
            self.explanatory_depth,
            self.paragraph_flow,
            self.sentence_rhythm,
            self.concept_scaffolding,
            self.example_continuity,
            self.practice_progression,
            self.voice_consistency,
        )


class ManuscriptReview(Model):
    decision: str = Field(pattern=r"^(approve|revise)$")
    summary: str = Field(min_length=1)
    notes: list[ManuscriptReviewNote]
    reader_experience: ReaderExperienceScorecard | None = None

    @model_validator(mode="after")
    def validate_decision_notes(self) -> "ManuscriptReview":
        if self.decision == "revise" and not self.notes:
            raise ValueError("a manuscript revise decision requires concrete review notes")
        if (
            self.decision == "approve"
            and self.reader_experience is not None
            and self.reader_experience.minimum < 4
        ):
            raise ValueError(
                "an approved manuscript needs a score of at least 4 in every reader-experience dimension"
            )
        return self


class PublicationReviewIssue(Model):
    category: str = Field(
        pattern=(
            r"^(title|title-bounds|layout|legibility|solutions|bibliography|navigation|"
            r"blank-page|content)$"
        )
    )
    page: int | None = Field(default=None, ge=1)
    evidence: str = Field(min_length=1)
    requested_change: str = Field(min_length=1)


class PublicationReview(Model):
    pdf_path: str = Field(min_length=1)
    decision: str = Field(pattern=r"^(approve|revise)$")
    summary: str = Field(min_length=1)
    issues: list[PublicationReviewIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_decision_issues(self) -> "PublicationReview":
        if self.decision == "revise" and not self.issues:
            raise ValueError("a publication revise decision requires concrete issues")
        return self


class EditorialState(Model):
    accepted_chapter_refs: list[str] = Field(default_factory=list)
    established_concepts: list[str] = Field(default_factory=list)
    terminology: dict[str, str] = Field(default_factory=dict)
    running_system_state: list[str] = Field(default_factory=list)
    reusable_examples: list[str] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)


class BlindAnswer(Model):
    exercise_ref: str
    answer: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    ambiguity: str = Field(pattern=r"^(none|minor|material)$")
    source_refs: list[str] = Field(default_factory=list)
    rubric: str | None = Field(default=None, min_length=20, max_length=1500)

    @model_validator(mode="after")
    def validate_solution(self) -> "BlindAnswer":
        if _is_placeholder_text(" ".join(self.answer.lower().split())):
            raise ValueError("independent answer cannot be a learner-response placeholder")
        if _is_placeholder_text(" ".join(self.reasoning.lower().split())):
            raise ValueError("independent reasoning cannot be a learner-response placeholder")
        return self


class BlindAnswers(Model):
    chapter_ref: str
    answers: list[BlindAnswer] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_answers(self) -> "BlindAnswers":
        refs = {item.exercise_ref for item in self.answers}
        if len(refs) != len(self.answers):
            raise ValueError("blind answer exercise refs must be unique")
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
        for verdict in self.verdicts:
            if verdict.decision == "approve" and (
                verdict.result == "different"
                or verdict.ambiguity == "material"
                or verdict.source_support == "insufficient"
            ):
                raise ValueError(
                    f"{verdict.exercise_ref} cannot be approved with a material defect"
                )
        return self


class ProductBook(Model):
    """Assembled book: stage JSON glued together for PDF publish."""

    book_id: str
    research: Research
    plan: ProductBookPlan
    chapters: list[ProductChapter] = Field(min_length=1)
    answer_keys: list[BlindAnswers] = Field(min_length=1)
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
        answer_chapters = {item.chapter_ref for item in self.answer_keys}
        if answer_chapters != chapter_ids:
            raise ValueError("independent answer keys must cover every chapter exactly once")
        plan_by_id = {item.chapter_id: item for item in self.plan.chapters}
        verification_by_id = {
            item.chapter_ref: item for item in self.exercise_verifications
        }
        answers_by_id = {item.chapter_ref: item for item in self.answer_keys}
        for chapter in self.chapters:
            chapter_plan = plan_by_id[chapter.chapter_id]
            if len(chapter.exercises) != chapter_plan.exercise_count:
                raise ValueError(
                    f"{chapter.chapter_id} exercise count does not match the plan"
                )
            assessed_outcomes = {
                exercise.learning_outcome for exercise in chapter.exercises
            }
            missing_outcomes = set(chapter_plan.learning_outcomes) - assessed_outcomes
            if missing_outcomes:
                raise ValueError(
                    f"{chapter.chapter_id} has unassessed learning outcomes: "
                    + ", ".join(sorted(missing_outcomes))
                )
            if chapter_plan.visual is not None:
                figure_ids = {figure.figure_id for figure in chapter.figures}
                if chapter_plan.visual.visual_id not in figure_ids:
                    raise ValueError(
                        f"{chapter.chapter_id} is missing planned visual "
                        f"{chapter_plan.visual.visual_id}"
                    )
            verification = verification_by_id[chapter.chapter_id]
            exercise_ids = {exercise.exercise_id for exercise in chapter.exercises}
            answer_refs = {
                answer.exercise_ref for answer in answers_by_id[chapter.chapter_id].answers
            }
            if answer_refs != exercise_ids:
                raise ValueError(
                    f"{chapter.chapter_id} independent answers must cover every exercise exactly once"
                )
            verdict_refs = {verdict.exercise_ref for verdict in verification.verdicts}
            if verdict_refs != exercise_ids:
                raise ValueError(
                    f"{chapter.chapter_id} verification must cover every exercise exactly once"
                )
            if any(verdict.decision != "approve" for verdict in verification.verdicts):
                raise ValueError(
                    f"{chapter.chapter_id} contains exercises that are not approved"
                )
        return self


def _normalized_prose(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _is_placeholder_text(value: str) -> bool:
    markers = (
        "learner response required",
        "learner reasoning required",
        "no draft answer",
        "no draft reasoning",
        "answer to be supplied",
        "reasoning to be supplied",
        "todo",
        "tbd",
    )
    return any(marker in value for marker in markers)

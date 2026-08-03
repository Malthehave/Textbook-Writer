"""Manager FunctionTool: assemble stage JSON and compile the Typst PDF."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from agents import FunctionTool, function_tool
from pydantic import BaseModel

from textbook_writer.models.product import (
    BlindAnswers,
    ChapterReview,
    EditorialState,
    ExerciseVerification,
    ProductBook,
    ProductBookPlan,
    ProductChapter,
    Research,
)
from textbook_writer.runtime.pdf import book_output_stem, build_textbook_pdf_file

STAGES_DIRNAME = "production"
BOOK_FILENAME = "book.json"
PUBLICATION_REPORT_FILENAME = "publication-report.json"
CHAPTERS_DIRNAME = "chapters"


def stages_dir(workspace: Path) -> Path:
    path = workspace.resolve() / STAGES_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_model(path: Path, model: BaseModel) -> None:
    write_json(path, model.model_dump(mode="json"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _resolved_production_path(workspace: Path, artifact_path: str) -> tuple[str, Path]:
    relative = PurePosixPath(artifact_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("artifact path must be workspace-relative")
    if not str(relative).startswith("production/"):
        raise ValueError("artifact path must be under production/")
    path = workspace.resolve() / Path(*relative.parts)
    return str(relative), path


def _model_for_artifact_path(artifact_path: str) -> type[BaseModel]:
    relative = PurePosixPath(artifact_path)
    if artifact_path == "production/research.json":
        return Research
    if artifact_path == "production/book-plan.json":
        return ProductBookPlan
    if artifact_path == "production/editorial-state.json":
        return EditorialState
    if relative.name.endswith(".answers.json"):
        return BlindAnswers
    if relative.name.endswith(".review.json"):
        return ChapterReview
    if relative.name.endswith(".verification.json"):
        return ExerciseVerification
    if relative.parent == PurePosixPath("production/chapters"):
        return ProductChapter
    raise ValueError(f"unsupported production artifact: {artifact_path}")


def _schema_type_label(node: object) -> str:
    if not isinstance(node, dict):
        return "any"
    if "$ref" in node:
        return str(node["$ref"]).rsplit("/", 1)[-1]
    if "anyOf" in node:
        return " | ".join(_schema_type_label(option) for option in node["anyOf"])
    if "type" in node:
        type_name = node["type"]
        if type_name == "array":
            return f"array[{_schema_type_label(node.get('items', {}))}]"
        if "pattern" in node:
            return f"{type_name} matching {node['pattern']}"
        return str(type_name)
    return "object"


def artifact_contract_help(artifact_path: str) -> str:
    """Compact required-field contract for specialist repair loops."""

    model = _model_for_artifact_path(artifact_path)
    schema = model.model_json_schema()
    properties = schema.get("properties", {})
    required = schema.get("required", list(properties))
    lines = [f"schema={model.__name__}", "required fields:"]
    for name in required:
        prop = properties.get(name, {})
        line = f"- {name}: {_schema_type_label(prop)}"
        if isinstance(prop, dict) and prop.get("description"):
            line = f"{line} — {prop['description']}"
        lines.append(line)
    if model is Research:
        lines.append(
            "notes: audience/learning_goal are plain strings; no extra keys; "
            "topic source_refs are source_ids (not URLs); ≥2 hosts/topic."
        )
    elif model is ProductChapter:
        lines.append(
            "notes: exercise count and learning_outcomes must match book-plan.json; "
            "planned visual id must appear in figures[] when the plan has a visual."
        )
    elif model is BlindAnswers:
        lines.append(
            "notes: answers[].exercise_ref must cover every exercise in the chapter exactly once."
        )
    elif model is ExerciseVerification:
        lines.append(
            "notes: verdicts[].exercise_ref must cover every exercise in the chapter exactly once."
        )
    return "\n".join(lines)


def _invalid_artifact_message(path: str, error: object) -> str:
    try:
        contract = artifact_contract_help(path)
    except Exception:
        contract = "schema=unknown"
    return f"invalid={path} error={error}\n{contract}"


def commit_production_artifact_tool(book_root: Path) -> FunctionTool:
    """Write + validate a production JSON artifact for specialist self-repair loops."""

    workspace = Path(book_root)

    @function_tool(name_override="commit-production-artifact")
    def commit_production_artifact(path: str, content: str) -> str:
        """Write one canonical production JSON file and validate it immediately.

        Use this for research, book-plan, chapter, review, answers, and verification
        artifacts. `path` is workspace-relative (e.g. production/research.json).
        `content` is the full JSON document as a string.

        Returns `valid=<path> schema=<Name>` on success.
        Returns `invalid=<path> error=<message>` plus the required-field contract on
        failure — fix the JSON and call again until valid. Do not finish until valid.
        """

        try:
            rel, dest = _resolved_production_path(workspace, path)
        except ValueError as exc:
            return _invalid_artifact_message(path, exc)
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            return _invalid_artifact_message(path, f"JSON parse error: {exc}")
        if not isinstance(payload, dict):
            return _invalid_artifact_message(path, "top-level JSON value must be an object")
        write_json(dest, payload)
        try:
            model_name = _validate_production_artifact(workspace, rel)
        except Exception as exc:
            return _invalid_artifact_message(rel, exc)
        return f"valid={rel} schema={model_name}"

    return commit_production_artifact


def describe_production_artifact_tool(book_root: Path) -> FunctionTool:
    """Return the canonical schema contract for a production artifact path."""

    del book_root  # path-only helper; kept for uniform tool wiring

    @function_tool(name_override="describe-production-artifact")
    def describe_production_artifact(path: str) -> str:
        """Return the required JSON contract for a production artifact path.

        Call this before writing if you are unsure of field names/types. Examples:
        production/research.json, production/book-plan.json,
        production/chapters/ch01.json, production/chapters/ch01.review.json,
        production/chapters/ch01.answers.json, production/chapters/ch01.verification.json.
        """

        try:
            return artifact_contract_help(path)
        except Exception as exc:
            return f"unsupported={path} error={exc}"

    return describe_production_artifact


def production_artifact_tools(book_root: Path) -> list[FunctionTool]:
    """Describe + commit + validate tools so specialists can self-repair before returning."""

    return [
        describe_production_artifact_tool(book_root),
        commit_production_artifact_tool(book_root),
        validate_production_artifact_tool(book_root),
    ]


def _assemble_book(workspace: Path) -> ProductBook:
    stages = stages_dir(workspace)
    research = Research.model_validate_json(
        (stages / "research.json").read_text(encoding="utf-8")
    )
    plan = ProductBookPlan.model_validate_json(
        (stages / "book-plan.json").read_text(encoding="utf-8")
    )
    chapter_dir = stages / CHAPTERS_DIRNAME
    if not chapter_dir.is_dir():
        raise FileNotFoundError("missing production/chapters/")
    chapters: list[ProductChapter] = []
    verifications: list[ExerciseVerification] = []
    for chapter_meta in plan.chapters:
        chapter_path = chapter_dir / f"{chapter_meta.chapter_id}.json"
        chapter = ProductChapter.model_validate_json(
            chapter_path.read_text(encoding="utf-8")
        )
        chapters.append(chapter)
        review_path = chapter_dir / f"{chapter_meta.chapter_id}.review.json"
        review = ChapterReview.model_validate_json(review_path.read_text(encoding="utf-8"))
        if review.chapter_ref != chapter_meta.chapter_id or review.decision != "approve":
            raise RuntimeError(
                f"{chapter_meta.chapter_id} needs an approved editorial review before publish"
            )
        _validate_figure_assets(workspace, chapter)
        verification_path = chapter_dir / f"{chapter_meta.chapter_id}.verification.json"
        if verification_path.is_file():
            verifications.append(
                ExerciseVerification.model_validate_json(
                    verification_path.read_text(encoding="utf-8")
                )
            )
    if len(verifications) != len(chapters):
        raise RuntimeError("every chapter needs a .verification.json before publish")
    editorial_state = EditorialState.model_validate_json(
        (stages / "editorial-state.json").read_text(encoding="utf-8")
    )
    accepted = set(editorial_state.accepted_chapter_refs)
    planned = {chapter.chapter_id for chapter in plan.chapters}
    if accepted != planned:
        raise RuntimeError("editorial state must accept every planned chapter before publish")
    book = ProductBook(
        book_id=workspace.name,
        research=research,
        plan=plan,
        chapters=chapters,
        exercise_verifications=verifications,
    )
    write_model(stages / BOOK_FILENAME, book)
    return book


def _validate_figure_assets(workspace: Path, chapter: ProductChapter) -> None:
    for figure in chapter.figures:
        path = workspace / figure.asset_path
        if path.suffix.lower() != ".png":
            raise RuntimeError(f"{figure.figure_id} asset must be a PNG")
        if not path.is_file():
            raise FileNotFoundError(f"figure asset missing at {path}")


def _validate_chapter_contract(workspace: Path, chapter: ProductChapter) -> None:
    production = stages_dir(workspace)
    research = Research.model_validate_json(
        (production / "research.json").read_text(encoding="utf-8")
    )
    plan = ProductBookPlan.model_validate_json(
        (production / "book-plan.json").read_text(encoding="utf-8")
    )
    planned = next(
        (item for item in plan.chapters if item.chapter_id == chapter.chapter_id), None
    )
    if planned is None:
        raise ValueError(f"{chapter.chapter_id} is not present in the approved plan")
    if chapter.learning_outcomes != planned.learning_outcomes:
        raise ValueError(f"{chapter.chapter_id} learning outcomes must match the plan exactly")
    if len(chapter.exercises) != planned.exercise_count:
        raise ValueError(f"{chapter.chapter_id} exercise count must match the plan")
    allowed_topics = set(planned.topic_refs + planned.supporting_topic_refs)
    used_topics = {topic for section in chapter.sections for topic in section.topic_refs}
    if not set(planned.topic_refs) <= used_topics or not used_topics <= allowed_topics:
        raise ValueError(f"{chapter.chapter_id} section topic refs do not match the plan")
    source_ids = {source.source_id for source in research.sources}
    used_sources = {
        source
        for section in chapter.sections
        for source in section.source_refs
    } | {
        source
        for exercise in chapter.exercises
        for source in exercise.source_refs
    }
    if not used_sources <= source_ids:
        missing = ", ".join(sorted(used_sources - source_ids))
        raise ValueError(f"{chapter.chapter_id} has unknown source refs: {missing}")
    if planned.visual is not None:
        figure_ids = {figure.figure_id for figure in chapter.figures}
        if planned.visual.visual_id not in figure_ids:
            raise ValueError(
                f"{chapter.chapter_id} is missing planned visual {planned.visual.visual_id}"
            )


def _validate_production_artifact(workspace: Path, artifact_path: str) -> str:
    relative = PurePosixPath(artifact_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("artifact path must be workspace-relative")
    path = workspace.resolve() / Path(*relative.parts)
    if not path.is_file():
        raise FileNotFoundError(f"artifact missing at {artifact_path}")

    model = _model_for_artifact_path(artifact_path)
    validated = model.model_validate_json(path.read_text(encoding="utf-8"))
    if isinstance(validated, ProductChapter):
        _validate_figure_assets(workspace, validated)
        _validate_chapter_contract(workspace, validated)
    elif isinstance(validated, BlindAnswers):
        chapter_path = path.with_name(f"{validated.chapter_ref}.json")
        chapter = ProductChapter.model_validate_json(
            chapter_path.read_text(encoding="utf-8")
        )
        expected = {exercise.exercise_id for exercise in chapter.exercises}
        actual = {answer.exercise_ref for answer in validated.answers}
        if actual != expected:
            raise ValueError(
                f"{validated.chapter_ref} blind answers must cover every exercise exactly once"
            )
    elif isinstance(validated, ChapterReview):
        expected_ref = path.name.removesuffix(".review.json")
        if validated.chapter_ref != expected_ref:
            raise ValueError("chapter review ref must match its filename")
    elif isinstance(validated, ExerciseVerification):
        expected_ref = path.name.removesuffix(".verification.json")
        if validated.chapter_ref != expected_ref:
            raise ValueError("exercise verification ref must match its filename")
        chapter_path = path.with_name(f"{validated.chapter_ref}.json")
        chapter = ProductChapter.model_validate_json(
            chapter_path.read_text(encoding="utf-8")
        )
        expected = {exercise.exercise_id for exercise in chapter.exercises}
        actual = {verdict.exercise_ref for verdict in validated.verdicts}
        if actual != expected:
            raise ValueError(
                f"{validated.chapter_ref} verification must cover every exercise exactly once"
            )
    return model.__name__


def validate_production_artifact_tool(book_root: Path) -> FunctionTool:
    workspace = Path(book_root)

    @function_tool(name_override="validate-production-artifact")
    def validate_production_artifact(path: str) -> str:
        """Validate one production JSON artifact already on disk.

        Returns `valid=<path> schema=<Name>` or `invalid=<path> error=<message>`.
        Specialists must fix invalid artifacts themselves (usually via
        `commit-production-artifact`) before finishing. Managers use this as a gate after
        a specialist returns.
        """

        try:
            rel, _dest = _resolved_production_path(workspace, path)
            model_name = _validate_production_artifact(workspace, rel)
        except Exception as exc:
            return _invalid_artifact_message(path, exc)
        return f"valid={rel} schema={model_name}"

    return validate_production_artifact


def build_textbook_pdf_tool(book_root: Path) -> FunctionTool:
    workspace = Path(book_root)

    @function_tool(name_override="build-textbook-pdf")
    def build_textbook_pdf() -> str:
        """Assemble production/*.json into book.json and compile the Typst PDF under build/.

        Call only after every planned chapter has an approved editorial review, an
        all-approve exercise verification, and is accepted in editorial-state.json.
        Returns measured paths and page counts — never invent those yourself.
        """

        book = _assemble_book(workspace)
        pdf_path = workspace / "build" / f"{book_output_stem(book.plan.title)}.pdf"
        report = build_textbook_pdf_file(
            book_path=stages_dir(workspace) / BOOK_FILENAME,
            output_path=pdf_path,
        )
        write_json(stages_dir(workspace) / PUBLICATION_REPORT_FILENAME, report)
        fit = "within-tolerance" if report["within_tolerance"] else "outside-tolerance"
        return (
            f"title={report['title']} pdf={report['pdf_path']} "
            f"pages={report['actual_pages']} target={report['target_pages']} "
            f"allowed={report['minimum_pages']}-{report['maximum_pages']} status={fit} "
            f"report=production/{PUBLICATION_REPORT_FILENAME}"
        )

    return build_textbook_pdf

"""Manager FunctionTool: assemble stage JSON and compile the Typst PDF."""

from __future__ import annotations

import json
from pathlib import Path

from agents import FunctionTool, function_tool
from pydantic import BaseModel

from textbook_writer.models.product import (
    ExerciseVerification,
    ProductBook,
    ProductBookPlan,
    ProductChapter,
    Research,
)
from textbook_writer.runtime.pdf import book_output_stem, build_textbook_pdf_file

STAGES_DIRNAME = "production"
BOOK_FILENAME = "book.json"
CHAPTERS_DIRNAME = "chapters"


def stages_dir(workspace: Path) -> Path:
    path = workspace.resolve() / STAGES_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


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
        chapters.append(
            ProductChapter.model_validate_json(chapter_path.read_text(encoding="utf-8"))
        )
        verification_path = chapter_dir / f"{chapter_meta.chapter_id}.verification.json"
        if verification_path.is_file():
            verifications.append(
                ExerciseVerification.model_validate_json(
                    verification_path.read_text(encoding="utf-8")
                )
            )
    if len(verifications) != len(chapters):
        raise RuntimeError("every chapter needs a .verification.json before publish")
    book = ProductBook(
        book_id=workspace.name,
        research=research,
        plan=plan,
        chapters=chapters,
        exercise_verifications=verifications,
    )
    write_model(stages / BOOK_FILENAME, book)
    return book


def build_textbook_pdf_tool(book_root: Path) -> FunctionTool:
    workspace = Path(book_root)

    @function_tool(name_override="build-textbook-pdf")
    def build_textbook_pdf() -> str:
        """Assemble production/*.json into book.json and compile the Typst PDF under build/.

        Call only after every planned chapter has an all-approve .verification.json.
        Returns measured paths and page counts — never invent those yourself.
        """

        book = _assemble_book(workspace)
        pdf_path = workspace / "build" / f"{book_output_stem(book.plan.title)}.pdf"
        report = build_textbook_pdf_file(
            book_path=stages_dir(workspace) / BOOK_FILENAME,
            output_path=pdf_path,
        )
        return (
            f"title={report['title']} pdf={report['pdf_path']} "
            f"pages={report['actual_pages']} (plan target {report['target_pages']})"
        )

    return build_textbook_pdf

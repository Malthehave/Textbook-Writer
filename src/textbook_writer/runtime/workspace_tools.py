"""Deterministic workspace tools for the manager-led textbook agent.

Specialists are agents-as-tools. These helpers freeze sources, bind citations,
assemble the book, and publish the PDF. They never invent measurements or sources.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agents import function_tool
from pydantic import BaseModel

from textbook_writer.models.product import (
    ContentEvidenceCitation,
    ContinuityAudit,
    ExerciseVerification,
    FrozenEvidenceChunk,
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
    SourceEvidencePacket,
)
from textbook_writer.publishing.product import (
    book_output_stem,
    build_product_book,
)
from textbook_writer.research import (
    SourceProvider,
    acquire_source_manifest,
    build_source_packets,
    prepare_product_acquisition_manifest,
    sync_dossier_to_acquired_sources,
)
from textbook_writer.runtime.discovery_chat import (
    default_page_tolerance,
    load_production_brief,
)
from textbook_writer.runtime.quality import (
    ensure_chapter_bridges,
    ensure_plan_visuals,
    validate_chapter_content,
)
from textbook_writer.runtime.workspace import rename_workspace_to_title


STAGES_DIRNAME = "production"
BOOK_FILENAME = "book.json"

CITATION_STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "before",
    "being",
    "between",
    "chapter",
    "could",
    "every",
    "first",
    "from",
    "have",
    "into",
    "must",
    "other",
    "should",
    "their",
    "these",
    "they",
    "this",
    "through",
    "using",
    "when",
}


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


def acquire_and_freeze_sources(
    *,
    dossier: ResearchDossier,
    stages: Path,
    source_provider: SourceProvider | None = None,
) -> tuple[ResearchDossier, AcquisitionBatch, list[SourceEvidencePacket]]:
    """Acquire approved URLs and create page-aware, hash-checked source packets."""

    stages.mkdir(parents=True, exist_ok=True)
    manifest_path = stages / "source-acquisition-manifest.json"
    archive_path = stages / "source-archive.json"
    acquired_dossier_path = stages / "research-dossier-acquired.json"
    failures_path = stages / "source-acquisition-failures.json"
    packet_dir = stages / "source-packets"
    if not manifest_path.exists():
        prepare_product_acquisition_manifest(dossier, manifest_path)
    if archive_path.exists():
        archive = AcquisitionBatch.model_validate_json(
            archive_path.read_text(encoding="utf-8")
        )
    else:
        archive = acquire_source_manifest(
            manifest_path,
            stages / "source-snapshots",
            archive_path,
            provider=source_provider,
        )
    failures: list[AcquisitionFailure] = []
    if failures_path.exists():
        failures = [
            AcquisitionFailure.model_validate(item)
            for item in json.loads(failures_path.read_text(encoding="utf-8"))
        ]
    if acquired_dossier_path.exists():
        acquired_dossier = ResearchDossier.model_validate_json(
            acquired_dossier_path.read_text(encoding="utf-8")
        )
    else:
        acquired_dossier = sync_dossier_to_acquired_sources(
            dossier,
            acquired_source_ids={item.source_id for item in archive.acquisitions},
            failures=failures,
        )
        write_model(acquired_dossier_path, acquired_dossier)

    expected = {item.source_id for item in acquired_dossier.sources}
    actual = {item.source_id for item in archive.acquisitions}
    if expected - actual:
        raise RuntimeError(
            "frozen source archive is missing sources retained after acquisition sync: "
            f"{sorted(expected - actual)}"
        )
    if actual != expected:
        archive = archive.model_copy(
            update={
                "acquisitions": [
                    item for item in archive.acquisitions if item.source_id in expected
                ],
                "source_fixtures": [
                    item
                    for item in archive.source_fixtures
                    if item.source.source_id in expected
                ],
            }
        )
        write_model(archive_path, archive)

    question_refs_by_source = {
        source_id: [
            topic.topic_id
            for topic in acquired_dossier.topics
            if source_id in {*topic.source_refs, *topic.practice_source_refs}
        ]
        for source_id in expected
    }
    packets = build_source_packets(
        archive_path,
        packet_dir,
        question_refs_by_source=question_refs_by_source,
    )
    packet_sources = {packet.source.source_id for packet in packets}
    if packet_sources != expected:
        raise RuntimeError("source packets do not cover every acquired dossier source")
    return acquired_dossier, archive, packets


def build_frozen_citation_ledger(
    *,
    dossier: ResearchDossier,
    chapters: list[ProductChapter],
    packets: list[SourceEvidencePacket],
) -> tuple[list[FrozenEvidenceChunk], list[ContentEvidenceCitation]]:
    """Bind every cited teaching artifact to a reproducible frozen chunk."""

    chunks_by_source: dict[str, list[tuple[str, Any]]] = {}
    evidence_index: list[FrozenEvidenceChunk] = []
    seen_chunks: set[str] = set()
    for packet in sorted(packets, key=lambda item: item.packet_id):
        for chunk in sorted(packet.chunks, key=lambda item: item.chunk_id):
            if chunk.chunk_id in seen_chunks:
                raise RuntimeError(f"duplicate frozen evidence chunk {chunk.chunk_id}")
            seen_chunks.add(chunk.chunk_id)
            chunks_by_source.setdefault(chunk.source_ref, []).append(
                (packet.packet_id, chunk)
            )
            evidence_index.append(
                FrozenEvidenceChunk(
                    packet_ref=packet.packet_id,
                    chunk_ref=chunk.chunk_id,
                    source_ref=chunk.source_ref,
                    page=chunk.page,
                    content_hash=chunk.content_hash,
                )
            )

    cited_content: list[tuple[str, str, list[str]]] = []
    cited_content.extend(
        (claim.claim_id, claim.statement, claim.source_refs)
        for topic in dossier.topics
        for claim in topic.claims
    )
    cited_content.extend(
        (section.section_id, section.markdown, section.source_refs)
        for chapter in chapters
        for section in chapter.sections
    )
    cited_content.extend(
        (
            exercise.exercise_id,
            f"{exercise.prompt} {exercise.answer} {exercise.reasoning}",
            exercise.source_refs,
        )
        for chapter in chapters
        for exercise in chapter.exercises
    )

    citations: list[ContentEvidenceCitation] = []
    for content_ref, content, source_refs in cited_content:
        for source_ref in dict.fromkeys(source_refs):
            candidates = chunks_by_source.get(source_ref, [])
            if not candidates:
                raise RuntimeError(
                    f"{content_ref} cites {source_ref}, but no frozen evidence exists"
                )
            scored = [
                (_citation_lexical_score(content, chunk.text), packet_id, chunk)
                for packet_id, chunk in candidates
            ]
            _score, _packet_id, selected = max(
                scored, key=lambda item: (item[0], len(item[2].text), item[2].chunk_id)
            )
            citations.append(
                ContentEvidenceCitation(
                    content_ref=content_ref,
                    source_ref=source_ref,
                    chunk_ref=selected.chunk_id,
                    lexical_score=round(_score, 6),
                )
            )
    return evidence_index, citations


def _citation_lexical_score(content: str, evidence: str) -> float:
    content_terms = _citation_terms(content)
    evidence_terms = _citation_terms(evidence)
    if not content_terms or not evidence_terms:
        return 0.0
    return len(content_terms & evidence_terms) / len(content_terms)


def _citation_terms(value: str) -> set[str]:
    return {
        term.casefold()
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", value)
        if term.casefold() not in CITATION_STOPWORDS
    }


def load_source_packets(stages: Path) -> list[SourceEvidencePacket]:
    packet_dir = stages / "source-packets"
    if not packet_dir.is_dir():
        raise FileNotFoundError("source packets missing; call acquire_and_freeze first")
    packets: list[SourceEvidencePacket] = []
    for path in sorted(packet_dir.glob("packet-*.json")):
        packets.append(
            SourceEvidencePacket.model_validate_json(path.read_text(encoding="utf-8"))
        )
    if not packets:
        raise FileNotFoundError("source packets directory is empty")
    return packets


def assemble_product_book(
    *,
    workspace: Path,
    book_id: str,
) -> ProductBook:
    """Assemble production/book.json from stage artifacts and bind citations."""

    stages = stages_dir(workspace)
    dossier_path = stages / "research-dossier-acquired.json"
    if not dossier_path.is_file():
        dossier_path = stages / "research-dossier.json"
    dossier = ResearchDossier.model_validate_json(dossier_path.read_text(encoding="utf-8"))
    plan_path = stages / "book-plan-final.json"
    if not plan_path.is_file():
        plan_path = stages / "book-plan.json"
    plan = ensure_plan_visuals(
        ProductBookPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    )
    research_audit = ResearchAudit.model_validate_json(
        (stages / "research-audit.json").read_text(encoding="utf-8")
        if (stages / "research-audit.json").is_file()
        else (stages / "research-audit-final.json").read_text(encoding="utf-8")
    )
    plan_audit_path = stages / "plan-audit-final.json"
    if not plan_audit_path.is_file():
        plan_audit_path = stages / "plan-audit.json"
    plan_audit = PlanAudit.model_validate_json(
        plan_audit_path.read_text(encoding="utf-8")
    )
    chapter_dirs = sorted(stages.glob("chapters-v*"), key=lambda p: p.name)
    if not chapter_dirs:
        raise FileNotFoundError("no chapters-v* directory under production/")
    chapter_dir = chapter_dirs[-1]
    chapters: list[ProductChapter] = []
    verifications: list[ExerciseVerification] = []
    for index, chapter_meta in enumerate(plan.chapters):
        chapter_path = chapter_dir / f"{chapter_meta.chapter_id}.json"
        chapter = ProductChapter.model_validate_json(
            chapter_path.read_text(encoding="utf-8")
        )
        validate_chapter_content(
            chapter_meta, dossier, chapter, chapter_index=index
        )
        chapters.append(chapter)
        verification_path = chapter_dir / f"{chapter_meta.chapter_id}.verification.json"
        if verification_path.is_file():
            verifications.append(
                ExerciseVerification.model_validate_json(
                    verification_path.read_text(encoding="utf-8")
                )
            )
    if len(verifications) != len(chapters):
        raise RuntimeError(
            "every chapter needs a .verification.json before assemble_book"
        )
    chapters = ensure_chapter_bridges(plan, chapters)
    archive = AcquisitionBatch.model_validate_json(
        (stages / "source-archive.json").read_text(encoding="utf-8")
    )
    packets = load_source_packets(stages)
    evidence_index, citation_ledger = build_frozen_citation_ledger(
        dossier=dossier,
        chapters=chapters,
        packets=packets,
    )
    continuity_path = stages / "continuity-audit.json"
    if continuity_path.is_file():
        continuity = ContinuityAudit.model_validate_json(
            continuity_path.read_text(encoding="utf-8")
        )
    else:
        continuity = ContinuityAudit(
            chapter_refs=[chapter.chapter_id for chapter in chapters],
            decision="approve",
        )
    book = ProductBook(
        book_id=book_id,
        dossier=dossier,
        research_audit=research_audit,
        plan=plan,
        plan_audit=plan_audit,
        chapters=chapters,
        exercise_verifications=verifications,
        continuity_audit=continuity,
        source_archive=archive,
        evidence_index=evidence_index,
        citation_ledger=citation_ledger,
    )
    write_model(stages / BOOK_FILENAME, book)
    return book


def publish_product_book(
    *,
    workspace: Path,
    page_tolerance: int,
) -> dict[str, Any]:
    """Compile production/book.json to build/<title-slug>.pdf and return measured report."""

    stages = stages_dir(workspace)
    book_path = stages / BOOK_FILENAME
    if not book_path.is_file():
        raise FileNotFoundError("production/book.json missing; call assemble_book first")
    book = ProductBook.model_validate_json(book_path.read_text(encoding="utf-8"))
    workspace = rename_workspace_to_title(workspace.resolve(), book.plan.title)
    stages = stages_dir(workspace)
    book_path = stages / BOOK_FILENAME
    pdf_path = workspace / "build" / f"{book_output_stem(book.plan.title)}.pdf"
    report = build_product_book(
        book_path=book_path,
        output_path=pdf_path,
        page_tolerance=page_tolerance,
    )
    return {
        "workspace": str(workspace),
        "pdf_path": str(pdf_path),
        "report_path": str(pdf_path.with_suffix(".build.json")),
        "actual_pages": report.actual_pages,
        "target_pages": report.target_pages,
        "within_page_tolerance": report.within_page_tolerance,
        "source_count": report.source_count,
        "exercise_count": report.exercise_count,
        "verified_exercise_count": report.verified_exercise_count,
        "figure_count": report.figure_count,
        "citation_count": report.citation_count,
    }


def build_manager_workspace_tools(
    *,
    workspace: Path,
    book_id: str,
    source_provider: SourceProvider | None = None,
) -> list[Any]:
    """Function tools closed over one book workspace for the main manager agent."""

    workspace = workspace.resolve()
    stages = stages_dir(workspace)

    @function_tool
    def list_stage_artifacts() -> str:
        """List JSON artifacts currently under production/."""

        if not stages.is_dir():
            return "[]"
        names = sorted(
            path.name for path in stages.rglob("*.json") if path.is_file()
        )
        return json.dumps(names)

    @function_tool
    def load_stage_artifact(relative_path: str) -> str:
        """Load a JSON file relative to production/ (e.g. research-dossier.json)."""

        path = (stages / relative_path).resolve()
        if not path.is_relative_to(stages.resolve()):
            raise ValueError("artifact path escapes production/")
        if not path.is_file():
            raise FileNotFoundError(f"missing artifact: {relative_path}")
        text = path.read_text(encoding="utf-8")
        if len(text) > 120_000:
            return text[:120_000] + "\n…[truncated]"
        return text

    @function_tool
    def save_stage_artifact(relative_path: str, json_payload: str) -> str:
        """Manually save JSON under production/. Specialist tools auto-save—use this only
        to merge diagram HTML into chapters-v1/<chapter_id>.json.
        """

        path = (stages / relative_path).resolve()
        if not path.is_relative_to(stages.resolve()):
            raise ValueError("artifact path escapes production/")
        if path.suffix != ".json":
            raise ValueError("stage artifacts must be .json")
        payload = json.loads(json_payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return f"Saved {relative_path} ({path.stat().st_size} bytes)."

    @function_tool
    def acquire_and_freeze() -> str:
        """Download and freeze every URL in the saved research dossier; build source packets.

        Prefers production/research-dossier.json (or research-dossier-acquired.json on resume).
        """

        dossier_path = stages / "research-dossier.json"
        if not dossier_path.is_file():
            raise FileNotFoundError(
                "save research-dossier.json before acquire_and_freeze"
            )
        dossier = ResearchDossier.model_validate_json(
            dossier_path.read_text(encoding="utf-8")
        )
        acquired, archive, packets = acquire_and_freeze_sources(
            dossier=dossier,
            stages=stages,
            source_provider=source_provider,
        )
        write_model(stages / "research-dossier.json", acquired)
        return json.dumps(
            {
                "acquired_sources": len(archive.acquisitions),
                "topics": len(acquired.topics),
                "packets": len(packets),
                "dossier_path": "research-dossier-acquired.json",
            },
            indent=2,
        )

    @function_tool
    def assemble_book() -> str:
        """Bind frozen citations and write production/book.json from stage artifacts."""

        book = assemble_product_book(workspace=workspace, book_id=book_id)
        return json.dumps(
            {
                "book_id": book.book_id,
                "title": book.plan.title,
                "chapters": len(book.chapters),
                "citations": len(book.citation_ledger),
                "evidence_chunks": len(book.evidence_index),
                "path": f"{STAGES_DIRNAME}/{BOOK_FILENAME}",
            },
            indent=2,
        )

    @function_tool
    def publish_book(page_tolerance: int | None = None) -> str:
        """Compile production/book.json to a measured PDF named from the book title.

        Returns actual page counts from the publication report only—never invent them.
        """

        brief = load_production_brief(workspace)
        tolerance = page_tolerance
        if tolerance is None:
            if brief is not None and brief.page_tolerance is not None:
                tolerance = brief.page_tolerance
            elif brief is not None:
                tolerance = default_page_tolerance(brief.target_pages)
            else:
                book = ProductBook.model_validate_json(
                    (stages / BOOK_FILENAME).read_text(encoding="utf-8")
                )
                tolerance = default_page_tolerance(book.plan.target_pages)
        report = publish_product_book(workspace=workspace, page_tolerance=tolerance)
        return json.dumps(report, indent=2)

    return [
        list_stage_artifacts,
        load_stage_artifact,
        save_stage_artifact,
        acquire_and_freeze,
        assemble_book,
        publish_book,
    ]

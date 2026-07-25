"""Create bounded, source-only evidence packets from frozen acquisitions."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from textbook_writer.models.research import (
    AcquisitionBatch,
    SourceEvidencePacket,
    SourceTextChunk,
)
from textbook_writer.research.extract import extract_document, normalize_text

MAX_CHUNK_CHARS = 10_000


def build_source_packets(
    batch_path: Path,
    output_dir: Path,
    *,
    question_refs_by_source: dict[str, list[str]],
) -> list[SourceEvidencePacket]:
    batch = AcquisitionBatch.model_validate_json(batch_path.read_text(encoding="utf-8"))
    batch_root = batch_path.resolve().parent
    output_dir.mkdir(parents=True, exist_ok=True)
    packets: list[SourceEvidencePacket] = []
    acquisitions = {item.source_id: item for item in batch.acquisitions}
    for fixture in batch.source_fixtures:
        source_id = fixture.source.source_id
        questions = question_refs_by_source.get(source_id, [])
        if not questions:
            raise ValueError(f"source {source_id} has no assigned research questions")
        acquisition = acquisitions[source_id]
        snapshot = (batch_root / fixture.snapshot_path).resolve()
        if not snapshot.is_relative_to(batch_root):
            raise ValueError(f"source snapshot escapes acquisition directory: {fixture.snapshot_path}")
        raw = snapshot.read_bytes()
        actual_hash = f"sha256:{sha256(raw).hexdigest()}"
        if actual_hash != acquisition.content_hash:
            raise ValueError(f"source snapshot hash mismatch: {source_id}")
        document = extract_document(raw, fixture.media_type)
        page_texts = list(enumerate(document.pages, start=1)) if document.pages else [(None, document.text)]
        chunks: list[SourceTextChunk] = []
        chunk_number = 0
        for page, text in page_texts:
            for segment in _split_text(text):
                chunk_number += 1
                digest = sha256(segment.encode()).hexdigest()
                chunks.append(
                    SourceTextChunk(
                        chunk_id=f"chunk-{source_id}-{chunk_number:04d}",
                        source_ref=source_id,
                        page=page,
                        text=segment,
                        content_hash=f"sha256:{digest}",
                    )
                )
        for index, chunk in enumerate(chunks, start=1):
            packet = SourceEvidencePacket(
                packet_id=f"packet-{source_id}-{index:04d}",
                acquisition_ref=acquisition.acquisition_id,
                source=fixture.source,
                question_refs=questions,
                chunks=[chunk],
            )
            (output_dir / f"{packet.packet_id}.json").write_text(
                json.dumps(packet.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            packets.append(packet)
    return packets


def _split_text(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    chunks: list[str] = []
    cursor = 0
    while cursor < len(normalized):
        end = min(cursor + MAX_CHUNK_CHARS, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", cursor, end)
            if boundary > cursor:
                end = boundary
        chunks.append(normalized[cursor:end].strip())
        cursor = end
        while cursor < len(normalized) and normalized[cursor].isspace():
            cursor += 1
    return chunks

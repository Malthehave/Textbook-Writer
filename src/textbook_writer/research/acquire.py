"""Acquire live sources into immutable, reviewable local snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import urllib.error

from textbook_writer.models.research import (
    AcquisitionBatch,
    AcquisitionFailure,
    AcquisitionManifest,
    AcquisitionRecord,
    SourceFixture,
)
from textbook_writer.research.extract import EXTRACTOR_VERSION, extract_document
from textbook_writer.research.providers import HttpSourceProvider, SourceProvider


_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/xhtml+xml": ".xhtml",
    "text/html": ".html",
    "text/plain": ".txt",
}


def acquire_source_manifest(
    manifest_path: Path,
    snapshot_dir: Path,
    result_path: Path,
    *,
    provider: SourceProvider | None = None,
) -> AcquisitionBatch:
    """Download approved URLs into frozen snapshots.

    Individual source failures are quarantined. A dead link, unsupported media type,
    or unreadable payload does not abort the batch; failures are recorded beside the
    successful archive so the dossier can shrink to what actually froze.
    """

    manifest = AcquisitionManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    result_parent = result_path.resolve().parent
    snapshots = snapshot_dir.resolve()
    if not snapshots.is_relative_to(result_parent):
        raise ValueError("snapshot directory must be inside the acquisition result directory")
    snapshots.mkdir(parents=True, exist_ok=True)
    result_parent.mkdir(parents=True, exist_ok=True)

    source_provider = provider or HttpSourceProvider(
        allowed_hosts=manifest.allowed_hosts,
        max_bytes=max(item.max_bytes for item in manifest.sources),
    )
    records: list[AcquisitionRecord] = []
    fixtures: list[SourceFixture] = []
    failures: list[AcquisitionFailure] = []
    retrieved_at = datetime.now(timezone.utc)

    for request in manifest.sources:
        url = str(request.source.url)
        try:
            fetched = source_provider.fetch(url)
            if fetched.media_type not in request.accepted_media_types:
                raise ValueError(
                    f"returned disallowed media type {fetched.media_type}"
                )
            if len(fetched.content) > request.max_bytes:
                raise ValueError(f"exceeds its {request.max_bytes}-byte limit")
            # Extraction is a gate: unreadable PDFs or unsupported payloads are not frozen.
            extract_document(fetched.content, fetched.media_type)
            digest = sha256(fetched.content).hexdigest()
            extension = _EXTENSIONS[fetched.media_type]
            target = snapshots / f"{request.source.source_id}-{digest[:16]}{extension}"
            temporary = target.with_suffix(target.suffix + ".part")
            temporary.write_bytes(fetched.content)
            temporary.replace(target)
            relative_path = target.relative_to(result_parent).as_posix()
            source = request.source.model_copy(update={"accessed_at": retrieved_at.date()})
            fixtures.append(
                SourceFixture(
                    source=source,
                    snapshot_path=relative_path,
                    media_type=fetched.media_type,
                )
            )
            records.append(
                AcquisitionRecord(
                    acquisition_id=f"acquisition-{request.source.source_id}",
                    source_id=request.source.source_id,
                    requested_url=fetched.requested_url,
                    resolved_url=fetched.resolved_url,
                    retrieved_at=retrieved_at,
                    media_type=fetched.media_type,
                    content_hash=f"sha256:{digest}",
                    byte_length=len(fetched.content),
                    extractor_version=EXTRACTOR_VERSION,
                    snapshot_path=relative_path,
                )
            )
        except Exception as exc:
            failures.append(
                AcquisitionFailure(
                    source_id=request.source.source_id,
                    requested_url=url,
                    error=_acquisition_error_message(exc),
                )
            )

    failures_path = result_path.with_name("source-acquisition-failures.json")
    failures_path.write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in failures],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if not records:
        detail = "; ".join(
            f"{item.source_id}: {item.error}" for item in failures[:5]
        )
        raise RuntimeError(
            "source acquisition failed for every approved URL"
            + (f" ({detail})" if detail else "")
        )

    batch = AcquisitionBatch(
        acquisition_batch_id=f"batch-{manifest.acquisition_manifest_id}",
        manifest_ref=manifest.acquisition_manifest_id,
        acquired_by_run=manifest.acquired_by_run,
        acquisitions=records,
        source_fixtures=fixtures,
    )
    result_path.write_text(
        json.dumps(batch.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return batch


def _acquisition_error_message(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"
    if isinstance(exc, urllib.error.URLError):
        return f"URL error: {exc.reason}"
    return str(exc)

from __future__ import annotations

from email.message import Message
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlsplit
import urllib.error

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from textbook_writer.models import AcquisitionBatch, AcquisitionManifest
from textbook_writer.models.product import (
    GroundedClaim,
    ProductSource,
    ResearchDossier,
    ResearchedTopic,
)
from textbook_writer.models.research import AcquisitionFailure
from textbook_writer.research import (
    FetchedSource,
    HttpSourceProvider,
    acquire_source_manifest,
    sync_dossier_to_acquired_sources,
)
from textbook_writer.research.extract import extract_document, normalize_pdf_text


ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "valid" / "live-acquisition-manifest.json"


class _FakeResponse:
    def __init__(self, url: str, content: bytes, media_type: str) -> None:
        self._url = url
        self._content = content
        self.headers = Message()
        self.headers["Content-Type"] = media_type
        self.headers["Content-Length"] = str(len(content))

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def geturl(self) -> str:
        return self._url

    def read(self, limit: int) -> bytes:
        return self._content[:limit]


class _FakeOpener:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response

    def open(self, request: object, timeout: float) -> _FakeResponse:
        return self.response


class _StaticProvider:
    def __init__(self, content: bytes, media_type: str = "text/html") -> None:
        self.content = content
        self.media_type = media_type

    def fetch(self, url: str) -> FetchedSource:
        return FetchedSource(
            requested_url=url,
            resolved_url=url,
            media_type=self.media_type,
            content=self.content,
        )


def _public_resolver(host: str) -> list[str]:
    return ["93.184.216.34"]


def _one_page_pdf(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    page[NameObject("/Resources")] = resources
    stream = DecodedStreamObject()
    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({safe_text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_live_acquisition_manifest_is_valid() -> None:
    manifest = AcquisitionManifest.model_validate_json(MANIFEST.read_text())

    assert len(manifest.sources) == 2
    assert "arxiv.org" in manifest.allowed_hosts


def test_http_provider_rejects_non_https_and_unlisted_hosts() -> None:
    provider = HttpSourceProvider(
        allowed_hosts=["example.com"],
        opener=_FakeOpener(_FakeResponse("https://example.com/a", b"hello", "text/plain")),
        resolver=_public_resolver,
    )

    with pytest.raises(ValueError, match="must use HTTPS"):
        provider.fetch("http://example.com/a")
    with pytest.raises(ValueError, match="not allowlisted"):
        provider.fetch("https://other.example/a")


def test_http_provider_rejects_private_resolution() -> None:
    provider = HttpSourceProvider(
        allowed_hosts=["example.com"],
        opener=_FakeOpener(_FakeResponse("https://example.com/a", b"hello", "text/plain")),
        resolver=lambda host: ["127.0.0.1"],
    )

    with pytest.raises(ValueError, match="non-public address"):
        provider.fetch("https://example.com/a")


def test_http_provider_allows_cdn_redirect_hosts_after_allowlisted_request() -> None:
    response = _FakeResponse(
        "https://static.googleusercontent.com/media/sre.google/en//static/pdf/example.pdf",
        b"%PDF-1.4 fake",
        "application/pdf",
    )
    provider = HttpSourceProvider(
        allowed_hosts=["sre.google"],
        opener=_FakeOpener(response),
        resolver=_public_resolver,
    )

    fetched = provider.fetch("https://sre.google/static/pdf/example.pdf")
    assert fetched.requested_url == "https://sre.google/static/pdf/example.pdf"
    assert "static.googleusercontent.com" in fetched.resolved_url


def test_http_provider_enforces_bounded_payload() -> None:
    response = _FakeResponse("https://example.com/a", b"123456", "text/plain")
    provider = HttpSourceProvider(
        allowed_hosts=["example.com"],
        max_bytes=5,
        opener=_FakeOpener(response),
        resolver=_public_resolver,
    )

    with pytest.raises(ValueError, match="exceeding limit"):
        provider.fetch("https://example.com/a")


def test_pdf_extraction_is_page_aware() -> None:
    document = extract_document(
        _one_page_pdf("Policy sampling and optimization"),
        "application/pdf",
    )

    assert "Policy sampling" in document.text_for_page(1)
    with pytest.raises(ValueError, match="outside the source page range"):
        document.text_for_page(2)


def test_pdf_visual_line_wrap_hyphenation_is_joined() -> None:
    assert normalize_pdf_text("which al-\nternate between stages") == (
        "which alternate between stages"
    )
    assert normalize_pdf_text("policy-gradient remains inline") == (
        "policy-gradient remains inline"
    )


def test_acquisition_quarantines_failed_sources(tmp_path: Path) -> None:
    payload = json.loads(MANIFEST.read_text())
    payload["sources"] = payload["sources"][:1]
    payload["allowed_hosts"] = ["docs.pytorch.org"]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    result_path = tmp_path / "result" / "batch.json"
    snapshot_dir = result_path.parent / "snapshots"
    source_id = payload["sources"][0]["source"]["source_id"]

    class _FailThenOk:
        def __init__(self) -> None:
            self.calls = 0

        def fetch(self, url: str) -> FetchedSource:
            self.calls += 1
            raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    # Single-source manifest that 404s should fail the batch entirely.
    with pytest.raises(RuntimeError, match="failed for every approved URL"):
        acquire_source_manifest(
            manifest_path,
            snapshot_dir,
            result_path,
            provider=_FailThenOk(),
        )
    failures = json.loads(
        result_path.with_name("source-acquisition-failures.json").read_text()
    )
    assert failures[0]["source_id"] == source_id
    assert "404" in failures[0]["error"]


def test_acquisition_keeps_successful_sources_when_one_fails(tmp_path: Path) -> None:
    payload = {

        "acquisition_manifest_id": "manifest-mixed",
        "acquired_by_run": "run-mixed",
        "allowed_hosts": ["example.com", "docs.example.org"],
        "sources": [
            {

                "source": {

                    "source_id": "source-dead",
                    "source_type": "approved-product-source",
                    "title": "Dead",
                    "authors": [],
                    "year": 2024,
                    "url": "https://example.com/missing",
                    "accessed_at": "2024-01-01",
                    "authority": "primary",
                    "license_note": "test",
                },
                "accepted_media_types": ["text/html"],
                "max_bytes": 1_000_000,
            },
            {

                "source": {

                    "source_id": "source-live",
                    "source_type": "approved-product-source",
                    "title": "Live",
                    "authors": [],
                    "year": 2024,
                    "url": "https://docs.example.org/guide",
                    "accessed_at": "2024-01-01",
                    "authority": "official",
                    "license_note": "test",
                },
                "accepted_media_types": ["text/html"],
                "max_bytes": 1_000_000,
            },
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    result_path = tmp_path / "result" / "batch.json"
    snapshot_dir = result_path.parent / "snapshots"

    class _MixedProvider:
        def fetch(self, url: str) -> FetchedSource:
            if url.endswith("/missing"):
                raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)
            return FetchedSource(
                requested_url=url,
                resolved_url=url,
                media_type="text/html",
                content=b"<html><body>Collective communication evidence</body></html>",
            )

    batch = acquire_source_manifest(
        manifest_path,
        snapshot_dir,
        result_path,
        provider=_MixedProvider(),
    )
    assert [item.source_id for item in batch.acquisitions] == ["source-live"]
    failures = json.loads(
        result_path.with_name("source-acquisition-failures.json").read_text()
    )
    assert failures[0]["source_id"] == "source-dead"


def test_sync_dossier_drops_failed_sources_without_aborting() -> None:
    dossier = ResearchDossier(
        dossier_id="dossier-acq",
        title="Acquisition sync",
        audience="Engineers",
        learning_goal="Keep grounded topics after a dead link.",
        sources=[
            ProductSource(
                source_id="source-a",
                title="Official A",
                url="https://example.com/a",
                authority="official",
                credibility_rationale="Official primary documentation for the workflow.",
                publication_year=2024,
            ),
            ProductSource(
                source_id="source-b",
                title="Practice B",
                url="https://docs.example.org/b",
                authority="practitioner",
                credibility_rationale="Practitioner guide showing operational use.",
                publication_year=2024,
            ),
            ProductSource(
                source_id="source-dead",
                title="Dead link",
                url="https://example.com/missing",
                authority="primary",
                credibility_rationale="Primary paper that is no longer fetchable.",
                publication_year=2024,
            ),
        ],
        topics=[
            ResearchedTopic(
                topic_id="topic-keep",
                title="Keep me",
                why_required="Needed for the role.",
                real_world_use="Used when assembling a grounded evaluation workflow.",
                learning_outcomes=["Use A and B together."],
                source_refs=["source-a", "source-b", "source-dead"],
                practice_source_refs=["source-b"],
                claims=[
                    GroundedClaim(
                        claim_id="claim-1",
                        statement="A and B support the workflow.",
                        source_refs=["source-a", "source-b", "source-dead"],
                    )
                ],
                teaching_brief=(
                    "Teach the learner to combine the official contract with the practitioner "
                    "workflow, call out the dead-link limitation, and keep the exercise grounded "
                    "in the sources that still freeze successfully for evidence reopening."
                ),
            )
        ],
    )
    synced = sync_dossier_to_acquired_sources(
        dossier,
        acquired_source_ids={"source-a", "source-b"},
        failures=[
            AcquisitionFailure(
                source_id="source-dead",
                requested_url="https://example.com/missing",
                error="HTTP 404: Not Found",
            )
        ],
    )
    assert [item.source_id for item in synced.sources] == ["source-a", "source-b"]
    assert synced.topics[0].source_refs == ["source-a", "source-b"]
    assert any("source-dead" in note for note in synced.unresolved)


def test_acquisition_freezes_hashed_snapshot(tmp_path: Path) -> None:
    payload = json.loads(MANIFEST.read_text())
    payload["sources"] = payload["sources"][:1]
    payload["allowed_hosts"] = ["docs.pytorch.org"]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    result_path = tmp_path / "result" / "batch.json"
    snapshot_dir = result_path.parent / "snapshots"

    batch = acquire_source_manifest(
        manifest_path,
        snapshot_dir,
        result_path,
        provider=_StaticProvider(b"<html><body>Collective communication</body></html>"),
    )

    assert batch.acquisitions[0].content_hash.startswith("sha256:")
    snapshot_path = result_path.parent / batch.source_fixtures[0].snapshot_path
    assert snapshot_path.read_bytes().startswith(b"<html>")
    assert AcquisitionBatch.model_validate_json(result_path.read_text()) == batch


def test_snapshot_output_must_remain_with_batch(tmp_path: Path) -> None:
    result_path = tmp_path / "result" / "batch.json"

    with pytest.raises(ValueError, match="must be inside"):
        acquire_source_manifest(
            MANIFEST,
            tmp_path / "elsewhere",
            result_path,
            provider=_StaticProvider(b"plain", media_type="text/plain"),
        )

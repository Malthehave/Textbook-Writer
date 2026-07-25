"""Small deterministic text extraction for reviewed HTML and plain-text snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
import re

from pypdf import PdfReader


EXTRACTOR_VERSION = "multi-format-text-v2"


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    text: str
    pages: tuple[str, ...] = ()

    def text_for_page(self, page: int | None) -> str:
        if page is None:
            return self.text
        if not self.pages:
            raise ValueError("page-specific evidence requires a paginated source")
        if page < 1 or page > len(self.pages):
            raise ValueError(
                f"evidence page {page} is outside the source page range 1-{len(self.pages)}"
            )
        return self.pages[page - 1]


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._suppressed_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "template"}:
            self._suppressed_depth += 1
        elif tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "template"} and self._suppressed_depth:
            self._suppressed_depth -= 1
        elif tag in {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._suppressed_depth:
            self.parts.append(data)


def extract_document(content: bytes, media_type: str) -> ExtractedDocument:
    if media_type == "text/plain":
        return ExtractedDocument(text=normalize_text(content.decode("utf-8", errors="replace")))
    if media_type in {"text/html", "application/xhtml+xml"}:
        parser = _VisibleTextParser()
        parser.feed(content.decode("utf-8", errors="replace"))
        parser.close()
        return ExtractedDocument(text=normalize_text(" ".join(parser.parts)))
    if media_type == "application/pdf":
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise ValueError("encrypted PDF sources are not supported")
        if not reader.pages:
            raise ValueError("PDF source contains no pages")
        if len(reader.pages) > 2_000:
            raise ValueError("PDF source exceeds the 2,000-page extraction limit")
        pages = tuple(normalize_pdf_text(page.extract_text() or "") for page in reader.pages)
        if not any(pages):
            raise ValueError("PDF source contains no extractable text; OCR review is required")
        return ExtractedDocument(text=normalize_text(" ".join(pages)), pages=pages)
    raise ValueError(f"unsupported research snapshot media type: {media_type}")


def extract_text(content: bytes, media_type: str) -> str:
    return extract_document(content, media_type).text


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_pdf_text(value: str) -> str:
    # PDF extractors preserve visual line-wrap hyphenation. Join only a letter followed by
    # a hyphen, a physical newline, and a lowercase continuation; ordinary inline
    # compounds remain unchanged.
    dehyphenated = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", value)
    return normalize_text(dehyphenated)

"""Replaceable provider boundaries for deterministic source acquisition."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
from typing import Callable, Iterable, Protocol
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    OpenerDirector,
    Request,
    build_opener,
)


@dataclass(frozen=True, slots=True)
class FetchedSource:
    requested_url: str
    resolved_url: str
    media_type: str
    content: bytes


class SourceProvider(Protocol):
    """Acquire the actual source content that evidence locations reopen against."""

    def fetch(self, url: str) -> FetchedSource: ...


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, validate_redirect: Callable[[str], None]) -> None:
        super().__init__()
        self._validate_redirect = validate_redirect

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        self._validate_redirect(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpSourceProvider:
    """Bounded HTTPS acquisition for approved source URLs.

    The host allowlist gates only the requested URL from the acquisition manifest.
    Redirect destinations (CDNs, PDF mirrors) still require HTTPS and a public IP,
    but need not repeat the original host.
    """

    SUPPORTED_MEDIA_TYPES = {
        "application/pdf",
        "application/xhtml+xml",
        "text/html",
        "text/plain",
    }

    def __init__(
        self,
        *,
        allowed_hosts: Iterable[str],
        max_bytes: int = 25_000_000,
        timeout_seconds: float = 30.0,
        opener: OpenerDirector | None = None,
        resolver: Callable[[str], Iterable[str]] | None = None,
    ) -> None:
        self._allowed_hosts = {
            host.strip().lower().rstrip(".") for host in allowed_hosts if host.strip()
        }
        if not self._allowed_hosts:
            raise ValueError("HTTP source provider requires at least one allowed host")
        if max_bytes < 1:
            raise ValueError("HTTP source provider max_bytes must be positive")
        if timeout_seconds <= 0:
            raise ValueError("HTTP source provider timeout must be positive")
        self._max_bytes = max_bytes
        self._timeout_seconds = timeout_seconds
        self._resolver = resolver or _resolve_host
        self._opener = opener or build_opener(
            _SafeRedirectHandler(
                lambda url: self._validate_url(url, require_allowlist=False)
            )
        )

    def fetch(self, url: str) -> FetchedSource:
        self._validate_url(url, require_allowlist=True)
        request = Request(
            url,
            headers={
                "Accept": "application/pdf, text/html, application/xhtml+xml, text/plain",
                "Accept-Encoding": "identity",
                "User-Agent": "TextbookWriterResearch/0.1",
            },
            method="GET",
        )
        with self._opener.open(request, timeout=self._timeout_seconds) as response:
            resolved_url = response.geturl()
            self._validate_url(resolved_url, require_allowlist=False)
            media_type = _response_media_type(response)
            if media_type not in self.SUPPORTED_MEDIA_TYPES:
                raise ValueError(f"unsupported live source media type: {media_type}")
            declared_length = _response_content_length(response)
            if declared_length is not None and declared_length > self._max_bytes:
                raise ValueError(
                    f"live source declares {declared_length} bytes, exceeding limit {self._max_bytes}"
                )
            content = response.read(self._max_bytes + 1)
        if len(content) > self._max_bytes:
            raise ValueError(f"live source exceeds download limit {self._max_bytes} bytes")
        if not content:
            raise ValueError("live source response is empty")
        _validate_content_signature(content, media_type)
        return FetchedSource(
            requested_url=url,
            resolved_url=resolved_url,
            media_type=media_type,
            content=content,
        )

    def _validate_url(self, url: str, *, require_allowlist: bool) -> None:
        parsed = urlsplit(url)
        if parsed.scheme.lower() != "https":
            raise ValueError("live source URLs must use HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("live source URLs cannot contain credentials")
        if parsed.fragment:
            raise ValueError("live source URLs cannot contain fragments")
        if parsed.port not in {None, 443}:
            raise ValueError("live source URLs may use only the default HTTPS port")
        host = (parsed.hostname or "").lower().rstrip(".")
        if require_allowlist and host not in self._allowed_hosts:
            raise ValueError(f"live source host is not allowlisted: {host or '<missing>'}")
        addresses = list(self._resolver(host))
        if not addresses:
            raise ValueError(f"live source host did not resolve: {host}")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise ValueError(f"live source host resolves to a non-public address: {address}")


def _resolve_host(host: str) -> list[str]:
    return sorted(
        {
            item[4][0]
            for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    )


def _response_media_type(response: object) -> str:
    headers = getattr(response, "headers")
    if hasattr(headers, "get_content_type"):
        return str(headers.get_content_type()).lower()
    raw = headers.get("Content-Type", "application/octet-stream")
    return str(raw).split(";", 1)[0].strip().lower()


def _response_content_length(response: object) -> int | None:
    headers = getattr(response, "headers")
    raw = headers.get("Content-Length")
    if raw is None:
        return None
    try:
        length = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("live source has an invalid Content-Length header") from exc
    if length < 0:
        raise ValueError("live source has a negative Content-Length header")
    return length


def _validate_content_signature(content: bytes, media_type: str) -> None:
    if media_type == "application/pdf" and not content.lstrip().startswith(b"%PDF-"):
        raise ValueError("live source declared PDF but has no PDF signature")

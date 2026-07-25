"""Deterministic research acquisition and frozen evidence packets."""

from textbook_writer.research.acquire import acquire_source_manifest
from textbook_writer.research.packets import build_source_packets
from textbook_writer.research.product_archive import (
    prepare_product_acquisition_manifest,
    sync_dossier_to_acquired_sources,
)
from textbook_writer.research.providers import (
    FetchedSource,
    HttpSourceProvider,
    SourceProvider,
)

__all__ = [
    "FetchedSource",
    "HttpSourceProvider",
    "SourceProvider",
    "acquire_source_manifest",
    "build_source_packets",
    "prepare_product_acquisition_manifest",
    "sync_dossier_to_acquired_sources",
]

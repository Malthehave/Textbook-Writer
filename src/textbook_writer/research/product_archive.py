"""Freeze an approved production dossier into reproducible source artifacts."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from textbook_writer.models.evidence import SourceAuthority, SourceRecord
from textbook_writer.models.product import ResearchDossier, ResearchedTopic
from textbook_writer.models.research import (
    AcquisitionFailure,
    AcquisitionManifest,
    LiveSourceRequest,
)


def prepare_product_acquisition_manifest(
    dossier: ResearchDossier,
    output_path: Path,
    *,
    accessed_at: date | None = None,
) -> AcquisitionManifest:
    """Convert an approved dossier's exact URLs into a bounded HTTPS manifest."""

    access_date = accessed_at or date.today()
    requests: list[LiveSourceRequest] = []
    hosts: set[str] = set()
    for source in dossier.sources:
        parsed = urlsplit(source.url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if not host:
            raise ValueError(f"product source has no hostname: {source.url}")
        hosts.add(host)
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
        accepted = (
            ["application/pdf"]
            if parsed.path.lower().endswith(".pdf") or "/pdf/" in parsed.path.lower()
            else ["text/html", "application/xhtml+xml", "text/plain", "application/pdf"]
        )
        requests.append(
            LiveSourceRequest(
                source=SourceRecord(
                    source_id=source.source_id,
                    source_type="approved-product-source",
                    title=source.title,
                    authors=[],
                    year=source.publication_year,
                    url=url,
                    accessed_at=access_date,
                    authority=SourceAuthority(source.authority),
                    license_note=(
                        "Frozen for factual verification and locator reopening. Publication in the "
                        "textbook remains limited to attribution, short quotations, and paraphrase."
                    ),
                ),
                accepted_media_types=accepted,
            )
        )
    manifest = AcquisitionManifest(
        acquisition_manifest_id=f"manifest-{dossier.dossier_id}",
        acquired_by_run=f"archive-{dossier.dossier_id}",
        allowed_hosts=sorted(hosts),
        sources=requests,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def sync_dossier_to_acquired_sources(
    dossier: ResearchDossier,
    *,
    acquired_source_ids: set[str],
    failures: list[AcquisitionFailure] | None = None,
) -> ResearchDossier:
    """Shrink an approved dossier to sources that actually froze.

    Dead or unreadable URLs are removed from topics. Topics that can no longer meet
    grounding requirements are dropped into exclusions rather than aborting generation.
    """

    keep_ids = {
        item.source_id for item in dossier.sources if item.source_id in acquired_source_ids
    }
    if not keep_ids:
        raise RuntimeError(
            "source acquisition left no frozen sources for the approved dossier"
        )
    sources = [item for item in dossier.sources if item.source_id in keep_ids]
    failure_by_id = {
        item.source_id: item for item in (failures or []) if item.source_id
    }
    unresolved = list(dossier.unresolved)
    exclusions = list(dossier.exclusions)
    for source in dossier.sources:
        if source.source_id in keep_ids:
            continue
        failure = failure_by_id.get(source.source_id)
        detail = failure.error if failure is not None else "Not present in the frozen archive."
        note = (
            f"Could not freeze {source.source_id} ({source.title}) at {source.url}: {detail}"
        )
        if note not in unresolved:
            unresolved.append(note)

    kept_topics: list[ResearchedTopic] = []
    for topic in dossier.topics:
        source_refs = [ref for ref in topic.source_refs if ref in keep_ids]
        practice_refs = [ref for ref in topic.practice_source_refs if ref in keep_ids]
        claims = []
        for claim in topic.claims:
            claim_refs = [ref for ref in claim.source_refs if ref in keep_ids]
            if claim_refs:
                claims.append(claim.model_copy(update={"source_refs": claim_refs}))
        candidate = topic.model_copy(
            update={
                "source_refs": source_refs,
                "practice_source_refs": practice_refs,
                "claims": claims,
            }
        )
        try:
            ResearchDossier(
                dossier_id=dossier.dossier_id,
                title=dossier.title,
                audience=dossier.audience,
                learning_goal=dossier.learning_goal,
                sources=sources,
                topics=[candidate],
            )
        except ValidationError:
            exclusion = (
                f"Dropped {topic.topic_id} ({topic.title}) after source acquisition "
                "could not preserve two independent hosts and a practice signal."
            )
            if exclusion not in exclusions:
                exclusions.append(exclusion)
            continue
        kept_topics.append(candidate)

    if not kept_topics:
        raise RuntimeError(
            "source acquisition left no grounded topics for production"
        )
    return prune_unreferenced_sources(
        ResearchDossier(
            dossier_id=dossier.dossier_id,
            title=dossier.title,
            audience=dossier.audience,
            learning_goal=dossier.learning_goal,
            sources=sources,
            topics=kept_topics,
            exclusions=exclusions,
            unresolved=unresolved,
        )
    )


def referenced_source_ids(dossier: ResearchDossier) -> set[str]:
    refs: set[str] = set()
    for topic in dossier.topics:
        refs.update(topic.source_refs)
        refs.update(topic.practice_source_refs)
        for claim in topic.claims:
            refs.update(claim.source_refs)
    return refs


def prune_unreferenced_sources(dossier: ResearchDossier) -> ResearchDossier:
    """Drop dossier sources that no kept topic uses."""

    keep_ids = referenced_source_ids(dossier)
    sources = [item for item in dossier.sources if item.source_id in keep_ids]
    if len(sources) == len(dossier.sources):
        return dossier
    return dossier.model_copy(update={"sources": sources})

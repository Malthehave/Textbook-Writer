"""Production role catalog (agents + deterministic tools)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RoleKind = Literal["manager", "specialist", "independent", "optional", "tool"]


@dataclass(frozen=True, slots=True)
class TeamRole:
    role_id: str
    display_name: str
    kind: RoleKind
    phase: str
    does: str
    does_not: str


PRODUCTION_TEAM: tuple[TeamRole, ...] = (
    TeamRole(
        role_id="manager",
        display_name="Textbook manager",
        kind="manager",
        phase="all",
        does=(
            "Sole learner-facing agent: discovery, specialist tools, deterministic "
            "gates, approvals, and publication"
        ),
        does_not="Draft chapters, verify answers, invent page counts, or hold full source text",
    ),
    TeamRole(
        role_id="research-scout",
        display_name="Research scout",
        kind="optional",
        phase="discovery",
        does="Hosted web-search leads for sizing the book (tool of the manager)",
        does_not="Count as frozen evidence for production grounding",
    ),
    TeamRole(
        role_id="research-architect",
        display_name="Research architect",
        kind="specialist",
        phase="research",
        does="Build the research dossier: topics, sources, claims, practice signals",
        does_not="Write teaching prose or skip corroboration rules",
    ),
    TeamRole(
        role_id="research-auditor",
        display_name="Research auditor",
        kind="independent",
        phase="research",
        does="Independently web-audit dossier relevance, accuracy, and practice use",
        does_not="Preserve the architect's outline by default",
    ),
    TeamRole(
        role_id="acquire-sources",
        display_name="Acquire & freeze sources",
        kind="tool",
        phase="research",
        does="Download allowlisted URLs, content-hash snapshots, extract page-aware text",
        does_not="Invent URLs or accept unreadable payloads without quarantine",
    ),
    TeamRole(
        role_id="curriculum-architect",
        display_name="Curriculum architect",
        kind="specialist",
        phase="curriculum",
        does=(
            "Chapter plan, outcomes, running_system spine, visual slots, "
            "word/exercise budgets"
        ),
        does_not="Approve its own coverage or invent sources",
    ),
    TeamRole(
        role_id="coverage-auditor",
        display_name="Coverage auditor",
        kind="independent",
        phase="curriculum",
        does="Challenge missing topics and broken prerequisite order",
        does_not="Block solely on soft padding taste",
    ),
    TeamRole(
        role_id="curriculum-repair",
        display_name="Curriculum repair editor",
        kind="specialist",
        phase="curriculum",
        does="Repair plan after coverage reject while preserving topics and page target",
        does_not="Add unsupported subject matter or self-approve",
    ),
    TeamRole(
        role_id="chapter-writer",
        display_name="Chapter writer",
        kind="specialist",
        phase="produce",
        does=(
            "Long-form sections from frozen evidence; mention the planned figure id; "
            "draft exercises and solutions"
        ),
        does_not="Invent Typst diagram graphs, style the PDF, or use unfrozen claims",
    ),
    TeamRole(
        role_id="html-diagram-author",
        display_name="HTML diagram author",
        kind="specialist",
        phase="produce",
        does=(
            "Author one self-contained HTML pedagogical diagram per chapter from the "
            "planned visual and running system; pipeline rasterizes via KaTeX/Playwright"
        ),
        does_not="Use typed diagram templates, external URLs, scripts, or GPT Image",
    ),
    TeamRole(
        role_id="independent-verifier",
        display_name="Independent verifier",
        kind="independent",
        phase="produce",
        does="Solve exercises without draft answers, then compare; request one repair",
        does_not="See solutions on the first pass",
    ),
    TeamRole(
        role_id="continuity-editor",
        display_name="Continuity editor",
        kind="specialist",
        phase="integrate",
        does="Cross-chapter terminology, order, and open loops (soft in v1)",
        does_not="Silently rewrite canon or self-approve",
    ),
    TeamRole(
        role_id="bind-citations",
        display_name="Citation binder",
        kind="tool",
        phase="integrate",
        does="Map claims/sections/exercises to frozen chunks; build the ledger",
        does_not="Accept missing frozen evidence silently",
    ),
    TeamRole(
        role_id="publish",
        display_name="Typst publisher",
        kind="tool",
        phase="publish",
        does="Render PDF, measure pages/links/figures, emit publication report",
        does_not="Let models invent layout or unverified page counts",
    ),
)


def team_role_ids() -> list[str]:
    return [role.role_id for role in PRODUCTION_TEAM]

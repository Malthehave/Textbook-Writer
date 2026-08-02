"""Per-role Agents SDK specialists and the learner-facing manager.

Each chat owns ``/books/<session-id>/`` (host ``output/books/<session-id>/``).
That directory is the sandbox ``manifest.root`` for the chat — the agent only sees
that book. Other sessions' files are never wiped and are not on the sandbox path.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from agents.run import RunConfig, ToolExecutionConfig
from agents.sandbox import Manifest, SandboxRunConfig
from agents.sandbox.capabilities import Filesystem, LocalDirLazySkillSource, Shell, Skills
from agents.sandbox.entries import LocalDir
from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClient

BOOKS_ROOT = Path(os.environ.get("TEXTBOOK_BOOKS_ROOT", "/books")).resolve()
_SESSION_ID_RE = re.compile(r"^session-[0-9a-f]{10}$")


def session_book_root(session_id: str) -> Path:
    """Return this chat's book directory (``/books/<session-id>``)."""

    if not _SESSION_ID_RE.fullmatch(session_id):
        raise ValueError(f"invalid session id: {session_id!r}")
    root = (BOOKS_ROOT / session_id).resolve()
    if not root.is_relative_to(BOOKS_ROOT):
        raise ValueError(f"invalid session id: {session_id!r}")
    return root


def create_session_book(session_id: str) -> Path:
    """Create an empty book directory for a new chat. Does not touch other sessions."""

    root = session_book_root(session_id)
    root.mkdir(parents=True, exist_ok=False)
    for name in ("input", "state", "build", "production"):
        (root / name).mkdir()
    return root


def agent_capabilities(agent_file: str) -> list[Any]:
    """Shell + Filesystem, plus skills from ``<agent_dir>/skills/`` if present."""

    caps: list[Any] = [Shell(), Filesystem()]
    skills_dir = Path(agent_file).resolve().parent / "skills"
    if skills_dir.is_dir() and any(skills_dir.iterdir()):
        caps.append(
            Skills(
                lazy_from=LocalDirLazySkillSource(source=LocalDir(src=skills_dir)),
                skills_path=".agents/skills",
            )
        )
    return caps


def sandbox_tool_run_config(*, root: str | Path) -> RunConfig:
    """Use this chat's book directory as the sandbox root."""

    return RunConfig(
        sandbox=SandboxRunConfig(
            client=UnixLocalSandboxClient(),
            manifest=Manifest(root=str(Path(root))),
        ),
        tool_execution=ToolExecutionConfig(max_function_tool_concurrency=2),
    )


from textbook_writer.runtime.agents.chapter_writer.agent import build_chapter_writer_agent
from textbook_writer.runtime.agents.chapter_reviewer.agent import build_chapter_reviewer_agent
from textbook_writer.runtime.agents.curriculum_architect.agent import (
    build_curriculum_architect_agent,
)
from textbook_writer.runtime.agents.html_diagram_author import build_html_diagram_agent
from textbook_writer.runtime.agents.independent_verifier.agent import (
    build_independent_verifier_agent,
)
from textbook_writer.runtime.agents.manager import build_manager_agent
from textbook_writer.runtime.agents.persona_interviewer import build_persona_interviewer_agent
from textbook_writer.runtime.agents.research_architect.agent import build_research_architect_agent
from textbook_writer.runtime.agents.solution_comparator.agent import (
    build_solution_comparator_agent,
)

__all__ = [
    "BOOKS_ROOT",
    "agent_capabilities",
    "build_chapter_writer_agent",
    "build_chapter_reviewer_agent",
    "build_curriculum_architect_agent",
    "build_html_diagram_agent",
    "build_independent_verifier_agent",
    "build_manager_agent",
    "build_persona_interviewer_agent",
    "build_research_architect_agent",
    "build_solution_comparator_agent",
    "create_session_book",
    "sandbox_tool_run_config",
    "session_book_root",
]

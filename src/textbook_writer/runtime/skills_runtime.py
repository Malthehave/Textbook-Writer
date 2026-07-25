"""Attach packaged SKILL.md trees via the Agents SDK Skills capability.

Skills are not inlined into instructions. Skilled specialists are SandboxAgent
instances with Skills(+Filesystem) at init; as_tool() calls must pass a sandbox
RunConfig so the capability materializes in nested runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.run import RunConfig
from agents.sandbox import SandboxAgent, SandboxRunConfig
from agents.sandbox.capabilities import Filesystem, LocalDirLazySkillSource, Skills
from agents.sandbox.entries import LocalDir
from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClient

from textbook_writer.runtime.specialist_stream import emit_specialist_stream_event


def packaged_skills_root() -> Path:
    return Path(__file__).resolve().parents[1] / "skills"


def skills_capability() -> Skills:
    """SDK Skills capability: lazy-load packaged skills (SDK parses SKILL.md frontmatter)."""

    root = packaged_skills_root()
    if not root.is_dir():
        raise FileNotFoundError(f"skills root not found: {root}")
    return Skills(
        lazy_from=LocalDirLazySkillSource(source=LocalDir(src=root)),
        skills_path=".agents/skills",
    )


def skilled_agent_capabilities(*_skill_names: str) -> list[Any]:
    """Filesystem + Skills so the agent can open SKILL.md via progressive disclosure.

    Skill name args are accepted for call-site clarity but unused: the SDK indexes
    every packaged skill under ``skills/`` and parses frontmatter itself.
    """

    return [Filesystem(), skills_capability()]


def sandbox_tool_run_config() -> RunConfig:
    """RunConfig so SandboxAgent specialists materialize Skills when used as tools."""

    return RunConfig(sandbox=SandboxRunConfig(client=UnixLocalSandboxClient()))


def as_specialist_tool(agent: Any, **kwargs: Any) -> Any:
    """Agent.as_tool(), attaching sandbox RunConfig for SandboxAgent specialists."""

    if isinstance(agent, SandboxAgent):
        kwargs.setdefault("run_config", sandbox_tool_run_config())
    kwargs.setdefault("on_stream", emit_specialist_stream_event)
    return agent.as_tool(**kwargs)

"""Per-role Agents SDK specialists and the learner-facing manager."""

from textbook_writer.runtime.agents._shared import DEFAULT_RESEARCH_MODEL
from textbook_writer.runtime.agents.catalog import PRODUCTION_TEAM, TeamRole, team_role_ids
from textbook_writer.runtime.agents.chapter_writer.agent import build_chapter_writer_agent
from textbook_writer.runtime.agents.continuity_editor.agent import build_continuity_editor_agent
from textbook_writer.runtime.agents.coverage_auditor.agent import build_coverage_auditor_agent
from textbook_writer.runtime.agents.curriculum_architect.agent import (
    build_curriculum_architect_agent,
)
from textbook_writer.runtime.agents.curriculum_repair.agent import build_curriculum_repair_agent
from textbook_writer.runtime.agents.exercise_repair.agent import build_exercise_repair_agent
from textbook_writer.runtime.agents.html_diagram_author import (
    build_diagram_author_prompt,
    build_html_diagram_agent,
    persist_html_diagram_files,
    render_html_to_png,
)
from textbook_writer.runtime.agents.independent_verifier.agent import (
    build_independent_verifier_agent,
)
from textbook_writer.runtime.agents.manager import (
    build_manager_agent,
    manager_tool_names,
)
from textbook_writer.runtime.agents.research_architect.agent import build_research_architect_agent
from textbook_writer.runtime.agents.research_auditor.agent import build_research_auditor_agent
from textbook_writer.runtime.agents.research_scout import (
    build_research_scout_agent,
    collect_search_provenance,
    run_research_scout,
)
from textbook_writer.runtime.agents.solution_comparator.agent import (
    build_solution_comparator_agent,
)

__all__ = [
    "DEFAULT_RESEARCH_MODEL",
    "PRODUCTION_TEAM",
    "TeamRole",
    "build_chapter_writer_agent",
    "build_continuity_editor_agent",
    "build_coverage_auditor_agent",
    "build_curriculum_architect_agent",
    "build_curriculum_repair_agent",
    "build_diagram_author_prompt",
    "build_exercise_repair_agent",
    "build_html_diagram_agent",
    "build_independent_verifier_agent",
    "build_manager_agent",
    "build_research_architect_agent",
    "build_research_auditor_agent",
    "build_research_scout_agent",
    "build_solution_comparator_agent",
    "collect_search_provenance",
    "manager_tool_names",
    "persist_html_diagram_files",
    "render_html_to_png",
    "run_research_scout",
    "team_role_ids",
]

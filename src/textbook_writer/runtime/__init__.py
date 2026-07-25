"""Manager-led textbook runtime."""

from textbook_writer.runtime.agents import (
    DEFAULT_RESEARCH_MODEL,
    PRODUCTION_TEAM,
    build_manager_agent,
    build_research_scout_agent,
    manager_tool_names,
    run_research_scout,
    team_role_ids,
)
from textbook_writer.runtime.discovery_chat import (
    load_production_brief,
    suggest_page_band_values,
    write_production_brief,
)
from textbook_writer.runtime.quality import (
    ensure_chapter_bridges,
    ensure_plan_visuals,
    sanitize_plain_english_title,
    validate_chapter_content,
)
from textbook_writer.runtime.workspace import (
    BookWorkspace,
    BOOKS_ROOT,
    initialize_workspace,
    rename_workspace_to_title,
)
from textbook_writer.runtime.workspace_tools import (
    acquire_and_freeze_sources,
    assemble_product_book,
    build_frozen_citation_ledger,
    publish_product_book,
)

__all__ = [
    "BOOKS_ROOT",
    "BookWorkspace",
    "DEFAULT_RESEARCH_MODEL",
    "PRODUCTION_TEAM",
    "acquire_and_freeze_sources",
    "assemble_product_book",
    "build_frozen_citation_ledger",
    "build_manager_agent",
    "build_research_scout_agent",
    "ensure_chapter_bridges",
    "ensure_plan_visuals",
    "initialize_workspace",
    "load_production_brief",
    "manager_tool_names",
    "publish_product_book",
    "rename_workspace_to_title",
    "run_research_scout",
    "sanitize_plain_english_title",
    "suggest_page_band_values",
    "team_role_ids",
    "validate_chapter_content",
    "write_production_brief",
]

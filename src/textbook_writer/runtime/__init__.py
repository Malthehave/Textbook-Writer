"""Manager-led textbook runtime."""

from textbook_writer.runtime.agents import build_manager_agent
from textbook_writer.runtime.workspace_tools import build_textbook_pdf_tool

__all__ = [
    "build_manager_agent",
    "build_textbook_pdf_tool",
]

"""Book workspace bootstrap under output/books/."""

from __future__ import annotations

import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path

from textbook_writer.publishing.product import book_output_stem


BOOKS_ROOT = Path("output") / "books"


@dataclass(frozen=True, slots=True)
class BookWorkspace:
    root: Path
    session_db_path: Path
    build_dir: Path
    book_id: str


def initialize_workspace() -> BookWorkspace:
    """Create a new draft workspace for an interactive manager session."""

    digest = secrets.token_hex(5)
    root = (BOOKS_ROOT / f"draft-{digest}").resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "input").mkdir(exist_ok=True)
    (root / "state").mkdir(exist_ok=True)
    build_dir = root / "build"
    build_dir.mkdir(exist_ok=True)
    return BookWorkspace(
        root=root,
        session_db_path=root / "state" / "product-sessions.sqlite",
        build_dir=build_dir,
        book_id=f"book-{digest}",
    )


def rename_workspace_to_title(workspace: Path, title: str) -> Path:
    """Move draft-* workspaces to output/books/<title-slug>/ after the title is known."""

    workspace = workspace.resolve()
    slug = book_output_stem(title)
    target = (BOOKS_ROOT / slug).resolve()
    if workspace == target:
        return workspace
    if not workspace.name.startswith("draft-"):
        return workspace
    BOOKS_ROOT.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target == workspace:
            return workspace
        raise RuntimeError(f"cannot rename workspace to {target}: path already exists")
    shutil.move(str(workspace), str(target))
    return target

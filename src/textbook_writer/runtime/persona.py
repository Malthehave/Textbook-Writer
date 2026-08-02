"""Global learner persona used across every book chat."""

from __future__ import annotations

import os
from pathlib import Path

API_ROOT = Path(os.environ.get("TEXTBOOK_API_ROOT", Path.cwd())).resolve()
PERSONA_DIR = Path(
    os.environ.get("TEXTBOOK_PERSONA_DIR", API_ROOT / "output" / "learner")
).resolve()
PERSONA_FILENAME = "persona.md"
INTERVIEW_SESSION_ID = "learner-persona-interview"


def persona_dir() -> Path:
    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
    return PERSONA_DIR


def persona_path() -> Path:
    return persona_dir() / PERSONA_FILENAME


def interview_session_db() -> Path:
    return persona_dir() / "interview-sessions.sqlite"


def load_persona() -> str:
    path = persona_path()
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def save_persona(markdown: str) -> str:
    text = markdown.strip()
    path = persona_path()
    if not text:
        if path.is_file():
            path.unlink()
        return ""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text + "\n", encoding="utf-8")
    temporary.replace(path)
    return text + "\n"


def persona_section(markdown: str | None = None) -> str:
    text = (markdown if markdown is not None else load_persona()).strip()
    if not text:
        return ""
    return (
        "## Learner persona\n\n"
        "The following durable profile describes who this learner is. It is meant to be "
        "self-contained (including work history / CV substance). Treat it as established "
        "background for personalizing examples, framing, and depth. Do not re-ask identity, "
        "job history, or strengths/gaps already covered here, and do not spend web_search "
        "re-looking up their resume or bio for facts already written below. You still own "
        "agreeing the scope of *this* textbook in chat before research: topic, learning "
        "goals for this book, depth, length, time horizon, and must-cover items. Do not "
        "treat persona.md as a curriculum or study plan.\n\n"
        f"{text}\n"
    )

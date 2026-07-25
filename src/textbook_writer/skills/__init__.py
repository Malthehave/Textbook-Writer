"""Application runtime skills: each skill is skills/<name>/SKILL.md."""

from importlib.resources import files


def load_skill(name: str) -> str:
    """Load skills/<name>/SKILL.md from the packaged skills tree."""

    path = files("textbook_writer.skills").joinpath(name, "SKILL.md")
    if not path.is_file():
        raise FileNotFoundError(f"skill not found: skills/{name}/SKILL.md")
    return path.read_text(encoding="utf-8")

"""Auto-persist specialist outputs and inject prior stage artifacts into tool input.

Managers must not be prompted to copy/paste JSON between tools. Structured specialist
results write themselves under production/; auditors load prerequisites from disk.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from textbook_writer.runtime.workspace_tools import stages_dir, write_model

FIXED_OUTPUT_PATHS: dict[str, str] = {
    "research-scout": "research-scout.json",
    "research-architect": "research-dossier.json",
    "research-auditor": "research-audit.json",
    "curriculum-architect": "book-plan.json",
    "coverage-auditor": "plan-audit.json",
    "curriculum-repair": "book-plan.json",
    "continuity-editor": "continuity-audit.json",
}

# Tools that should receive these production/ files before the specialist runs.
INPUT_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "research-auditor": ("research-dossier.json",),
    "curriculum-architect": ("research-dossier.json",),
    "coverage-auditor": ("book-plan.json", "research-dossier.json"),
    "curriculum-repair": ("book-plan.json", "plan-audit.json"),
}


def resolve_output_path(tool_name: str, output: Any) -> str | None:
    """Return production/-relative path for a specialist output, or None if ephemeral."""

    fixed = FIXED_OUTPUT_PATHS.get(tool_name)
    if fixed:
        return fixed
    if tool_name in {"chapter-writer", "exercise-repair"}:
        chapter_id = _field(output, "chapter_id")
        return f"chapters-v1/{chapter_id}.json" if chapter_id else None
    if tool_name == "solution-comparator":
        chapter_ref = _field(output, "chapter_ref")
        return f"chapters-v1/{chapter_ref}.verification.json" if chapter_ref else None
    return None


def persist_specialist_output(
    *,
    workspace: Path,
    tool_name: str,
    output: Any,
) -> str | None:
    """Write structured output under production/. Returns relative path or None."""

    relative = resolve_output_path(tool_name, output)
    if relative is None or output is None:
        return None
    stages = stages_dir(workspace)
    path = (stages / relative).resolve()
    if not path.is_relative_to(stages.resolve()):
        raise ValueError(f"persist path escapes production/: {relative}")
    if isinstance(output, BaseModel):
        write_model(path, output)
    else:
        data = _as_dict(output)
        if not data:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    return relative


def summarize_output(tool_name: str, output: Any) -> dict[str, Any]:
    """Compact fields for the manager (full JSON is already on disk)."""

    data = _as_dict(output)
    if tool_name == "research-scout":
        return {
            "interpreted_goal": data.get("interpreted_goal"),
            "confirmed": (data.get("confirmed") or [])[:8],
            "unresolved": (data.get("unresolved") or [])[:8],
            "clarifying_questions": (data.get("clarifying_questions") or [])[:6],
            "candidate_competency_count": len(data.get("candidate_competencies") or []),
            "source_lead_count": len(data.get("source_leads") or []),
            "stopping_reason": data.get("stopping_reason"),
        }
    if tool_name == "research-architect":
        return {
            "title": data.get("title"),
            "topics": len(data.get("topics") or []),
            "sources": len(data.get("sources") or []),
            "unresolved": data.get("unresolved") or [],
        }
    if tool_name == "research-auditor":
        return {
            "decision": data.get("decision"),
            "missing_topics": (data.get("missing_topics") or [])[:8],
            "low_value_topics": (data.get("low_value_topics") or [])[:8],
            "topic_audit_count": len(data.get("topic_audits") or []),
        }
    if tool_name == "coverage-auditor":
        return {
            "decision": data.get("decision"),
            "missing_topic_refs": data.get("missing_topic_refs") or [],
            "ordering_issues": (data.get("ordering_issues") or [])[:6],
            "outcome_issues": (data.get("outcome_issues") or [])[:6],
            "padding_risks": (data.get("padding_risks") or [])[:4],
        }
    if tool_name in {"curriculum-architect", "curriculum-repair"}:
        chapters = data.get("chapters") or []
        return {
            "title": data.get("title"),
            "chapters": [
                {"chapter_id": item.get("chapter_id"), "title": item.get("title")}
                for item in chapters
                if isinstance(item, dict)
            ],
            "target_pages": data.get("target_pages"),
        }
    if tool_name in {"chapter-writer", "exercise-repair"}:
        return {
            "chapter_id": data.get("chapter_id"),
            "title": data.get("title"),
            "sections": len(data.get("sections") or []),
            "exercises": len(data.get("exercises") or []),
            "figures": len(data.get("figures") or []),
        }
    if tool_name == "solution-comparator":
        verdicts = data.get("verdicts") or []
        return {
            "chapter_ref": data.get("chapter_ref"),
            "verdicts": [
                {
                    "exercise_ref": item.get("exercise_ref"),
                    "decision": item.get("decision"),
                }
                for item in verdicts
                if isinstance(item, dict)
            ],
        }
    if tool_name == "continuity-editor":
        return {
            "decision": data.get("decision"),
            "chapter_refs": data.get("chapter_refs") or [],
            "concept_order_issues": (data.get("concept_order_issues") or [])[:6],
            "contradictions": (data.get("contradictions") or [])[:6],
        }
    return {"keys": sorted(data.keys())[:20]}


def make_persisting_extractor(
    workspace: Path,
    tool_name: str,
) -> Callable[[Any], Awaitable[str]]:
    """custom_output_extractor: persist then return a compact saved summary."""

    async def extract(result: Any) -> str:
        output = result.final_output
        if output is None:
            return f"{tool_name} returned no structured output"
        saved = persist_specialist_output(
            workspace=workspace, tool_name=tool_name, output=output
        )
        payload: dict[str, Any] = {
            "tool": tool_name,
            "summary": summarize_output(tool_name, output),
        }
        if saved:
            path = stages_dir(workspace) / saved
            payload["saved"] = saved
            payload["bytes"] = path.stat().st_size if path.is_file() else 0
        else:
            # Ephemeral tools (verifier, diagram): return a short dump.
            if isinstance(output, BaseModel):
                payload["output"] = output.model_dump(mode="json")
            elif hasattr(output, "model_dump"):
                payload["output"] = output.model_dump(mode="json")
            else:
                payload["output"] = str(output)[:8000]
        return json.dumps(payload, indent=2)

    return extract


def make_artifact_input_builder(
    workspace: Path,
    *relative_paths: str,
) -> Callable[[dict[str, Any]], Awaitable[str]]:
    """input_builder: append saved production/ JSON to the manager's brief."""

    async def build(options: dict[str, Any]) -> str:
        params = options.get("params")
        brief = ""
        if isinstance(params, dict):
            raw = params.get("input")
            if isinstance(raw, str):
                brief = raw.strip()
            elif raw is not None:
                brief = json.dumps(raw, indent=2)
        elif params is not None:
            brief = str(params)

        stages = stages_dir(workspace)
        sections: list[str] = []
        if brief:
            sections.append(brief)
        for relative in relative_paths:
            path = (stages / relative).resolve()
            if not path.is_relative_to(stages.resolve()):
                raise ValueError(f"artifact path escapes production/: {relative}")
            if not path.is_file():
                raise FileNotFoundError(
                    f"missing production/{relative}; complete the prior stage first"
                )
            sections.append(
                f"## production/{relative}\n```json\n{path.read_text(encoding='utf-8')}\n```"
            )
        if not sections:
            raise FileNotFoundError(
                f"no brief and missing artifacts: {', '.join(relative_paths)}"
            )
        return "\n\n".join(sections)

    return build


def _field(output: Any, name: str) -> str | None:
    value = getattr(output, name, None)
    if value is None and isinstance(output, dict):
        value = output.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_dict(output: Any) -> dict[str, Any]:
    if isinstance(output, BaseModel):
        return output.model_dump(mode="json")
    if hasattr(output, "model_dump"):
        data = output.model_dump(mode="json")
        return data if isinstance(data, dict) else {}
    if isinstance(output, dict):
        return output
    return {}

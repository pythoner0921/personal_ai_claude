"""Reflection generator: synthesize higher-level summaries from stable preferences."""
from __future__ import annotations

from pathlib import Path

from .engine_io import read_yaml, write_yaml, read_jsonl, now_iso, new_id

ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "memory"
RAW = ROOT / "raw"

STABLE_PATH = MEM / "stable_preferences.yaml"
RECENT_PATH = MEM / "recent_tendencies.yaml"
REFLECTIONS_PATH = MEM / "reflections.yaml"

# Trigger threshold: regenerate after this many new captured events
EVENT_THRESHOLD = 50


def _count_raw_events() -> int:
    """Count total raw interaction events."""
    return len(read_jsonl(RAW / "ai_interactions.jsonl"))


def _last_reflection_event_count() -> int:
    """Return the event count at last reflection generation."""
    data = read_yaml(REFLECTIONS_PATH)
    return int(data.get("last_event_count", 0))


def should_reflect(force: bool = False) -> bool:
    """Check if reflection generation should run."""
    if force:
        return True
    current = _count_raw_events()
    last = _last_reflection_event_count()
    return (current - last) >= EVENT_THRESHOLD


def _group_by_theme(items: list[dict]) -> dict[str, list[dict]]:
    """Group preferences into semantic themes for summarization."""
    themes: dict[str, list[dict]] = {
        "communication_style": [],
        "code_approach": [],
        "general": [],
    }
    for item in items:
        desc = (item.get("description", "") + " " + item.get("id", "")).lower()
        if any(kw in desc for kw in ("concise", "summary", "table", "format", "evidence", "verbose", "output")):
            themes["communication_style"].append(item)
        elif any(kw in desc for kw in ("modular", "compact", "code", "rewrite", "command")):
            themes["code_approach"].append(item)
        else:
            themes["general"].append(item)
    return {k: v for k, v in themes.items() if v}


def _synthesize_theme(theme: str, items: list[dict]) -> str:
    """Produce a 1-sentence summary for a theme group."""
    descs = [item.get("description", "") for item in items]
    confs = [item.get("confidence_score", 0.0) for item in items]
    avg_conf = sum(confs) / len(confs) if confs else 0.0

    if theme == "communication_style":
        parts = []
        for d in descs:
            dl = d.lower()
            if "summary" in dl or "before detail" in dl:
                parts.append("lead with summaries")
            elif "table" in dl:
                parts.append("use tables for comparisons")
            elif "concise" in dl:
                parts.append("keep output concise")
            elif "evidence" in dl:
                parts.append("cite specific files as evidence")
            else:
                parts.append(d)
        return f"Communication: {', '.join(parts)}. (avg confidence {avg_conf:.0%})"

    if theme == "code_approach":
        parts = []
        for d in descs:
            dl = d.lower()
            if "modular" in dl:
                parts.append("prefer modular incremental changes")
            elif "compact" in dl:
                parts.append("use compact command style")
            else:
                parts.append(d)
        return f"Code approach: {', '.join(parts)}. (avg confidence {avg_conf:.0%})"

    # general fallback
    joined = "; ".join(descs)
    return f"General: {joined}. (avg confidence {avg_conf:.0%})"


def generate_reflections(force: bool = False) -> dict | None:
    """Generate reflection summaries from current preferences.

    Returns the reflections data dict, or None if skipped.
    """
    if not should_reflect(force=force):
        return None

    stable = read_yaml(STABLE_PATH).get("items", [])
    recent = read_yaml(RECENT_PATH).get("items", [])

    # Only reflect on items with reasonable confidence
    all_items = [i for i in stable + recent if i.get("confidence_score", 0) >= 0.5]
    if not all_items:
        return None

    themes = _group_by_theme(all_items)
    summaries = []
    for theme_name, items in themes.items():
        summary_text = _synthesize_theme(theme_name, items)
        summaries.append({
            "id": new_id("ref"),
            "theme": theme_name,
            "summary": summary_text,
            "source_count": len(items),
            "source_ids": [i.get("id", "") for i in items],
        })

    data = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "last_event_count": _count_raw_events(),
        "summaries": summaries,
    }
    write_yaml(REFLECTIONS_PATH, data)
    return data

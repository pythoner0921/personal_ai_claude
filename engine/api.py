"""Public API surface for the personal_ai memory engine."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .engine_io import read_yaml
from .consolidate import run_consolidation, _jaccard_similarity, FUZZY_MERGE_THRESHOLD
from .inject_context import build_injection_payload, _decay_score
from .reflect import generate_reflections as _generate_reflections
from .memory_health import run_health_check, format_report
from .task_classify import classify_task

ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "memory"

STABLE_PATH = MEM / "stable_preferences.yaml"
RECENT_PATH = MEM / "recent_tendencies.yaml"
ARCHIVE_PATH = MEM / "archive.yaml"


def get_active_memories() -> list[dict]:
    """Return all active preferences (stable + recent) with computed decay."""
    stable = read_yaml(STABLE_PATH).get("items", [])
    recent = read_yaml(RECENT_PATH).get("items", [])
    for item in stable:
        item["_category"] = "stable"
        item["decay_score"] = round(_decay_score(item.get("last_seen", "")), 3)
    for item in recent:
        item["_category"] = "recent"
        item["decay_score"] = round(_decay_score(item.get("last_seen", "")), 3)
    return stable + recent


def get_archived_memories() -> list[dict]:
    """Return all archived preferences."""
    return read_yaml(ARCHIVE_PATH).get("items", [])


def search_memories(query: str, include_archived: bool = False) -> list[dict]:
    """Search preferences by keyword. Returns matches sorted by relevance."""
    memories = get_active_memories()
    if include_archived:
        memories += get_archived_memories()

    query_lower = query.lower()
    scored: list[tuple[float, dict]] = []
    for m in memories:
        desc = m.get("description", "")
        evidence = m.get("evidence_summary", "")
        text = f"{desc} {evidence}".lower()
        # Simple keyword match scoring
        tokens = [t for t in query_lower.split() if t]
        hits = sum(1 for t in tokens if t in text)
        if hits > 0:
            scored.append((hits + m.get("confidence_score", 0), m))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]


def generate_reflections(force: bool = False) -> dict | None:
    """Generate reflection summaries from current preferences."""
    return _generate_reflections(force=force)


def get_reflections() -> dict:
    """Return current reflection data."""
    return read_yaml(MEM / "reflections.yaml")


def get_memory_health() -> dict:
    """Run health check and return report dict."""
    return run_health_check()


def get_memory_health_text() -> str:
    """Run health check and return formatted text report."""
    return format_report(run_health_check())


def consolidate() -> dict[str, int]:
    """Run consolidation (dedup, noise filter, fuzzy merge, archival)."""
    return run_consolidation()


def get_injection_payload(query: str, project_id: str | None = None) -> dict:
    """Build the context injection payload for a given query."""
    return build_injection_payload(query, project_id=project_id)


def export_memory(output_path: str | Path) -> dict:
    """Export all memory state to a JSON file."""
    # Import here to avoid circular dependency with tools/
    import json
    from .engine_io import now_iso

    bundle = {
        "export_version": "1.0",
        "exported_at": now_iso(),
        "stable_preferences": read_yaml(STABLE_PATH),
        "recent_tendencies": read_yaml(RECENT_PATH),
        "archive": read_yaml(ARCHIVE_PATH),
        "deprecated_preferences": read_yaml(MEM / "deprecated_preferences.yaml"),
        "reflections": read_yaml(MEM / "reflections.yaml"),
    }
    path = Path(output_path)
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle


def import_memory(input_path: str | Path) -> dict[str, int]:
    """Import memory state from a JSON bundle. Backs up existing files first."""
    import json
    import shutil
    from .engine_io import write_yaml, now_iso, append_jsonl

    path = Path(input_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("export_version") != "1.0":
        raise ValueError(f"Unsupported export version: {data.get('export_version')}")

    file_map = {
        "stable_preferences": STABLE_PATH,
        "recent_tendencies": RECENT_PATH,
        "archive": ARCHIVE_PATH,
        "deprecated_preferences": MEM / "deprecated_preferences.yaml",
        "reflections": MEM / "reflections.yaml",
    }

    backup_dir = MEM / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for key, fpath in file_map.items():
        if fpath.exists():
            shutil.copy2(fpath, backup_dir / f"{fpath.stem}_pre_import{fpath.suffix}")

    counts: dict[str, int] = {}
    for key, fpath in file_map.items():
        if key in data and data[key]:
            write_yaml(fpath, data[key])
            items = data[key].get("items", data[key].get("summaries", []))
            counts[key] = len(items) if isinstance(items, list) else 0

    append_jsonl(MEM / "change_log.jsonl", {
        "timestamp": now_iso(),
        "change_type": "import",
        "source": str(path),
        "counts": counts,
    })
    return counts

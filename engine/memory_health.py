"""Memory health monitor: report on memory system quality metrics."""
from __future__ import annotations

from pathlib import Path

from .engine_io import read_yaml, read_jsonl, append_jsonl, now_iso
from .consolidate import _jaccard_similarity, FUZZY_MERGE_THRESHOLD

ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "memory"
STATE = ROOT / "state"

STABLE_PATH = MEM / "stable_preferences.yaml"
RECENT_PATH = MEM / "recent_tendencies.yaml"
ARCHIVE_PATH = MEM / "archive.yaml"
DEPRECATED_PATH = MEM / "deprecated_preferences.yaml"
HEALTH_LOG = STATE / "health_log.jsonl"


def _detect_duplicates(items: list[dict]) -> list[tuple[str, str, float]]:
    """Find pairs of items with high keyword overlap that might be duplicates."""
    dupes: list[tuple[str, str, float]] = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            desc_i = items[i].get("description", "")
            desc_j = items[j].get("description", "")
            sim = _jaccard_similarity(desc_i, desc_j)
            if sim >= FUZZY_MERGE_THRESHOLD * 0.8:  # slightly lower threshold for detection
                dupes.append((desc_i, desc_j, round(sim, 3)))
    return dupes


def run_health_check() -> dict:
    """Run a health check on the memory system and return a report."""
    stable = read_yaml(STABLE_PATH).get("items", [])
    recent = read_yaml(RECENT_PATH).get("items", [])
    archive = read_yaml(ARCHIVE_PATH).get("items", [])
    deprecated = read_yaml(DEPRECATED_PATH).get("items", [])

    all_active = stable + recent
    duplicates = _detect_duplicates(all_active)

    # Confidence distribution
    confs = [i.get("confidence_score", 0) for i in all_active]
    avg_conf = sum(confs) / len(confs) if confs else 0.0

    # Decay health: items with very low decay
    low_decay = [i for i in all_active if i.get("decay_score", 1.0) < 0.5]

    # Usage stats
    used = [i for i in all_active if int(i.get("use_count", 0)) > 0]

    report = {
        "timestamp": now_iso(),
        "total_active": len(all_active),
        "stable_count": len(stable),
        "recent_count": len(recent),
        "archived_count": len(archive),
        "deprecated_count": len(deprecated),
        "duplicate_candidates": len(duplicates),
        "duplicate_details": [{"a": a, "b": b, "similarity": s} for a, b, s in duplicates],
        "avg_confidence": round(avg_conf, 3),
        "low_decay_count": len(low_decay),
        "used_count": len(used),
        "unused_count": len(all_active) - len(used),
    }

    # Persist to health log
    append_jsonl(HEALTH_LOG, report)

    return report


def format_report(report: dict) -> str:
    """Format a health report as readable text."""
    lines = [
        "Memory Health Report",
        f"  Active preferences:  {report['total_active']} (stable={report['stable_count']}, recent={report['recent_count']})",
        f"  Archived:            {report['archived_count']}",
        f"  Deprecated:          {report['deprecated_count']}",
        f"  Avg confidence:      {report['avg_confidence']:.1%}",
        f"  Used / unused:       {report['used_count']} / {report['unused_count']}",
        f"  Low decay (< 0.5):   {report['low_decay_count']}",
        f"  Duplicate candidates: {report['duplicate_candidates']}",
    ]
    if report["duplicate_details"]:
        for d in report["duplicate_details"]:
            lines.append(f"    ~ \"{d['a']}\" ≈ \"{d['b']}\" (sim={d['similarity']})")
    return "\n".join(lines)

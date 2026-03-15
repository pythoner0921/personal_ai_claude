"""Export all memory state into a single JSON bundle."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.engine_io import read_yaml, now_iso

ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "memory"
DEFAULT_OUT = ROOT / "memory_export.json"


def export_memory(output_path: Path | None = None) -> dict:
    bundle = {
        "export_version": "1.0",
        "exported_at": now_iso(),
        "stable_preferences": read_yaml(MEM / "stable_preferences.yaml"),
        "recent_tendencies": read_yaml(MEM / "recent_tendencies.yaml"),
        "archive": read_yaml(MEM / "archive.yaml"),
        "deprecated_preferences": read_yaml(MEM / "deprecated_preferences.yaml"),
        "reflections": read_yaml(MEM / "reflections.yaml"),
    }

    out = output_path or DEFAULT_OUT
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle


if __name__ == "__main__":
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    bundle = export_memory(out_path)
    target = out_path or DEFAULT_OUT
    stable_n = len(bundle["stable_preferences"].get("items", []))
    recent_n = len(bundle["recent_tendencies"].get("items", []))
    archive_n = len(bundle["archive"].get("items", []))
    print(f"Exported {stable_n} stable, {recent_n} recent, {archive_n} archived → {target}")

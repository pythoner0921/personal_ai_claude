"""Import memory state from a JSON bundle created by export_memory.py."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.engine_io import write_yaml, now_iso, append_jsonl

ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "memory"
CHANGE_LOG = MEM / "change_log.jsonl"

FILE_MAP = {
    "stable_preferences": MEM / "stable_preferences.yaml",
    "recent_tendencies": MEM / "recent_tendencies.yaml",
    "archive": MEM / "archive.yaml",
    "deprecated_preferences": MEM / "deprecated_preferences.yaml",
    "reflections": MEM / "reflections.yaml",
}


def import_memory(input_path: Path) -> dict[str, int]:
    data = json.loads(input_path.read_text(encoding="utf-8"))

    if data.get("export_version") != "1.0":
        raise ValueError(f"Unsupported export version: {data.get('export_version')}")

    # Backup current files before overwriting
    backup_dir = MEM / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for key, path in FILE_MAP.items():
        if path.exists():
            shutil.copy2(path, backup_dir / f"{path.stem}_pre_import{path.suffix}")

    counts: dict[str, int] = {}
    for key, path in FILE_MAP.items():
        if key in data and data[key]:
            write_yaml(path, data[key])
            items = data[key].get("items", data[key].get("summaries", []))
            counts[key] = len(items) if isinstance(items, list) else 0

    append_jsonl(CHANGE_LOG, {
        "timestamp": now_iso(),
        "change_type": "import",
        "source": str(input_path),
        "counts": counts,
    })

    return counts


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/import_memory.py <export.json>")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    counts = import_memory(path)
    print(f"Imported from {path}:")
    for k, v in counts.items():
        print(f"  {k}: {v} items")
    print(f"Backups saved to memory/backup/")

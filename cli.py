#!/usr/bin/env python
"""CLI interface for the personal_ai memory engine."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure engine is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.api import (
    get_active_memories,
    get_archived_memories,
    search_memories,
    generate_reflections,
    get_reflections,
    get_memory_health,
    get_memory_health_text,
    consolidate,
    export_memory,
    import_memory,
)


def cmd_health(args: argparse.Namespace) -> None:
    print(get_memory_health_text())


def cmd_list(args: argparse.Namespace) -> None:
    memories = get_active_memories()
    if not memories:
        print("No active memories.")
        return
    for m in sorted(memories, key=lambda x: x.get("confidence_score", 0), reverse=True):
        cat = m.get("_category", "?")
        conf = m.get("confidence_score", 0)
        decay = m.get("decay_score", 1.0)
        uses = int(m.get("use_count", 0))
        desc = m.get("description", "")
        print(f"  [{cat:6s}] ({conf:.2f}|d={decay:.2f}|u={uses:2d}) {desc}")


def cmd_search(args: argparse.Namespace) -> None:
    results = search_memories(args.query, include_archived=args.archived)
    if not results:
        print(f"No matches for '{args.query}'.")
        return
    for m in results:
        cat = m.get("_category", "archived")
        conf = m.get("confidence_score", 0)
        print(f"  [{cat}] ({conf:.2f}) {m.get('description', '')}")


def cmd_reflect(args: argparse.Namespace) -> None:
    result = generate_reflections(force=True)
    if result:
        for s in result.get("summaries", []):
            print(f"  [{s['theme']}] {s['summary']}")
    else:
        print("No reflections generated (not enough data).")


def cmd_consolidate(args: argparse.Namespace) -> None:
    result = consolidate()
    print(f"Consolidation complete:")
    for k, v in result.items():
        print(f"  {k}: {v}")


def cmd_dashboard(args: argparse.Namespace) -> None:
    from tools.memory_dashboard import generate_dashboard
    path = generate_dashboard()
    print(f"Dashboard written to {path}")


def cmd_export(args: argparse.Namespace) -> None:
    bundle = export_memory(args.file)
    stable_n = len(bundle.get("stable_preferences", {}).get("items", []))
    recent_n = len(bundle.get("recent_tendencies", {}).get("items", []))
    archive_n = len(bundle.get("archive", {}).get("items", []))
    print(f"Exported {stable_n} stable, {recent_n} recent, {archive_n} archived → {args.file}")


def cmd_import(args: argparse.Namespace) -> None:
    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    counts = import_memory(path)
    print(f"Imported from {path}:")
    for k, v in counts.items():
        print(f"  {k}: {v} items")
    print("Backups saved to memory/backup/")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="personal_ai",
        description="Personal AI Memory Engine CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # memory subcommand group
    mem = sub.add_parser("memory", help="Memory system commands")
    mem_sub = mem.add_subparsers(dest="subcmd")

    mem_sub.add_parser("health", help="Show memory health report")
    mem_sub.add_parser("list", help="List active memories")
    mem_sub.add_parser("reflect", help="Generate reflections")
    mem_sub.add_parser("consolidate", help="Run consolidation")
    mem_sub.add_parser("dashboard", help="Generate HTML dashboard")

    search_p = mem_sub.add_parser("search", help="Search memories")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--archived", action="store_true", help="Include archived")

    export_p = mem_sub.add_parser("export", help="Export memory to JSON")
    export_p.add_argument("file", help="Output JSON file path")

    import_p = mem_sub.add_parser("import", help="Import memory from JSON")
    import_p.add_argument("file", help="Input JSON file path")

    args = parser.parse_args()

    if args.command != "memory" or not args.subcmd:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "health": cmd_health,
        "list": cmd_list,
        "search": cmd_search,
        "reflect": cmd_reflect,
        "consolidate": cmd_consolidate,
        "dashboard": cmd_dashboard,
        "export": cmd_export,
        "import": cmd_import,
    }
    dispatch[args.subcmd](args)


if __name__ == "__main__":
    main()

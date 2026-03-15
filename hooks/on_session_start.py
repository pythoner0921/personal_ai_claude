#!/usr/bin/env python
"""SessionStart hook: inject existing preferences at session startup."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add engine to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.inject_context import build_injection_payload, output_for_claude_hook
from engine.engine_io import read_yaml, append_jsonl
from engine.session import create_new_session
from engine.reflect import generate_reflections

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
MEM = ROOT / "memory"


def main() -> None:
    try:
        # Read stdin (Claude hook passes JSON)
        stdin_data = sys.stdin.read().strip()
        hook_input = json.loads(stdin_data) if stdin_data else {}
    except (json.JSONDecodeError, Exception):
        hook_input = {}

    # Generate a new session ID for this session
    session_id = create_new_session()
    project_id = os.environ.get("CLAUDE_PROJECT_DIR", "global")

    # Check if any preferences exist
    stable = read_yaml(MEM / "stable_preferences.yaml").get("items", [])
    recent = read_yaml(MEM / "recent_tendencies.yaml").get("items", [])

    if not stable and not recent:
        # No preferences yet, silent exit
        sys.exit(0)

    # Generate reflections if threshold reached (once per session start)
    try:
        generate_reflections(force=False)
    except Exception:
        pass  # Reflection is best-effort

    # Load and inject reflection summaries before preferences
    reflections = read_yaml(MEM / "reflections.yaml")
    reflection_lines = []
    for s in reflections.get("summaries", []):
        reflection_lines.append(f"- {s.get('summary', '')}")

    # Build and output injection payload
    payload = build_injection_payload(
        query="session_start",
        budget_chars=600,
        project_id=project_id
    )

    # Prepend reflections to the preference payload
    if reflection_lines:
        reflection_text = "User Profile (reflections)\n" + "\n".join(reflection_lines) + "\n\n"
        payload["payload_text"] = reflection_text + payload["payload_text"]

    output_for_claude_hook(payload, hook_event="SessionStart")

    # Log evidence
    append_jsonl(STATE / "evidence.jsonl", {
        "event": "session_start_inject",
        "session_id": session_id,
        "project_id": project_id,
        "preferences_injected": payload["selected_count"],
        "timestamp": __import__("datetime").datetime.now().isoformat()
    })


if __name__ == "__main__":
    main()

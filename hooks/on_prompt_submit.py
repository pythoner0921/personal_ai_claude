#!/usr/bin/env python
"""UserPromptSubmit hook: capture prompt + inject preferences (lightweight).

Extract/update pipeline has been moved to on_stop.py to keep this hook fast.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

# Add engine to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.engine_io import append_jsonl
from engine.capture import capture_from_hook_input
from engine.session import get_or_create_session_id
from engine.inject_context import build_injection_payload, output_for_claude_hook

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"


def main() -> None:
    try:
        # Read stdin JSON from Claude hook
        stdin_data = sys.stdin.read().strip()
        hook_input = json.loads(stdin_data) if stdin_data else {}
    except (json.JSONDecodeError, Exception):
        hook_input = {}

    session_id = get_or_create_session_id()
    project_id = os.environ.get("CLAUDE_PROJECT_DIR", "global")
    prompt = hook_input.get("prompt", "")

    if not prompt:
        sys.exit(0)

    try:
        # 1. Capture: record prompt event (fast, append-only)
        capture_from_hook_input(hook_input, session_id)
    except Exception:
        # Log error but don't block
        append_jsonl(STATE / "evidence.jsonl", {
            "event": "capture_error",
            "session_id": session_id,
            "error": traceback.format_exc(),
            "timestamp": __import__("datetime").datetime.now().isoformat()
        })

    try:
        # 2. Inject: output preferences as additionalContext
        payload = build_injection_payload(
            query=prompt[:120],
            budget_chars=600,
            project_id=project_id
        )

        if payload["selected_count"] > 0:
            output_for_claude_hook(payload, hook_event="UserPromptSubmit")

        # Log evidence
        append_jsonl(STATE / "evidence.jsonl", {
            "event": "prompt_submit_pipeline",
            "session_id": session_id,
            "project_id": project_id,
            "prompt_length": len(prompt),
            "preferences_injected": payload["selected_count"],
            "timestamp": __import__("datetime").datetime.now().isoformat()
        })
    except Exception:
        # Never block the user
        append_jsonl(STATE / "evidence.jsonl", {
            "event": "inject_error",
            "session_id": session_id,
            "error": traceback.format_exc(),
            "timestamp": __import__("datetime").datetime.now().isoformat()
        })


if __name__ == "__main__":
    main()

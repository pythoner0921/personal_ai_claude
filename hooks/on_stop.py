#!/usr/bin/env python
"""Stop hook: capture assistant response patterns and update preferences."""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

# Add engine to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.engine_io import append_jsonl, read_yaml
from engine.capture import capture_ai_interaction
from engine.extract import run as run_extract
from engine.update_preferences import run_update
from engine.llm_analyze import analyze_interaction, should_call_llm
from engine.session import get_or_create_session_id
from engine.consolidate import is_noise, run_consolidation, rotate_change_log
from engine.reflect import generate_reflections
from engine.memory_health import run_health_check

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
RAW = ROOT / "raw"
CONFIG_PATH = ROOT / "config.yaml"


def _build_response_patterns() -> dict[str, list[str]]:
    """Load response-side keyword patterns from taxonomy config.

    Reads the 'response_keywords' field from each taxonomy entry.
    Also maps legacy key 'simplify' → 'concise_output' for backward compat.
    """
    cfg = read_yaml(CONFIG_PATH)
    taxonomy = cfg.get("taxonomy", {})
    legacy = cfg.get("legacy_marker_map", {})
    patterns: dict[str, list[str]] = {}
    for key, entry in taxonomy.items():
        if isinstance(entry, dict) and "response_keywords" in entry:
            patterns[key] = entry["response_keywords"]
    # Map legacy aliases (e.g., simplify → concise_output)
    for old_key, new_key in legacy.items():
        if new_key in patterns and old_key not in patterns:
            patterns[old_key] = patterns[new_key]
    return patterns


def detect_response_markers(text: str) -> list[str]:
    """Detect behavioral patterns in assistant response using taxonomy config."""
    patterns = _build_response_patterns()
    lower = text.lower()
    found: list[str] = []
    for marker, keywords in patterns.items():
        if any(kw in lower for kw in keywords):
            found.append(marker)
    return found


def main() -> None:
    try:
        stdin_data = sys.stdin.read().strip()
        hook_input = json.loads(stdin_data) if stdin_data else {}
    except (json.JSONDecodeError, Exception):
        hook_input = {}

    session_id = get_or_create_session_id()
    project_id = os.environ.get("CLAUDE_PROJECT_DIR", "global")

    # Extract the assistant's last message from stop_reason or content
    # Claude Code Stop hook provides: stop_reason, last_assistant_message
    last_message = hook_input.get("last_assistant_message", "")
    if not last_message:
        # Try to get from response content
        last_message = hook_input.get("response", "")

    if not last_message:
        sys.exit(0)

    # Get the user's prompt for LLM analysis context
    user_prompt = hook_input.get("prompt", hook_input.get("input", ""))

    try:
        # 1. Keyword-based detection (fast, always runs)
        markers = detect_response_markers(last_message)

        if markers:
            capture_ai_interaction(
                prompt_intent="[response_pattern]",
                markers=",".join(markers),
                session_id=session_id,
                project_id=project_id
            )

        # 2. LLM-based analysis (local Ollama, gated + best-effort)
        llm_patterns: list[str] = []
        llm_confidence = 0.0
        llm_skipped = ""
        try:
            call_llm, gate_reason = should_call_llm(
                response_length=len(last_message),
                keyword_markers_found=len(markers),
            )
            if call_llm:
                llm_result = analyze_interaction(user_prompt, last_message)
                if llm_result and llm_result["confidence"] >= 0.4:
                    llm_patterns = llm_result["patterns"]
                    llm_confidence = llm_result["confidence"]
                    # Filter out task-specific noise before recording
                    llm_patterns = [p for p in llm_patterns if not is_noise(p)]
                    if llm_patterns:
                        capture_ai_interaction(
                            prompt_intent="[llm_behavior_analysis]",
                            markers=",".join(llm_patterns),
                            session_id=session_id,
                            project_id=project_id
                        )
            else:
                llm_skipped = gate_reason
        except Exception:
            pass  # LLM analysis is best-effort, never block

        # 3. Re-run extract + update + consolidate pipeline if anything was detected
        if markers or llm_patterns:
            run_extract()
            run_update()
            # 4. Consolidate: dedup synonyms, remove noise, rotate logs
            try:
                run_consolidation()
                rotate_change_log(max_lines=200)
            except Exception:
                pass  # Consolidation is best-effort

            # 5. Generate reflections if threshold reached or session end
            try:
                generate_reflections(force=False)
            except Exception:
                pass  # Reflection is best-effort

            # 6. Memory health check (once per session end)
            try:
                run_health_check()
            except Exception:
                pass  # Health check is best-effort

        # Log evidence
        append_jsonl(STATE / "evidence.jsonl", {
            "event": "stop_capture",
            "session_id": session_id,
            "project_id": project_id,
            "response_length": len(last_message),
            "markers_detected": markers,
            "llm_patterns": llm_patterns,
            "llm_confidence": llm_confidence,
            "llm_skipped": llm_skipped,
            "timestamp": __import__("datetime").datetime.now().isoformat()
        })
    except Exception:
        append_jsonl(STATE / "evidence.jsonl", {
            "event": "stop_error",
            "session_id": session_id,
            "error": traceback.format_exc(),
            "timestamp": __import__("datetime").datetime.now().isoformat()
        })


if __name__ == "__main__":
    main()

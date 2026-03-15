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

from engine.engine_io import append_jsonl
from engine.capture import capture_ai_interaction
from engine.extract import run as run_extract
from engine.update_preferences import run_update
from engine.llm_analyze import analyze_interaction
from engine.session import get_or_create_session_id
from engine.consolidate import is_noise, run_consolidation, rotate_change_log
from engine.reflect import generate_reflections
from engine.memory_health import run_health_check

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
RAW = ROOT / "raw"

# Response pattern detectors (detect what Claude actually does in responses)
RESPONSE_PATTERNS: dict[str, list[str]] = {
    "summary_first": ["summary", "overview", "摘要", "概要", "tldr", "tl;dr", "总结", "结论"],
    "modular_changes": ["step 1", "step 2", "分步", "逐步", "first,", "then,", "方案 1", "方案 2"],
    "simplify": ["simply", "in short", "简单来说", "简而言之", "一句话说"],
    "use_chinese": ["诊断", "建议", "修复", "检查", "问题"],  # response is in Chinese
    "use_tables": ["| ", "|-", "| ---"],  # markdown table detected
    "show_evidence": ["具体文件", "file_path", "line ", "第 ", "行 "],
}


def detect_response_markers(text: str) -> list[str]:
    """Detect behavioral patterns in assistant response."""
    lower = text.lower()
    found: list[str] = []
    for marker, keywords in RESPONSE_PATTERNS.items():
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

        # 2. LLM-based analysis (local Ollama, best-effort)
        llm_patterns: list[str] = []
        llm_confidence = 0.0
        try:
            llm_result = analyze_interaction(user_prompt, last_message)
            if llm_result and llm_result["confidence"] >= 0.4:
                llm_patterns = llm_result["patterns"]
                llm_confidence = llm_result["confidence"]
                # Record LLM-detected patterns as events
                # Filter out task-specific noise before recording
                llm_patterns = [p for p in llm_patterns if not is_noise(p)]
                if llm_patterns:
                    capture_ai_interaction(
                        prompt_intent="[llm_behavior_analysis]",
                        markers=",".join(llm_patterns),
                        session_id=session_id,
                        project_id=project_id
                    )
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

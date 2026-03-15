from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from .engine_io import append_jsonl, new_id, now_iso


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"

# Keyword → marker mapping (supports Chinese + English)
MARKER_KEYWORDS: dict[str, list[str]] = {
    # Communication style
    "summary_first": ["摘要", "summary", "先总结", "概要", "overview first", "先给摘要", "先说结论", "结论先行"],
    "simplify": ["简洁", "简单", "simplify", "concise", "brief", "精简", "别啰嗦", "少废话", "直接说"],
    "use_chinese": ["用中文", "中文回复", "说中文", "chinese", "请用中文"],
    "use_tables": ["用表格", "表格形式", "table format", "用表格展示"],
    "show_evidence": ["给证据", "证据", "依据", "evidence", "show proof", "哪个文件", "具体文件"],
    # Execution style
    "modular_changes": ["模块化", "modular", "incremental", "逐步", "分步", "小步", "一步一步", "最小改动"],
    "avoid_interruptions": ["不要问", "别问", "don't ask", "no questions", "直接做", "just do it", "别确认"],
    "check_before_change": ["先检查", "先看看", "先读", "read first", "check first", "先确认一下"],
    "prefer_diagnosis": ["诊断", "diagnose", "排查", "定位问题", "根因", "root cause", "什么原因"],
    # Decision style
    "wants_options": ["给我选项", "有哪些方案", "options", "几种方案", "哪些选择", "你建议"],
    "prefers_direct_action": ["直接改", "直接做", "不用问", "just fix", "just do", "帮我改"],
    # Scope control
    "no_over_engineering": ["不要过度", "别过度", "不要大重构", "最小修复", "minimal", "不要加额外的"],
    "stay_focused": ["不要跑题", "别跑题", "专注", "focus", "只做这个", "不要扩展"],
}


def detect_markers(prompt: str) -> list[str]:
    """Scan prompt text for preference keywords and return matching markers."""
    text = prompt.lower()
    found: list[str] = []
    for marker, keywords in MARKER_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            found.append(marker)
    return found


def _command_shape(command: str) -> str:
    cmd = command.strip().lower()
    cmd = re.sub(r"[a-zA-Z]:\\[^ ]*", "<path>", cmd)
    cmd = re.sub(r"/[^ ]+", "<path>", cmd)
    cmd = re.sub(r"\b\d+\b", "<num>", cmd)
    return cmd[:240]


def _layer_for_command(command: str) -> str:
    cmd = command.lower().strip()
    project_markers = ["git ", "pytest", "npm ", "pnpm ", "cargo ", "mvn ", "gradle", "make "]
    personal_markers = ["date", "whoami", "echo ", "pwd", "cd "]
    if any(m in cmd for m in project_markers):
        return "project"
    if any(cmd.startswith(m) for m in personal_markers):
        return "personal"
    return "mixed"


def capture_terminal_command(command: str, cwd: str, session_id: str, project_id: str | None = None) -> dict:
    event = {
        "schema_version": "1.0",
        "event_id": new_id("evt"),
        "event_type": "terminal_command",
        "timestamp": now_iso(),
        "session_id": session_id,
        "layer": _layer_for_command(command),
        "project_id": project_id,
        "source": "claude_code",
        "payload": {
            "cwd": cwd,
            "command_shape": _command_shape(command),
            "command_hash": hashlib.sha256(command.encode("utf-8")).hexdigest()[:16],
            "token_count": len(command.split()),
            "has_pipe": "|" in command,
            "has_redirect": ">" in command or "<" in command
        }
    }
    append_jsonl(RAW_DIR / "episodic.jsonl", event)
    return event


def capture_manual_note(summary: str, note_type: str, session_id: str, tags: str = "") -> dict:
    tag_list = [x.strip() for x in tags.split(",") if x.strip()]
    layer = "personal" if note_type in {"habit", "preference", "style"} else "project"
    event = {
        "schema_version": "1.0",
        "event_id": new_id("evt"),
        "event_type": "manual_note",
        "timestamp": now_iso(),
        "session_id": session_id,
        "layer": layer,
        "project_id": None,
        "source": "manual",
        "payload": {
            "summary": summary.strip(),
            "note_type": note_type,
            "tags": tag_list
        }
    }
    append_jsonl(RAW_DIR / "manual_notes.jsonl", event)
    return event


def capture_ai_interaction(
    prompt_intent: str,
    markers: str,
    session_id: str,
    project_id: str | None = None
) -> dict:
    marker_list = [x.strip() for x in markers.split(",") if x.strip()]
    layer = "personal" if marker_list else "mixed"
    event = {
        "schema_version": "1.0",
        "event_id": new_id("evt"),
        "event_type": "ai_interaction",
        "timestamp": now_iso(),
        "session_id": session_id,
        "layer": layer,
        "project_id": project_id,
        "source": "claude_code",
        "payload": {
            "prompt_intent": prompt_intent,
            "preference_markers": marker_list
        }
    }
    append_jsonl(RAW_DIR / "ai_interactions.jsonl", event)
    return event


def _safe_str(s: str) -> str:
    """Remove surrogate characters that break JSON serialization on Windows."""
    return s.encode("utf-8", errors="replace").decode("utf-8")


def capture_from_hook_input(hook_input: dict, session_id: str) -> dict:
    """Capture an event from Claude Code hook stdin JSON."""
    prompt = hook_input.get("prompt", "")
    if not prompt:
        return {}
    markers = detect_markers(prompt)
    project_id = _safe_str(os.environ.get("CLAUDE_PROJECT_DIR", "global"))
    return capture_ai_interaction(
        prompt_intent=_safe_str(prompt[:120]),
        markers=",".join(markers),
        session_id=_safe_str(session_id),
        project_id=project_id
    )

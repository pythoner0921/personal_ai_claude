from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from .engine_io import append_jsonl, new_id, now_iso, read_yaml


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"
CONFIG_PATH = ROOT / "config.yaml"


def _load_taxonomy() -> dict[str, dict]:
    """Load taxonomy from config. Returns {key: {category, description, keywords}}."""
    cfg = read_yaml(CONFIG_PATH)
    return cfg.get("taxonomy", {})


def _build_marker_keywords() -> dict[str, list[str]]:
    """Build marker → keywords mapping from taxonomy config."""
    taxonomy = _load_taxonomy()
    markers: dict[str, list[str]] = {}
    for key, entry in taxonomy.items():
        if isinstance(entry, dict) and "keywords" in entry:
            markers[key] = entry["keywords"]
    return markers


# Legacy compatibility: also load old-style markers section if taxonomy is missing
def _get_marker_keywords() -> dict[str, list[str]]:
    markers = _build_marker_keywords()
    if markers:
        return markers
    # Fallback to legacy markers section
    cfg = read_yaml(CONFIG_PATH)
    return cfg.get("markers", {})


def detect_markers(prompt: str) -> list[str]:
    """Scan prompt text for preference keywords and return matching taxonomy keys."""
    text = prompt.lower()
    found: list[str] = []
    for marker, keywords in _get_marker_keywords().items():
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

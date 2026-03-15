"""Self-generated session tracking (CLAUDE_SESSION_ID is unavailable)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .engine_io import new_id, now_iso


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
SESSION_FILE = STATE / "current_session.json"


def get_or_create_session_id() -> str:
    """Return current session ID, or generate a new one.

    Called by SessionStart to create, and by other hooks to read.
    Falls back to CLAUDE_SESSION_ID env var if available.
    """
    env_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if env_id and env_id != "unknown":
        return env_id

    # Try reading the persisted session file
    try:
        if SESSION_FILE.exists():
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            sid = data.get("session_id", "")
            if sid:
                return sid
    except (json.JSONDecodeError, OSError):
        pass

    return "unknown"


def create_new_session() -> str:
    """Generate a new session ID and persist it. Called only by SessionStart."""
    sid = new_id("ses")
    STATE.mkdir(parents=True, exist_ok=True)
    data = {
        "session_id": sid,
        "started_at": now_iso(),
        "project_id": os.environ.get("CLAUDE_PROJECT_DIR", "global"),
    }
    SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return sid

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .engine_io import read_yaml, write_yaml, now_iso
from .task_classify import classify_task, task_affinity_bonus


ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "memory"

STABLE_PATH = MEM / "stable_preferences.yaml"
RECENT_PATH = MEM / "recent_tendencies.yaml"

# Decay: confidence weight halves roughly every 23 days (0.97^23 ≈ 0.50)
DECAY_BASE = 0.97


def _keyword_score(text: str, query: str) -> int:
    t = text.lower()
    q_tokens = [x for x in query.lower().split() if x]
    return sum(1 for tok in q_tokens if tok in t)


def _days_since(iso_timestamp: str) -> float:
    """Return days elapsed since the given ISO timestamp. Returns 0 on parse failure."""
    if not iso_timestamp:
        return 0.0
    try:
        then = dt.datetime.fromisoformat(iso_timestamp)
        now = dt.datetime.now(dt.timezone.utc).astimezone()
        delta = (now - then).total_seconds()
        return max(0.0, delta / 86400.0)
    except (ValueError, TypeError):
        return 0.0


def _decay_score(last_seen: str) -> float:
    """Compute time-decay multiplier: 0.97^days_since_last_seen."""
    days = _days_since(last_seen)
    return max(0.01, DECAY_BASE ** days)


def _scope_bonus(pref_scope: str, project_id: str | None) -> float:
    """Return bonus score if the preference scope matches the current project."""
    if not project_id or not pref_scope:
        return 0.0
    if pref_scope == "global":
        return 0.0
    # Project-scoped preference matching current project gets a boost
    if pref_scope.startswith("project:"):
        scope_project = pref_scope[len("project:"):]
        if scope_project and scope_project in project_id:
            return 0.2
    return 0.0


def _load_preferences() -> tuple[list[dict], list[dict], list[dict]]:
    """Load preferences, returning (all_prefs, stable_items, recent_items)."""
    stable_items = read_yaml(STABLE_PATH).get("items", [])
    recent_items = read_yaml(RECENT_PATH).get("items", [])
    by_id: dict[str, dict] = {}
    for x in stable_items:
        x2 = dict(x)
        x2["_priority"] = 3
        by_id[x2.get("id", f"stable_{len(by_id)}")] = x2
    for x in recent_items:
        x2 = dict(x)
        x2["_priority"] = 2
        pid = x2.get("id", f"recent_{len(by_id)}")
        if pid not in by_id:
            by_id[pid] = x2
    return list(by_id.values()), stable_items, recent_items


def _record_usage(selected_ids: set[str], stable_items: list[dict], recent_items: list[dict]) -> None:
    """Update last_used and use_count on preferences that were injected."""
    if not selected_ids:
        return
    now = now_iso()
    changed = False
    for items in (stable_items, recent_items):
        for item in items:
            if item.get("id") in selected_ids:
                item["last_used"] = now
                item["use_count"] = int(item.get("use_count", 0)) + 1
                changed = True
    if changed:
        try:
            write_yaml(STABLE_PATH, {"schema_version": "1.0", "items": stable_items})
            write_yaml(RECENT_PATH, {"schema_version": "1.0", "items": recent_items})
        except Exception:
            pass  # Usage tracking is best-effort


def build_injection_payload(query: str, budget_chars: int = 600, project_id: str | None = None) -> dict:
    prefs, stable_items, recent_items = _load_preferences()
    task_type = classify_task(query)

    for p in prefs:
        desc = p.get("description", "")
        relevance = _keyword_score(
            desc + " " + p.get("evidence_summary", ""), query
        )
        confidence = p.get("confidence_score", 0.0)
        decay = _decay_score(p.get("last_seen", ""))
        scope = _scope_bonus(p.get("scope", "global"), project_id)
        affinity = task_affinity_bonus(task_type, desc)
        priority = p.get("_priority", 1) * 3

        p["_decay"] = decay
        p["_task_type"] = task_type
        p["_affinity"] = affinity
        p["_score"] = priority + (confidence * decay) + relevance + scope + affinity

    ranked = sorted(
        prefs,
        key=lambda x: (x["_score"], x.get("confidence_score", 0.0)),
        reverse=True
    )

    lines = []
    selected_ids: set[str] = set()
    for p in ranked:
        if len(lines) >= 4:
            break
        line = f"- ({p.get('confidence_score', 0):.2f}) {p.get('description', '')}"
        if len("\n".join(lines + [line])) > budget_chars:
            break
        lines.append(line)
        selected_ids.add(p.get("id", ""))

    # Record usage on the selected preferences
    _record_usage(selected_ids, stable_items, recent_items)

    text = (
        "Personal Preferences\n"
        f"Project: {project_id or 'global'}\n"
        "Apply unless user overrides:\n"
        + ("\n".join(lines) if lines else "- (no stable preferences yet)")
    )

    payload = {
        "query": query,
        "project_id": project_id,
        "budget_chars": budget_chars,
        "selected_count": len(lines),
        "payload_text": text
    }
    return payload


def output_for_claude_hook(payload: dict, hook_event: str = "UserPromptSubmit") -> None:
    """Output JSON in Claude Code hook format to stdout."""
    result = {
        "hookSpecificOutput": {
            "hookEventName": hook_event,
            "additionalContext": payload["payload_text"]
        }
    }
    print(json.dumps(result, ensure_ascii=False))

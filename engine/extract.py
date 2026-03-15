from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .engine_io import new_id, now_iso, read_jsonl, write_jsonl


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
INF = ROOT / "inference"


def _signal_from_terminal(ev: dict) -> tuple[str, str] | None:
    shape = ev.get("payload", {}).get("command_shape", "")
    token_count = ev.get("payload", {}).get("token_count", 0)

    if shape.startswith("rg ") or shape.startswith("get-childitem") or shape.startswith("ls "):
        return ("execution", "starts_with_context_scan")
    if "apply_patch" in shape:
        return ("execution", "prefers_incremental_patch_updates")
    if token_count <= 3:
        return ("execution", "uses_compact_command_style")
    return None


_MARKER_TO_SIGNAL: dict[str, tuple[str, str]] = {
    # Communication
    "summary_first": ("communication", "prefers_summary_before_details"),
    "simplify": ("communication", "prefers_simplified_explanations"),
    "use_chinese": ("communication", "prefers_chinese_communication"),
    "use_tables": ("communication", "prefers_table_format_for_comparison"),
    "show_evidence": ("communication", "wants_evidence_with_specific_files"),
    # Execution
    "modular_changes": ("execution", "prefers_modular_changes_over_big_rewrites"),
    "check_before_change": ("execution", "prefers_read_before_modify"),
    "prefer_diagnosis": ("execution", "prefers_diagnosis_before_action"),
    # Decision
    "avoid_interruptions": ("decision", "dislikes_repeated_clarification_interruptions"),
    "wants_options": ("decision", "wants_options_before_deciding"),
    "prefers_direct_action": ("decision", "prefers_direct_action_over_discussion"),
    # Scope
    "no_over_engineering": ("scope", "dislikes_over_engineering"),
    "stay_focused": ("scope", "prefers_staying_focused_on_task"),
}


def _normalize_llm_pattern(pattern: str) -> tuple[str, str]:
    """Convert a free-text LLM pattern into a (category, signal_key) tuple."""
    p = pattern.lower().strip()
    # Try to categorize by keywords
    if any(w in p for w in ["chinese", "中文", "language", "table", "format", "verbose", "concise", "brief"]):
        cat = "communication"
    elif any(w in p for w in ["diagnos", "check", "read", "scan", "verify", "test"]):
        cat = "execution"
    elif any(w in p for w in ["option", "decide", "choose", "direct", "ask"]):
        cat = "decision"
    elif any(w in p for w in ["focus", "scope", "minimal", "over-engineer", "simple"]):
        cat = "scope"
    else:
        cat = "general"
    # Normalize key: replace spaces/special chars with underscores
    key = p.replace(" ", "_").replace("-", "_").replace("'", "")
    key = "".join(c for c in key if c.isalnum() or c == "_")[:60]
    return (cat, key)


def _signals_from_ai(ev: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    markers = ev.get("payload", {}).get("preference_markers", [])
    intent = ev.get("payload", {}).get("prompt_intent", "")
    is_llm = intent == "[llm_behavior_analysis]"

    for m in markers:
        if is_llm:
            # Free-text patterns from LLM analysis
            out.append(_normalize_llm_pattern(m))
        else:
            sig = _MARKER_TO_SIGNAL.get(m)
            if sig:
                out.append(sig)
    return out


def _signals_from_note(ev: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    note_type = ev.get("payload", {}).get("note_type", "")
    tags = set(ev.get("payload", {}).get("tags", []))
    if note_type == "preference" and "communication" in tags:
        out.append(("communication", "explicit_communication_preference_update"))
    if note_type == "habit":
        out.append(("emerging_change", "manual_habit_reflection"))
    return out


def build_habit_and_candidates() -> tuple[list[dict], list[dict]]:
    events = (
        read_jsonl(RAW / "episodic.jsonl")
        + read_jsonl(RAW / "ai_interactions.jsonl")
        + read_jsonl(RAW / "manual_notes.jsonl")
    )
    events = sorted(events, key=lambda x: x.get("timestamp", ""))

    habit_events: list[dict] = []
    signal_sources: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    signal_event_ids: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    signal_first_seen: dict[tuple[str, str], str] = {}
    signal_last_seen: dict[tuple[str, str], str] = {}
    context_counter: defaultdict[tuple[str, str], Counter] = defaultdict(Counter)

    for ev in events:
        signals: list[tuple[str, str]] = []
        etype = ev.get("event_type")
        if etype == "terminal_command":
            s = _signal_from_terminal(ev)
            if s:
                signals.append(s)
        elif etype == "ai_interaction":
            signals.extend(_signals_from_ai(ev))
        elif etype == "manual_note":
            signals.extend(_signals_from_note(ev))

        for cat, key in signals:
            he = {
                "schema_version": "1.0",
                "habit_event_id": new_id("habit"),
                "timestamp": ev.get("timestamp", now_iso()),
                "category": cat,
                "signal_key": key,
                "signal_value": True,
                "evidence_event_ids": [ev.get("event_id", "")],
                "context_scope": ev.get("project_id") or "global"
            }
            habit_events.append(he)
            sig = (cat, key)
            signal_sources[sig].add(ev.get("source", "unknown"))
            signal_event_ids[sig].append(ev.get("event_id", ""))
            context_counter[sig][ev.get("project_id") or "global"] += 1
            t = ev.get("timestamp", now_iso())
            signal_first_seen[sig] = min(signal_first_seen.get(sig, t), t)
            signal_last_seen[sig] = max(signal_last_seen.get(sig, t), t)

    candidates: list[dict] = []
    total_events = max(1, len(events))
    for (cat, key), eids in signal_event_ids.items():
        count = len(eids)
        ctx_counts = context_counter[(cat, key)]
        ctx_total = max(1, len(ctx_counts))
        cross_context_stability = min(1.0, ctx_total / 3.0)
        source_frequency = min(1.0, count / total_events)
        confidence = min(0.95, 0.45 * source_frequency + 0.55 * cross_context_stability + min(0.3, count * 0.03))
        # Determine dominant project for scope inference
        ctx = context_counter[(cat, key)]
        dominant_project = ctx.most_common(1)[0][0] if ctx else "global"
        candidates.append({
            "schema_version": "1.0",
            "candidate_id": f"cand_{cat}_{key}",
            "description": key.replace("_", " "),
            "category": cat,
            "status": "candidate_preference",
            "evidence_count": count,
            "source_frequency": round(source_frequency, 3),
            "cross_context_stability": round(cross_context_stability, 3),
            "confidence_score": round(confidence, 3),
            "first_seen": signal_first_seen[(cat, key)],
            "last_seen": signal_last_seen[(cat, key)],
            "evidence_summary": f"{count} supporting events from {len(signal_sources[(cat, key)])} source types",
            "dominant_project": dominant_project,
            "project_count": len(ctx),
        })

    return habit_events, candidates


def run() -> None:
    habit_events, candidates = build_habit_and_candidates()
    write_jsonl(INF / "habit_candidates.jsonl", habit_events)
    write_jsonl(INF / "preference_candidates.jsonl", candidates)

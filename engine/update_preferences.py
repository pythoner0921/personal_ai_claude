from __future__ import annotations

from pathlib import Path

from .engine_io import append_jsonl, now_iso, read_jsonl, read_yaml, write_yaml


ROOT = Path(__file__).resolve().parents[1]
INF = ROOT / "inference"
MEM = ROOT / "memory"

STABLE_PATH = MEM / "stable_preferences.yaml"
RECENT_PATH = MEM / "recent_tendencies.yaml"
DEPRECATED_PATH = MEM / "deprecated_preferences.yaml"
CHANGE_LOG = MEM / "change_log.jsonl"


PROMOTE_MIN_COUNT = 5
PROMOTE_MIN_CONF = 0.75
PROMOTE_MIN_STABILITY = 0.60
RECENT_MIN_COUNT = 2
RECENT_MIN_CONF = 0.50


def _index(items: list[dict]) -> dict[str, dict]:
    return {x["id"]: x for x in items if "id" in x}


def _infer_scope(candidate: dict) -> str:
    """Infer whether a preference is global or project-specific.

    If seen in 2+ projects (project_count >= 2), it's global.
    If all evidence comes from one project, mark as project-scoped.
    """
    project_count = candidate.get("project_count", 1)
    if project_count >= 2:
        return "global"
    dominant = candidate.get("dominant_project", "global")
    if dominant and dominant != "global":
        return f"project:{dominant}"
    return "global"


def run_update() -> dict[str, int]:
    candidates = read_jsonl(INF / "preference_candidates.jsonl")

    stable = read_yaml(STABLE_PATH)
    recent = read_yaml(RECENT_PATH)
    deprecated = read_yaml(DEPRECATED_PATH)

    stable_items = stable.get("items", [])
    recent_items = recent.get("items", [])
    dep_items = deprecated.get("items", [])

    stable_idx = _index(stable_items)
    recent_idx = _index(recent_items)

    promoted = 0
    recented = 0
    deprecated_count = 0
    updated = 0

    for c in candidates:
        pid = c["candidate_id"].replace("cand_", "pref_")
        # Determine scope from context distribution
        scope = _infer_scope(c)
        item = {
            "schema_version": "1.0",
            "id": pid,
            "description": c["description"],
            "category": c["category"],
            "evidence_summary": c.get("evidence_summary", ""),
            "confidence_score": c["confidence_score"],
            "first_seen": c["first_seen"],
            "last_seen": c["last_seen"],
            "status": "candidate_preference",
            "source_frequency": c["source_frequency"],
            "cross_context_stability": c["cross_context_stability"],
            "scope": scope,
            "last_used": "",
            "use_count": 0,
            "version": 1
        }

        if (
            c["evidence_count"] >= PROMOTE_MIN_COUNT
            and c["confidence_score"] >= PROMOTE_MIN_CONF
            and c["cross_context_stability"] >= PROMOTE_MIN_STABILITY
        ):
            if pid in recent_idx:
                recent_items.remove(recent_idx[pid])
                recent_idx.pop(pid, None)
                append_jsonl(CHANGE_LOG, {
                    "timestamp": now_iso(),
                    "change_type": "remove_recent_after_stable_promotion",
                    "preference_id": pid
                })
            if pid in stable_idx:
                current = stable_idx[pid]
                # Preserve usage-tracking fields that inject_context maintains
                saved_last_used = current.get("last_used", "")
                saved_use_count = current.get("use_count", 0)
                saved_scope = current.get("scope", "global")
                current.update(item)
                current["category"] = "stable_preference"
                current["status"] = "active"
                current["version"] = int(current.get("version", 1)) + 1
                current["last_used"] = saved_last_used
                current["use_count"] = saved_use_count
                current["scope"] = saved_scope if saved_scope != "global" else scope
                updated += 1
            else:
                item["category"] = "stable_preference"
                item["status"] = "active"
                stable_items.append(item)
                stable_idx[pid] = item
                promoted += 1
            append_jsonl(CHANGE_LOG, {
                "timestamp": now_iso(),
                "change_type": "promote_or_update_stable",
                "preference_id": pid
            })
        elif c["evidence_count"] >= RECENT_MIN_COUNT and c["confidence_score"] >= RECENT_MIN_CONF:
            if pid in recent_idx:
                current = recent_idx[pid]
                saved_last_used = current.get("last_used", "")
                saved_use_count = current.get("use_count", 0)
                saved_scope = current.get("scope", "global")
                current.update(item)
                current["category"] = "recent_tendency"
                current["status"] = "active"
                current["version"] = int(current.get("version", 1)) + 1
                current["last_used"] = saved_last_used
                current["use_count"] = saved_use_count
                current["scope"] = saved_scope if saved_scope != "global" else scope
                updated += 1
            else:
                item["category"] = "recent_tendency"
                item["status"] = "active"
                recent_items.append(item)
                recent_idx[pid] = item
                recented += 1
            append_jsonl(CHANGE_LOG, {
                "timestamp": now_iso(),
                "change_type": "upsert_recent_tendency",
                "preference_id": pid
            })

    still_active = {x.replace("cand_", "pref_") for x in [c["candidate_id"] for c in candidates]}
    for pref in list(stable_items):
        if pref["id"] not in still_active:
            pref["status"] = "deprecated"
            pref["category"] = "deprecated_preference"
            dep_items.append(pref)
            stable_items.remove(pref)
            deprecated_count += 1
            append_jsonl(CHANGE_LOG, {
                "timestamp": now_iso(),
                "change_type": "deprecate_stable_preference",
                "preference_id": pref["id"]
            })

    write_yaml(STABLE_PATH, {"schema_version": "1.0", "items": stable_items})
    write_yaml(RECENT_PATH, {"schema_version": "1.0", "items": recent_items})
    write_yaml(DEPRECATED_PATH, {"schema_version": "1.0", "items": dep_items})

    return {
        "promoted": promoted,
        "recentered": recented,
        "deprecated": deprecated_count,
        "updated": updated
    }

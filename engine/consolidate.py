"""Memory consolidation: synonym dedup, fuzzy merge, noise filtering, decay, lifecycle, and log rotation."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .engine_io import read_yaml, write_yaml, read_jsonl, write_jsonl, append_jsonl, now_iso
from .inject_context import _decay_score, _days_since


ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "memory"
INF = ROOT / "inference"

STABLE_PATH = MEM / "stable_preferences.yaml"
RECENT_PATH = MEM / "recent_tendencies.yaml"
ARCHIVE_PATH = MEM / "archive.yaml"
CHANGE_LOG = MEM / "change_log.jsonl"

# Lifecycle thresholds
ARCHIVE_CONF_THRESHOLD = 0.3
ARCHIVE_DAYS_THRESHOLD = 90

# ── Synonym groups: map variant descriptions → canonical form ──
SYNONYM_GROUPS: dict[str, list[str]] = {
    "prefers concise output": [
        "dislikes verbose output",
        "wants concise output",
        "prefers concise instructions",
        "prefers concise feedback",
        "prefers concise information",
        "prefers concise code",
        "prefers concise settings",
        "prefers concise updates",
        "prefers concise deliverables",
        "prefers concise documentation",
        "prefers concise changes",
        "prefers concise state definitions",
        "prefers concise error messages",
        "dislikes verbose documentation",
        "dislikes verbose code examples",
        "dislikes verbose command line",
        "dislikes verbose code comments",
        "dislikes redundant information",
        "prefers simplified explanations",
    ],
    "prefers summary before details": [
        "wants clear session summary",
        "wants clear evaluation summary",
        "prefers clear structure",
    ],
    "prefers modular changes over big rewrites": [
        "wants modular code organization",
    ],
}

# Build reverse lookup: variant → canonical
_VARIANT_TO_CANONICAL: dict[str, str] = {}
for canonical, variants in SYNONYM_GROUPS.items():
    for v in variants:
        _VARIANT_TO_CANONICAL[v] = canonical


# ── Noise filter: patterns that are task-specific, not preference-related ──
NOISE_KEYWORDS: list[str] = [
    "posture", "upright", "keypoint", "debounce", "monitoring",
    "bypass", "permission", "config", "json config",
    "surrogate", "session summary", "event logs",
    "activity insights", "status update", "verification steps",
    "classification rules", "presence intervals",
    "focused attention", "immediate assistance",
    "immediate effect", "action confirmation",
    "clear posture", "helper function",
    "distinction between states", "files are stored",
    "technical terms", "code examples",
    "numerical data", "numerical metrics",
]


# ── Fuzzy merge: keyword-overlap similarity for descriptions not in synonym groups ──
# Stopwords to ignore in similarity comparison
_STOPWORDS = {"prefers", "wants", "dislikes", "likes", "uses", "needs", "over", "for", "with", "and", "the", "a", "an", "in", "to", "of", "is", "are", "be"}

# Semantic equivalence groups: words that should be treated as the same token
_SEMANTIC_GROUPS: dict[str, list[str]] = {
    "concise": ["short", "compact", "brief", "terse", "minimal", "simplified"],
    "verbose": ["long", "detailed", "wordy", "lengthy"],
    "output": ["response", "responses", "explanations", "answers", "reply", "replies"],
    "summary": ["overview", "recap", "outline"],
    "modular": ["incremental", "stepwise", "step-by-step"],
    "rewrite": ["overhaul", "replacement", "rewrite"],
}

# Build reverse lookup: variant → canonical token
_TOKEN_CANONICAL: dict[str, str] = {}
for _canon_tok, _variants in _SEMANTIC_GROUPS.items():
    for _v in _variants:
        _TOKEN_CANONICAL[_v] = _canon_tok

FUZZY_MERGE_THRESHOLD = 0.6  # Jaccard similarity threshold for auto-merge


def _tokenize(text: str) -> set[str]:
    """Tokenize a description into meaningful keywords, normalizing synonyms."""
    tokens = set()
    for w in text.lower().split():
        if w in _STOPWORDS or len(w) <= 1:
            continue
        # Normalize to canonical token if it's a known synonym
        tokens.add(_TOKEN_CANONICAL.get(w, w))
    return tokens


def _jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two descriptions."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    intersection = ta & tb
    union = ta | tb
    return len(intersection) / len(union)


def _pick_canonical(a: dict, b: dict) -> tuple[dict, dict]:
    """Pick the canonical item (higher confidence/evidence) and the duplicate."""
    score_a = a.get("confidence_score", 0) + int(a.get("use_count", 0)) * 0.01
    score_b = b.get("confidence_score", 0) + int(b.get("use_count", 0)) * 0.01
    if score_a >= score_b:
        return a, b
    return b, a


def is_noise(description: str) -> bool:
    """Return True if the preference is task-specific noise, not a real preference."""
    d = description.lower()
    return any(kw in d for kw in NOISE_KEYWORDS)


def canonical_description(description: str) -> str:
    """Return the canonical form if this is a known synonym, else return as-is."""
    return _VARIANT_TO_CANONICAL.get(description, description)


def _absorb(existing: dict, item: dict) -> None:
    """Absorb item's data into existing (merge fields in-place)."""
    existing["confidence_score"] = max(
        existing.get("confidence_score", 0),
        item.get("confidence_score", 0),
    )
    existing["evidence_count"] = (
        existing.get("evidence_count", 0) + item.get("evidence_count", 0)
    )
    existing["cross_context_stability"] = max(
        existing.get("cross_context_stability", 0),
        item.get("cross_context_stability", 0),
    )
    fs_e = existing.get("first_seen", "")
    fs_i = item.get("first_seen", "")
    if fs_i and (not fs_e or fs_i < fs_e):
        existing["first_seen"] = fs_i
    ls_e = existing.get("last_seen", "")
    ls_i = item.get("last_seen", "")
    if ls_i and (not ls_e or ls_i > ls_e):
        existing["last_seen"] = ls_i
    lu_e = existing.get("last_used", "")
    lu_i = item.get("last_used", "")
    if lu_i and (not lu_e or lu_i > lu_e):
        existing["last_used"] = lu_i
    existing["use_count"] = (
        int(existing.get("use_count", 0)) + int(item.get("use_count", 0))
    )
    if item.get("scope", "global") != "global":
        existing["scope"] = item["scope"]
    existing["version"] = int(existing.get("version", 1)) + 1


def _merge_items(items: list[dict]) -> list[dict]:
    """Merge items with synonym descriptions into their canonical form."""
    by_canonical: dict[str, dict] = {}

    for item in items:
        desc = item.get("description", "")
        canon = canonical_description(desc)

        if canon in by_canonical:
            _absorb(by_canonical[canon], item)
        else:
            merged = dict(item)
            if canon != desc:
                merged["description"] = canon
                cat_prefix = merged.get("id", "").rsplit("_", 1)[0]
                if not cat_prefix:
                    cat_prefix = "pref_" + merged.get("category", "general")
                canon_key = canon.replace(" ", "_")
                merged["id"] = f"{cat_prefix}_{canon_key}"
            merged.setdefault("scope", "global")
            merged.setdefault("last_used", "")
            merged.setdefault("use_count", 0)
            by_canonical[canon] = merged

    return list(by_canonical.values())


def _fuzzy_merge(items: list[dict]) -> tuple[list[dict], int]:
    """Second pass: merge items that weren't caught by synonym groups but are semantically similar.

    Uses Jaccard keyword overlap. Returns (merged_items, merge_count).
    """
    if len(items) <= 1:
        return items, 0

    merged_count = 0
    absorbed: set[int] = set()  # indices absorbed into another item

    for i in range(len(items)):
        if i in absorbed:
            continue
        for j in range(i + 1, len(items)):
            if j in absorbed:
                continue
            desc_i = items[i].get("description", "")
            desc_j = items[j].get("description", "")
            sim = _jaccard_similarity(desc_i, desc_j)
            if sim >= FUZZY_MERGE_THRESHOLD:
                canonical, duplicate = _pick_canonical(items[i], items[j])
                _absorb(canonical, duplicate)
                absorbed.add(j if canonical is items[i] else i)
                merged_count += 1
                append_jsonl(CHANGE_LOG, {
                    "timestamp": now_iso(),
                    "change_type": "fuzzy_merge",
                    "kept": canonical.get("description", ""),
                    "absorbed": duplicate.get("description", ""),
                    "similarity": round(sim, 3),
                })

    result = [items[i] for i in range(len(items)) if i not in absorbed]
    return result, merged_count


def _filter_noise(items: list[dict]) -> list[dict]:
    """Remove items that are task-specific noise."""
    return [item for item in items if not is_noise(item.get("description", ""))]


def _should_archive(item: dict) -> bool:
    """Check if an item should be archived based on lifecycle rules."""
    conf = item.get("confidence_score", 0.0)
    if conf < ARCHIVE_CONF_THRESHOLD:
        return True
    days = _days_since(item.get("last_seen", ""))
    if days > ARCHIVE_DAYS_THRESHOLD:
        return True
    return False


def _run_archival(stable_items: list[dict], recent_items: list[dict]) -> tuple[list[dict], list[dict], int]:
    """Move items that meet archive criteria to archive.yaml. Returns updated lists + count."""
    archive_data = read_yaml(ARCHIVE_PATH)
    archive_items = archive_data.get("items", [])
    archive_ids = {a.get("id", "") for a in archive_items}

    archived_count = 0

    new_stable = []
    for item in stable_items:
        if _should_archive(item):
            if item.get("id", "") not in archive_ids:
                item["status"] = "archived"
                item["archived_at"] = now_iso()
                item["archived_from"] = "stable_preference"
                archive_items.append(item)
                archive_ids.add(item.get("id", ""))
                archived_count += 1
                append_jsonl(CHANGE_LOG, {
                    "timestamp": now_iso(),
                    "change_type": "archive",
                    "preference_id": item.get("id", ""),
                    "reason": f"conf={item.get('confidence_score', 0):.2f}, days={_days_since(item.get('last_seen', '')):.0f}",
                })
        else:
            new_stable.append(item)

    new_recent = []
    for item in recent_items:
        if _should_archive(item):
            if item.get("id", "") not in archive_ids:
                item["status"] = "archived"
                item["archived_at"] = now_iso()
                item["archived_from"] = "recent_tendency"
                archive_items.append(item)
                archive_ids.add(item.get("id", ""))
                archived_count += 1
                append_jsonl(CHANGE_LOG, {
                    "timestamp": now_iso(),
                    "change_type": "archive",
                    "preference_id": item.get("id", ""),
                    "reason": f"conf={item.get('confidence_score', 0):.2f}, days={_days_since(item.get('last_seen', '')):.0f}",
                })
        else:
            new_recent.append(item)

    if archived_count > 0:
        # Dedup archive by id (keep latest)
        seen: dict[str, dict] = {}
        for a in archive_items:
            aid = a.get("id", "")
            if aid in seen:
                # Keep the one with later archived_at
                if a.get("archived_at", "") > seen[aid].get("archived_at", ""):
                    seen[aid] = a
            else:
                seen[aid] = a
        archive_items = list(seen.values())
        write_yaml(ARCHIVE_PATH, {"schema_version": "1.0", "items": archive_items})

    return new_stable, new_recent, archived_count


def run_consolidation() -> dict[str, int]:
    """Run full consolidation: noise filter + synonym dedup + fuzzy merge + archival."""
    stable = read_yaml(STABLE_PATH)
    recent = read_yaml(RECENT_PATH)

    stable_items = stable.get("items", [])
    recent_items = recent.get("items", [])

    orig_stable = len(stable_items)
    orig_recent = len(recent_items)

    # 1. Filter noise
    stable_items = _filter_noise(stable_items)
    recent_items = _filter_noise(recent_items)

    # 2. Merge synonyms (exact match)
    stable_items = _merge_items(stable_items)
    recent_items = _merge_items(recent_items)

    # 3. Fuzzy merge (keyword overlap)
    stable_items, fuzzy_stable = _fuzzy_merge(stable_items)
    recent_items, fuzzy_recent = _fuzzy_merge(recent_items)

    # 4. Remove recent items that are already covered by stable
    stable_descs = {item.get("description", "") for item in stable_items}
    recent_items = [
        item for item in recent_items
        if item.get("description", "") not in stable_descs
    ]

    # 5. Compute decay_score for all items
    for item in stable_items + recent_items:
        item["decay_score"] = round(_decay_score(item.get("last_seen", "")), 3)
        item.setdefault("scope", "global")
        item.setdefault("last_used", "")
        item.setdefault("use_count", 0)

    # 6. Lifecycle archival (confidence < 0.3 or last_seen > 90 days)
    stable_items, recent_items, archived_count = _run_archival(stable_items, recent_items)

    # 7. Dedup deprecated_preferences.yaml (keep latest per id)
    try:
        dep_path = MEM / "deprecated_preferences.yaml"
        dep_data = read_yaml(dep_path)
        dep_items = dep_data.get("items", [])
        if dep_items:
            dep_seen: dict[str, dict] = {}
            for d in dep_items:
                did = d.get("id", "")
                if did in dep_seen:
                    if d.get("last_seen", "") > dep_seen[did].get("last_seen", ""):
                        dep_seen[did] = d
                else:
                    dep_seen[did] = d
            if len(dep_seen) < len(dep_items):
                write_yaml(dep_path, {"schema_version": "1.0", "items": list(dep_seen.values())})
    except Exception:
        pass  # Deprecated dedup is best-effort

    # 8. Write back
    write_yaml(STABLE_PATH, {"schema_version": "1.0", "items": stable_items})
    write_yaml(RECENT_PATH, {"schema_version": "1.0", "items": recent_items})

    noise_removed = (orig_stable + orig_recent) - (len(stable_items) + len(recent_items)) - archived_count
    total_merged = fuzzy_stable + fuzzy_recent

    # Log
    append_jsonl(CHANGE_LOG, {
        "timestamp": now_iso(),
        "change_type": "consolidation",
        "noise_removed": max(0, noise_removed),
        "synonyms_merged": max(0, total_merged),
        "archived": archived_count,
        "stable_count": len(stable_items),
        "recent_count": len(recent_items),
    })

    return {
        "noise_removed": max(0, noise_removed),
        "synonyms_merged": max(0, total_merged),
        "fuzzy_merged": fuzzy_stable + fuzzy_recent,
        "archived": archived_count,
        "stable_after": len(stable_items),
        "recent_after": len(recent_items),
    }


def rotate_change_log(max_lines: int = 200) -> int:
    """Keep only the most recent max_lines entries in change_log."""
    rows = read_jsonl(CHANGE_LOG)
    if len(rows) <= max_lines:
        return 0
    trimmed = len(rows) - max_lines
    write_jsonl(CHANGE_LOG, rows[-max_lines:])
    return trimmed

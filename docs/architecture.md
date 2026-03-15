# Architecture

## Overview

The memory engine operates as a pipeline attached to Claude Code hooks. It observes user–assistant interactions, extracts behavioral preferences, and reinjects them as context in future sessions.

```
User Prompt → [capture] → [extract] → [update] → [consolidate] → [inject]
                                                        ↓
                                                   [reflect]
                                                        ↓
                                                   [archive]
```

## Hook Pipeline

| Hook | Trigger | Actions |
|------|---------|---------|
| `SessionStart` | New conversation | Create session ID, generate reflections, inject preferences |
| `UserPromptSubmit` | Each user message | Capture keywords, inject ranked preferences |
| `Stop` | Assistant response | Capture patterns, LLM analysis, extract → update → consolidate → reflect → health check |

All hooks use try/catch fail-safe: they never block Claude even if errors occur.

## Memory Lifecycle

```
candidate → recent → stable → archived
              ↑                    ↑
          evidence ≥ 2         conf < 0.3
          conf ≥ 0.50          OR last_seen > 90d
              ↓
          evidence ≥ 5
          conf ≥ 0.75
          stability ≥ 0.60
              ↓
           stable
```

| State | Criteria | Storage |
|-------|----------|---------|
| candidate | Newly extracted, evidence < 2 | `inference/preference_candidates.jsonl` |
| recent | evidence ≥ 2, confidence ≥ 0.50 | `memory/recent_tendencies.yaml` |
| stable | evidence ≥ 5, confidence ≥ 0.75, stability ≥ 0.60 | `memory/stable_preferences.yaml` |
| archived | confidence < 0.3 OR last_seen > 90 days | `memory/archive.yaml` |

Data is never deleted — archived preferences are preserved in `archive.yaml`.

## Ranking Formula

Each preference gets a composite score for injection priority:

```
score = (priority × 3) + (confidence × decay) + relevance + scope_bonus + affinity_bonus
```

| Component | Description |
|-----------|-------------|
| priority | stable=3, recent=2 → multiplied by 3 |
| confidence | 0.0–0.95, from evidence frequency + cross-context stability |
| decay | `0.97 ^ days_since_last_seen` (halves every ~23 days) |
| relevance | Keyword overlap between preference description and current query |
| scope_bonus | +0.2 if preference scope matches current project |
| affinity_bonus | +0.2 per task-type affinity match (max +0.4) |

Top 4 preferences (by score, within 600-char budget) are injected.

## Confidence Formula

```
confidence = min(0.95, 0.45 × source_frequency + 0.55 × cross_context_stability + min(0.3, count × 0.03))
```

## Deduplication

Three layers:

1. **Synonym groups** — Exact-match mapping of known variants to canonical forms (e.g., "dislikes verbose output" → "prefers concise output")
2. **Fuzzy merge** — Jaccard similarity on normalized tokens. Semantic groups normalize synonyms (short→concise, responses→output, incremental→modular). Threshold: 0.6
3. **Noise filter** — Keyword blocklist removes task-specific patterns (e.g., "posture", "keypoint")

## Task Classification

Rule-based classifier with 7 types: debugging, coding, architecture, explanation, configuration, documentation, review.

Each type has affinity keywords. When a preference description matches an affinity keyword for the current task type, it gets a +0.2 bonus (max +0.4).

## Reflections

Higher-level summaries synthesized from stable + recent preferences:

- Grouped by theme (communication_style, code_approach, general)
- 1 sentence per theme
- Regenerated every 50 captured events or at session start
- Injected before individual preferences in SessionStart

## Storage Format

| File | Format | Purpose |
|------|--------|---------|
| `memory/stable_preferences.yaml` | YAML | Active stable preferences |
| `memory/recent_tendencies.yaml` | YAML | Active recent preferences |
| `memory/archive.yaml` | YAML | Archived preferences |
| `memory/reflections.yaml` | YAML | Synthesized summaries |
| `memory/change_log.jsonl` | JSONL | Audit trail (bounded to 200 lines) |
| `state/evidence.jsonl` | JSONL | Pipeline event log |
| `raw/ai_interactions.jsonl` | JSONL | Raw captured events |
| `inference/preference_candidates.jsonl` | JSONL | Extracted candidates |

## Dashboard

`tools/memory_dashboard.py` generates `memory/dashboard.html` — a self-contained HTML file with:
- Stat cards (stable/recent/archived/deprecated counts, avg confidence, total uses)
- Reflection summaries
- Sortable preference table (confidence bars, decay bars, usage counts)

## Export / Import

- `export_memory(path)` bundles all YAML files into a versioned JSON
- `import_memory(path)` restores from JSON, backing up existing files first
- Export format version: `1.0`

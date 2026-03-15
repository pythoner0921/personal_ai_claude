# Personal AI Memory Engine

**A persistent memory system for Claude Code that learns how you work and adapts every response to your preferences.**

![Demo](docs/assets/demo.gif)

## What It Does

The memory engine observes your interactions with Claude, extracts behavioral preferences, and reinjects them as context — automatically, every session. No configuration, no prompting, no reminders. Claude just remembers.

**Core capabilities:**

- **Preference learning** — Detects patterns like "prefers concise output" or "wants summary before details" from natural conversation
- **Memory lifecycle** — Preferences evolve through `candidate → recent → stable → archived` with confidence scoring and time decay
- **Context-aware ranking** — A task classifier boosts relevant preferences per prompt (debugging → concise + evidence, architecture → summary + tables)
- **Reflection synthesis** — Generates higher-level user profiles from accumulated preferences ("User prefers concise, summary-first, structured responses")
- **Self-maintaining** — Deduplication, noise filtering, fuzzy merge, and health monitoring keep the memory clean without manual intervention

**Example:**

You say _"keep it concise and start with a summary"_ once. From then on, every Claude session in this project opens with:

```
Personal Preferences
- (0.95) prefers summary before details
- (0.94) prefers table format for comparison
- (0.78) prefers concise output
```

No explicit memory commands needed. The system captures, learns, ranks, and injects — all through Claude Code hooks running in the background.

## Architecture

![Architecture](docs/assets/architecture.svg)

```
User Prompt → Capture → Extract → Update → Consolidate → Inject
                                                 ↓
                                            Reflect + Archive
```

The engine runs as three Claude Code hooks:

| Hook | Trigger | Actions |
|------|---------|---------|
| `SessionStart` | New conversation | Create session, generate reflections, inject preferences |
| `UserPromptSubmit` | Each user message | Capture keywords, inject ranked preferences |
| `Stop` | Assistant response | Extract patterns, consolidate, reflect, health check |

See [docs/architecture.md](docs/architecture.md) for the full system design.

## Quick Start

The engine runs automatically via Claude Code hooks. No manual setup needed beyond placing the hooks in your Claude Code configuration.

### CLI

```bash
python cli.py memory health          # Memory health report
python cli.py memory list            # List active preferences
python cli.py memory search concise  # Search by keyword
python cli.py memory reflect         # Generate reflections
python cli.py memory consolidate     # Run dedup + archival
python cli.py memory dashboard       # Generate HTML dashboard
python cli.py memory export out.json # Export memory state
python cli.py memory import out.json # Import from backup
```

### API

```python
from engine.api import get_active_memories, search_memories, get_memory_health_text

memories = get_active_memories()
results = search_memories("concise")
print(get_memory_health_text())
```

## Key Internals

### Ranking Formula

```
score = priority × 3 + confidence × decay + relevance + scope + affinity
```

| Component | Description |
|-----------|-------------|
| priority | stable=3, recent=2 (× 3) |
| confidence | 0.0–0.95, from evidence frequency + cross-context stability |
| decay | `0.97 ^ days` — halves every ~23 days |
| relevance | Keyword overlap with current query |
| scope | +0.2 if preference matches current project |
| affinity | +0.2 per task-type match (max +0.4) |

### Memory Lifecycle

```
candidate → recent → stable → archived
  (new)    (evidence≥2)  (evidence≥5,   (confidence<0.3
                          conf≥0.75)     or >90 days)
```

### Deduplication

Three layers: synonym groups (exact match), fuzzy merge (Jaccard similarity with semantic token normalization), and noise filtering (keyword blocklist for task-specific patterns).

## Project Structure

```
engine/          Core modules
  api.py              Public API surface
  inject_context.py   Ranking + injection
  consolidate.py      Dedup + merge + archival
  reflect.py          Reflection synthesis
  memory_health.py    Health monitoring
  task_classify.py    Context-aware retrieval
  extract.py          Preference extraction
  update_preferences.py  Lifecycle promotion
  capture.py          Event capture
  session.py          Session tracking
  llm_analyze.py      Local LLM analysis (Ollama)
  engine_io.py        YAML/JSONL I/O

hooks/           Claude Code hooks
  on_session_start.py  Inject preferences + reflections
  on_prompt_submit.py  Capture + inject per prompt
  on_stop.py           Extract + consolidate + reflect + health

tools/           Utilities
  memory_dashboard.py  HTML dashboard generator
  export_memory.py     Standalone export script
  import_memory.py     Standalone import script

tests/           Test suite (39 tests)
  test_lifecycle.py    Archival + state machine
  test_ranking.py      Decay, scope, affinity, ordering
  test_merge.py        Synonym, fuzzy, noise, field preservation

memory/          YAML preference storage
state/           Session + evidence logs
raw/             Raw interaction events
inference/       Extracted candidates
```

## Vision

Most AI tools treat every conversation as a blank slate. This project is a step toward AI that genuinely learns from working with you — not through fine-tuning or cloud sync, but through a lightweight, local, transparent memory layer that you own and control.

## Requirements

- Python 3.10+
- PyYAML
- pytest (for tests)
- Optional: Ollama with qwen2.5:3b (for LLM-based behavior analysis)

## License

MIT

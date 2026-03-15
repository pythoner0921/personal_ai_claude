"""Generate a self-contained HTML dashboard for the memory system."""
from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.engine_io import read_yaml

ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "memory"
OUT = MEM / "dashboard.html"


def _esc(s: str) -> str:
    return html.escape(str(s))


def _pref_rows(items: list[dict], category: str) -> str:
    rows = []
    for item in sorted(items, key=lambda x: x.get("confidence_score", 0), reverse=True):
        conf = item.get("confidence_score", 0)
        decay = item.get("decay_score", 1.0)
        use = int(item.get("use_count", 0))
        scope = item.get("scope", "global")
        last_seen = item.get("last_seen", "")[:10]
        last_used = item.get("last_used", "")[:10] or "—"
        desc = _esc(item.get("description", ""))
        pid = _esc(item.get("id", ""))
        conf_bar = f'<div class="bar" style="width:{conf*100:.0f}%"></div>'
        decay_bar = f'<div class="bar decay" style="width:{decay*100:.0f}%"></div>'
        rows.append(
            f"<tr>"
            f"<td>{_esc(category)}</td>"
            f"<td title=\"{pid}\">{desc}</td>"
            f"<td><div class='bar-wrap'>{conf_bar}<span>{conf:.2f}</span></div></td>"
            f"<td><div class='bar-wrap'>{decay_bar}<span>{decay:.3f}</span></div></td>"
            f"<td class='num'>{use}</td>"
            f"<td>{_esc(scope)}</td>"
            f"<td>{last_seen}</td>"
            f"<td>{last_used}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _reflection_section(reflections: dict) -> str:
    summaries = reflections.get("summaries", [])
    if not summaries:
        return "<p>No reflections generated yet.</p>"
    generated = reflections.get("generated_at", "")[:19]
    lines = [f"<p class='meta'>Generated: {_esc(generated)}</p>", "<ul>"]
    for s in summaries:
        lines.append(f"<li><strong>{_esc(s.get('theme', ''))}</strong>: {_esc(s.get('summary', ''))}</li>")
    lines.append("</ul>")
    return "\n".join(lines)


def _stats_cards(stable: list, recent: list, archive: list, deprecated: list) -> str:
    all_active = stable + recent
    confs = [i.get("confidence_score", 0) for i in all_active]
    avg_conf = sum(confs) / len(confs) if confs else 0
    total_use = sum(int(i.get("use_count", 0)) for i in all_active)
    return f"""
    <div class="cards">
      <div class="card"><div class="card-num">{len(stable)}</div><div class="card-label">Stable</div></div>
      <div class="card"><div class="card-num">{len(recent)}</div><div class="card-label">Recent</div></div>
      <div class="card"><div class="card-num">{len(archive)}</div><div class="card-label">Archived</div></div>
      <div class="card"><div class="card-num">{len(deprecated)}</div><div class="card-label">Deprecated</div></div>
      <div class="card"><div class="card-num">{avg_conf:.0%}</div><div class="card-label">Avg Confidence</div></div>
      <div class="card"><div class="card-num">{total_use}</div><div class="card-label">Total Uses</div></div>
    </div>"""


def generate_dashboard() -> Path:
    stable = read_yaml(MEM / "stable_preferences.yaml").get("items", [])
    recent = read_yaml(MEM / "recent_tendencies.yaml").get("items", [])
    archive = read_yaml(MEM / "archive.yaml").get("items", [])
    deprecated = read_yaml(MEM / "deprecated_preferences.yaml").get("items", [])
    reflections = read_yaml(MEM / "reflections.yaml")

    pref_rows = _pref_rows(stable, "stable") + _pref_rows(recent, "recent") + _pref_rows(archive, "archived")

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Memory Dashboard</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background:#f5f5f5; color:#222; padding:24px; }}
  h1 {{ font-size:1.5rem; margin-bottom:8px; }}
  h2 {{ font-size:1.1rem; margin:20px 0 8px; border-bottom:2px solid #ddd; padding-bottom:4px; }}
  .meta {{ color:#666; font-size:.85rem; margin-bottom:8px; }}
  .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin:12px 0; }}
  .card {{ background:#fff; border-radius:8px; padding:16px 20px; min-width:110px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,.1); }}
  .card-num {{ font-size:1.6rem; font-weight:700; color:#2563eb; }}
  .card-label {{ font-size:.75rem; color:#666; margin-top:2px; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.1); }}
  th {{ background:#f0f0f0; text-align:left; padding:8px 10px; font-size:.8rem; cursor:pointer; user-select:none; }}
  th:hover {{ background:#e0e0e0; }}
  td {{ padding:6px 10px; border-top:1px solid #eee; font-size:.85rem; }}
  .num {{ text-align:center; }}
  .bar-wrap {{ position:relative; width:80px; height:18px; background:#eee; border-radius:3px; overflow:hidden; }}
  .bar {{ position:absolute; top:0; left:0; height:100%; background:#60a5fa; border-radius:3px; }}
  .bar.decay {{ background:#34d399; }}
  .bar-wrap span {{ position:relative; z-index:1; font-size:.75rem; line-height:18px; padding-left:4px; }}
  ul {{ padding-left:20px; }}
  li {{ margin:4px 0; font-size:.9rem; }}
</style>
</head>
<body>
<h1>Memory System Dashboard</h1>
<p class="meta">Generated by tools/memory_dashboard.py</p>

{_stats_cards(stable, recent, archive, deprecated)}

<h2>Reflections</h2>
{_reflection_section(reflections)}

<h2>All Preferences</h2>
<table id="prefs">
<thead>
<tr>
  <th onclick="sortTable(0)">Category</th>
  <th onclick="sortTable(1)">Description</th>
  <th onclick="sortTable(2)">Confidence</th>
  <th onclick="sortTable(3)">Decay</th>
  <th onclick="sortTable(4)">Uses</th>
  <th onclick="sortTable(5)">Scope</th>
  <th onclick="sortTable(6)">Last Seen</th>
  <th onclick="sortTable(7)">Last Used</th>
</tr>
</thead>
<tbody>
{pref_rows}
</tbody>
</table>

<script>
let sortDir = {{}};
function sortTable(col) {{
  const tb = document.querySelector('#prefs tbody');
  const rows = Array.from(tb.rows);
  sortDir[col] = !sortDir[col];
  rows.sort((a, b) => {{
    let va = a.cells[col].textContent.trim();
    let vb = b.cells[col].textContent.trim();
    let na = parseFloat(va), nb = parseFloat(vb);
    if (!isNaN(na) && !isNaN(nb)) return sortDir[col] ? na - nb : nb - na;
    return sortDir[col] ? va.localeCompare(vb) : vb.localeCompare(va);
  }});
  rows.forEach(r => tb.appendChild(r));
}}
</script>
</body>
</html>"""

    OUT.write_text(page, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    path = generate_dashboard()
    print(f"Dashboard written to {path}")

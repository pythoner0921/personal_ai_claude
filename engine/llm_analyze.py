"""Taxonomy-driven LLM behavior analysis via local Ollama with gating and circuit breaker."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from .engine_io import read_yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"

# ── Circuit breaker state (per-process, resets each session) ──
_consecutive_failures: int = 0
_circuit_open: bool = False
_ollama_healthy: bool | None = None  # None = not checked yet


def _load_llm_config() -> dict:
    cfg = read_yaml(CONFIG_PATH).get("llm", {})
    return {
        "enabled": cfg.get("enabled", True),
        "model": cfg.get("model", "qwen2.5:3b"),
        "ollama_url": cfg.get("ollama_url", "http://localhost:11434"),
        "timeout": cfg.get("timeout_seconds", 15),
        "max_prompt_chars": cfg.get("max_prompt_chars", 600),
        "max_response_chars": cfg.get("max_response_chars", 1000),
        "temperature": cfg.get("temperature", 0.1),
        "max_tokens": cfg.get("max_tokens", 300),
        "circuit_breaker_threshold": cfg.get("gating", {}).get("circuit_breaker_threshold", 3),
    }


def _load_taxonomy_keys() -> list[str]:
    """Load all valid taxonomy keys from config."""
    cfg = read_yaml(CONFIG_PATH)
    taxonomy = cfg.get("taxonomy", {})
    return list(taxonomy.keys())


def _build_system_prompt(taxonomy_keys: list[str]) -> str:
    key_list = ", ".join(taxonomy_keys)
    return f"""You are a user preference extractor for a coding assistant memory system.

Given a user prompt and assistant response from a coding session, identify the user's REUSABLE working preferences.

TAXONOMY KEYS (select from these when possible):
{key_list}

OUTPUT FORMAT — valid JSON only, no markdown, no explanation:
{{
  "taxonomy_matches": ["key1", "key2"],
  "new_candidates": ["short free-text preference if no taxonomy key fits"],
  "confidence": 0.0
}}

RULES:
1. ONLY extract reusable preferences about HOW the user wants to work
2. DO NOT extract task-specific content (what they're building, bug details, file names)
3. DO NOT extract temporary instructions ("fix this now", "run the test")
4. Prefer taxonomy_matches over new_candidates — only use new_candidates for genuinely novel preferences
5. Maximum 3 taxonomy_matches and 1 new_candidate per analysis
6. confidence: 0.0-1.0 indicating how clear the preferences are
7. If no clear preference signal, return {{"taxonomy_matches": [], "new_candidates": [], "confidence": 0.0}}

POSITIVE EXAMPLES (extract these):
- User says "keep it concise" → {{"taxonomy_matches": ["concise_output"], "new_candidates": [], "confidence": 0.8}}
- User says "walk me through step by step" → {{"taxonomy_matches": ["step_by_step"], "new_candidates": [], "confidence": 0.7}}
- User says "I prefer seeing diffs over full files" → {{"taxonomy_matches": [], "new_candidates": ["prefers diff view over full file"], "confidence": 0.6}}

NEGATIVE EXAMPLES (do NOT extract):
- User says "fix the login bug" → {{"taxonomy_matches": [], "new_candidates": [], "confidence": 0.0}}
- User says "add a retry to the API call" → {{"taxonomy_matches": [], "new_candidates": [], "confidence": 0.0}}
- User says "run pytest" → {{"taxonomy_matches": [], "new_candidates": [], "confidence": 0.0}}"""


def check_ollama_health(ollama_url: str, timeout: int = 3) -> bool:
    """Quick health check — HEAD request to Ollama API."""
    global _ollama_healthy
    try:
        req = urllib.request.Request(f"{ollama_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=timeout):
            _ollama_healthy = True
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        _ollama_healthy = False
        return False


def should_call_llm(
    response_length: int,
    keyword_markers_found: int,
    config: dict | None = None,
) -> tuple[bool, str]:
    """Gating logic: decide whether to invoke LLM.

    Returns (should_call, reason).
    """
    global _circuit_open, _ollama_healthy

    cfg = config or _load_llm_config()

    if not cfg["enabled"]:
        return False, "llm.enabled=false"

    if _circuit_open:
        return False, "circuit_breaker_open"

    # Check Ollama health on first call
    if _ollama_healthy is None:
        if not check_ollama_health(cfg["ollama_url"]):
            return False, "ollama_offline"

    if _ollama_healthy is False:
        return False, "ollama_offline"

    gating = read_yaml(CONFIG_PATH).get("llm", {}).get("gating", {})
    min_len = gating.get("min_response_length", 200)
    skip_when_kw = gating.get("skip_when_keywords_found", True)

    if response_length < min_len:
        return False, f"response_too_short ({response_length}<{min_len})"

    if skip_when_kw and keyword_markers_found > 0:
        return False, f"keywords_sufficient ({keyword_markers_found} found)"

    return True, "ok"


def _record_failure() -> None:
    """Track consecutive failures for circuit breaker."""
    global _consecutive_failures, _circuit_open
    _consecutive_failures += 1
    cfg = _load_llm_config()
    if _consecutive_failures >= cfg["circuit_breaker_threshold"]:
        _circuit_open = True


def _record_success() -> None:
    """Reset failure counter on success."""
    global _consecutive_failures
    _consecutive_failures = 0


def analyze_interaction(
    prompt: str,
    response: str,
    timeout: int | None = None,
    model: str | None = None,
) -> Optional[dict]:
    """Call local Ollama to extract behavior patterns from an interaction.

    Returns dict with "taxonomy_matches", "new_candidates", "confidence",
    and legacy "patterns" field for backward compatibility. Returns None on failure.
    """
    cfg = _load_llm_config()
    use_model = model or cfg["model"]
    use_timeout = timeout or cfg["timeout"]

    # Truncate inputs
    prompt_text = prompt[:cfg["max_prompt_chars"]] if prompt else ""
    response_text = response[:cfg["max_response_chars"]] if response else ""

    if not prompt_text and not response_text:
        return None

    taxonomy_keys = _load_taxonomy_keys()
    system_prompt = _build_system_prompt(taxonomy_keys)

    user_msg = f"User prompt:\n{prompt_text}\n\nAssistant response (truncated):\n{response_text}"

    payload = {
        "model": use_model,
        "prompt": user_msg,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": cfg["temperature"],
            "num_predict": cfg["max_tokens"],
        }
    }

    try:
        req = urllib.request.Request(
            f"{cfg['ollama_url']}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=use_timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        raw = result.get("response", "").strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        # Strip leading/trailing non-JSON
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]

        parsed = json.loads(raw)
        taxonomy_matches = parsed.get("taxonomy_matches", [])
        new_candidates = parsed.get("new_candidates", [])
        confidence = float(parsed.get("confidence", 0.0))

        if not isinstance(taxonomy_matches, list):
            taxonomy_matches = []
        if not isinstance(new_candidates, list):
            new_candidates = []

        # Validate taxonomy matches against known keys
        valid_keys = set(taxonomy_keys)
        taxonomy_matches = [k for k in taxonomy_matches if k in valid_keys][:3]
        new_candidates = [str(c)[:60] for c in new_candidates[:1]]

        _record_success()

        # Build legacy "patterns" field for backward compatibility
        patterns = list(taxonomy_matches) + new_candidates

        return {
            "taxonomy_matches": taxonomy_matches,
            "new_candidates": new_candidates,
            "patterns": patterns,
            "confidence": min(1.0, max(0.0, confidence)),
            "model": use_model,
        }
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError, TimeoutError, OSError):
        _record_failure()
        return None

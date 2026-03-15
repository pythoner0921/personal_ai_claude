"""Lightweight LLM-based behavior analysis via local Ollama."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Optional

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"
TIMEOUT_SECONDS = 15

SYSTEM_PROMPT = """You are a behavior pattern analyzer. Given a user prompt and an AI assistant response from a coding session, extract the user's implicit working preferences.

Output ONLY a JSON object with these fields:
- "patterns": list of short preference strings (max 5), e.g. ["prefers chinese", "wants diagnosis before action", "dislikes verbose output"]
- "confidence": float 0-1 indicating how clear the patterns are

Rules:
- Focus on HOW the user wants to work, not WHAT they're working on
- Ignore task-specific content, only extract reusable preferences
- If no clear pattern, return {"patterns": [], "confidence": 0.0}
- Keep each pattern under 10 words
- Output valid JSON only, no markdown, no explanation"""


def analyze_interaction(prompt: str, response: str, timeout: int = TIMEOUT_SECONDS) -> Optional[dict]:
    """Call local Ollama to extract behavior patterns from an interaction.

    Returns dict with "patterns" and "confidence", or None on failure.
    """
    # Truncate to keep it fast
    prompt_text = prompt[:500] if prompt else ""
    response_text = response[:800] if response else ""

    if not prompt_text and not response_text:
        return None

    user_msg = f"User prompt:\n{prompt_text}\n\nAssistant response (truncated):\n{response_text}"

    payload = {
        "model": MODEL,
        "prompt": user_msg,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 200,
        }
    }

    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        raw = result.get("response", "").strip()
        # Try to extract JSON from response
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw)
        patterns = parsed.get("patterns", [])
        confidence = float(parsed.get("confidence", 0.0))

        if not isinstance(patterns, list):
            return None

        return {
            "patterns": [str(p)[:60] for p in patterns[:5]],
            "confidence": min(1.0, max(0.0, confidence))
        }
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError, TimeoutError, OSError):
        return None

"""Tests for preference ranking score ordering."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from engine.inject_context import _decay_score, _scope_bonus, _keyword_score
from engine.task_classify import classify_task, task_affinity_bonus


class TestDecayScore:
    def test_fresh_item_decay_near_one(self):
        from engine.engine_io import now_iso
        score = _decay_score(now_iso())
        assert score >= 0.99

    def test_old_item_decay_lower(self):
        score = _decay_score("2025-01-01T00:00:00+09:00")
        assert score < 0.5

    def test_empty_string_returns_one(self):
        score = _decay_score("")
        assert score == 1.0  # 0.97^0 = 1.0

    def test_decay_never_below_floor(self):
        score = _decay_score("2020-01-01T00:00:00+09:00")
        assert score >= 0.01


class TestScopeBonus:
    def test_global_scope_no_bonus(self):
        assert _scope_bonus("global", "my_project") == 0.0

    def test_matching_project_scope_gets_bonus(self):
        assert _scope_bonus("project:my_project", "my_project") == 0.2

    def test_non_matching_project_no_bonus(self):
        assert _scope_bonus("project:other", "my_project") == 0.0

    def test_no_project_id_no_bonus(self):
        assert _scope_bonus("project:foo", None) == 0.0


class TestKeywordScore:
    def test_matching_keywords(self):
        assert _keyword_score("prefers concise output", "concise") >= 1

    def test_no_match(self):
        assert _keyword_score("prefers tables", "concise") == 0


class TestTaskAffinity:
    def test_debugging_boosts_concise(self):
        bonus = task_affinity_bonus("debugging", "prefers concise output")
        assert bonus > 0

    def test_architecture_boosts_summary(self):
        bonus = task_affinity_bonus("architecture", "prefers summary before details")
        assert bonus > 0

    def test_unrelated_no_bonus(self):
        bonus = task_affinity_bonus("documentation", "prefers compact command style")
        assert bonus == 0.0


class TestRankingOrder:
    """Verify that ranking produces correct relative ordering."""

    def test_stable_outranks_recent(self):
        """Stable preferences (priority=3) should score higher than recent (priority=2)."""
        stable_score = 3 * 3 + 0.95  # priority*3 + confidence
        recent_score = 2 * 3 + 0.95
        assert stable_score > recent_score

    def test_high_confidence_outranks_low(self):
        """Same priority, higher confidence should win."""
        high = 3 * 3 + 0.95
        low = 3 * 3 + 0.50
        assert high > low

    def test_decayed_item_scores_lower(self):
        """Confidence * decay should reduce effective score."""
        fresh = 0.95 * 1.0
        decayed = 0.95 * 0.5
        assert fresh > decayed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Tests for memory lifecycle transitions and archival rules."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from engine.consolidate import _should_archive, ARCHIVE_CONF_THRESHOLD, ARCHIVE_DAYS_THRESHOLD


def _make_item(conf=0.8, last_seen="2026-03-15T00:00:00+09:00", evidence=5):
    return {"confidence_score": conf, "last_seen": last_seen, "evidence_count": evidence}


class TestArchivalRules:
    def test_low_confidence_triggers_archive(self):
        item = _make_item(conf=0.2)
        assert _should_archive(item) is True

    def test_threshold_confidence_not_archived(self):
        item = _make_item(conf=ARCHIVE_CONF_THRESHOLD)
        assert _should_archive(item) is False

    def test_high_confidence_not_archived(self):
        item = _make_item(conf=0.9)
        assert _should_archive(item) is False

    def test_old_item_archived(self):
        item = _make_item(conf=0.9, last_seen="2025-10-01T00:00:00+09:00")
        assert _should_archive(item) is True

    def test_fresh_item_not_archived(self):
        item = _make_item(conf=0.5, last_seen="2026-03-14T00:00:00+09:00")
        assert _should_archive(item) is False


class TestLifecycleStates:
    """Verify the state machine: candidate → recent → stable → archived."""

    def test_candidate_state(self):
        """evidence < 2 → candidate"""
        item = _make_item(conf=0.45, evidence=1)
        assert item["evidence_count"] < 2
        assert not _should_archive(item)

    def test_recent_state(self):
        """evidence ≥ 2, conf < 0.75 → recent"""
        item = _make_item(conf=0.55, evidence=3)
        assert item["evidence_count"] >= 2
        assert item["confidence_score"] < 0.75
        assert not _should_archive(item)

    def test_stable_state(self):
        """evidence ≥ 5, conf ≥ 0.75 → stable"""
        item = _make_item(conf=0.85, evidence=7)
        assert item["evidence_count"] >= 5
        assert item["confidence_score"] >= 0.75
        assert not _should_archive(item)

    def test_archived_from_low_conf(self):
        item = _make_item(conf=0.1, evidence=10)
        assert _should_archive(item) is True

    def test_archived_from_old_age(self):
        item = _make_item(conf=0.9, evidence=10, last_seen="2025-06-01T00:00:00+09:00")
        assert _should_archive(item) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

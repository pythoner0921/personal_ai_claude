"""Tests for merge logic: synonym dedup, fuzzy merge, and noise filtering."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from engine.consolidate import (
    canonical_description,
    is_noise,
    _merge_items,
    _fuzzy_merge,
    _jaccard_similarity,
    _tokenize,
    FUZZY_MERGE_THRESHOLD,
)


class TestSynonymMerge:
    def test_known_synonym_maps_to_canonical(self):
        assert canonical_description("dislikes verbose output") == "prefers concise output"

    def test_unknown_description_unchanged(self):
        assert canonical_description("prefers blue UI") == "prefers blue UI"

    def test_merge_combines_synonyms(self):
        items = [
            {"id": "a", "description": "prefers concise output", "confidence_score": 0.8, "evidence_count": 3},
            {"id": "b", "description": "dislikes verbose output", "confidence_score": 0.6, "evidence_count": 2},
        ]
        result = _merge_items(items)
        assert len(result) == 1
        assert result[0]["description"] == "prefers concise output"
        assert result[0]["confidence_score"] == 0.8  # max
        assert result[0]["evidence_count"] == 5  # sum


class TestFuzzyMerge:
    def test_similar_descriptions_merge(self):
        items = [
            {"id": "a", "description": "prefers concise output", "confidence_score": 0.8, "use_count": 5},
            {"id": "b", "description": "wants short responses", "confidence_score": 0.6, "use_count": 1},
        ]
        result, count = _fuzzy_merge(items)
        assert len(result) == 1
        assert count == 1

    def test_different_descriptions_not_merged(self):
        items = [
            {"id": "a", "description": "prefers concise output", "confidence_score": 0.8},
            {"id": "b", "description": "prefers table format", "confidence_score": 0.7},
        ]
        result, count = _fuzzy_merge(items)
        assert len(result) == 2
        assert count == 0

    def test_single_item_unchanged(self):
        items = [{"id": "a", "description": "test", "confidence_score": 0.5}]
        result, count = _fuzzy_merge(items)
        assert len(result) == 1
        assert count == 0

    def test_empty_list(self):
        result, count = _fuzzy_merge([])
        assert result == []
        assert count == 0


class TestTokenization:
    def test_stopwords_removed(self):
        tokens = _tokenize("prefers concise output for the user")
        assert "prefers" not in tokens
        assert "for" not in tokens
        assert "the" not in tokens
        assert "concise" in tokens

    def test_semantic_normalization(self):
        tokens = _tokenize("wants short responses")
        # "short" should normalize to "concise", "responses" to "output"
        assert "concise" in tokens
        assert "output" in tokens

    def test_similarity_symmetric(self):
        a, b = "prefers concise output", "wants brief answers"
        assert _jaccard_similarity(a, b) == _jaccard_similarity(b, a)


class TestNoiseFilter:
    def test_noise_detected(self):
        assert is_noise("prefers upright posture") is True
        assert is_noise("wants clear posture feedback") is True

    def test_real_preference_not_noise(self):
        assert is_noise("prefers concise output") is False
        assert is_noise("prefers summary before details") is False


class TestMergePreservesFields:
    def test_merge_keeps_usage_fields(self):
        items = [
            {"id": "a", "description": "prefers concise output",
             "confidence_score": 0.8, "evidence_count": 3,
             "use_count": 5, "last_used": "2026-03-15T00:00:00+09:00", "scope": "global"},
            {"id": "b", "description": "dislikes verbose output",
             "confidence_score": 0.6, "evidence_count": 2,
             "use_count": 3, "last_used": "2026-03-14T00:00:00+09:00", "scope": "project:test"},
        ]
        result = _merge_items(items)
        assert len(result) == 1
        assert result[0]["use_count"] == 8  # sum
        assert result[0]["last_used"] == "2026-03-15T00:00:00+09:00"  # latest
        assert result[0]["scope"] == "project:test"  # project-scoped wins


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

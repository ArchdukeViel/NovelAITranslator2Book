"""Glossary revision translation invalidation tests.

Covers:
- GlossarySnapshot dataclass
- compute_glossary_freshness classification (fresh, stale, legacy_unknown, unknown)
- Stale reason semantics
- Non-mutating behavior (never deactivates active versions)
- Stale active translation counts
- Cache key includes glossary_revision and glossary_hash

No live translation providers. All tests are offline.
"""

from __future__ import annotations

import pytest

from novelai.services.translation_cache import make_cache_key
from novelai.translation.glossary_freshness import (
    FRESHNESS_FRESH,
    FRESHNESS_LEGACY_UNKNOWN,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    STALE_REASON_CURRENT_SNAPSHOT_UNAVAILABLE,
    STALE_REASON_FRESH,
    STALE_REASON_HASH_MISMATCH,
    STALE_REASON_LEGACY_MISSING_REVISION,
    STALE_REASON_REVISION_MISMATCH,
    GlossarySnapshot,
    compute_glossary_freshness,
    compute_stale_active_translation_counts,
)

# ---------------------------------------------------------------------------
# Task 2: GlossarySnapshot
# ---------------------------------------------------------------------------


class TestGlossarySnapshot:
    def test_snapshot_with_revision_only(self) -> None:
        snap = GlossarySnapshot(revision=12)
        assert snap.revision == 12
        assert snap.hash is None
        assert snap.approved_term_count is None

    def test_snapshot_with_all_fields(self) -> None:
        snap = GlossarySnapshot(
            revision=12,
            hash="sha256:abc123",
            approved_term_count=48,
        )
        assert snap.revision == 12
        assert snap.hash == "sha256:abc123"
        assert snap.approved_term_count == 48

    def test_snapshot_is_frozen(self) -> None:
        snap = GlossarySnapshot(revision=12)
        with pytest.raises((AttributeError, Exception)):
            snap.revision = 13  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Task 6: Freshness classification
# ---------------------------------------------------------------------------


class TestFreshnessClassification:
    def test_fresh_when_revision_matches(self) -> None:
        current = GlossarySnapshot(revision=12, hash="sha256:abc")
        version = {"glossary_revision": 12, "glossary_hash": "sha256:abc"}
        result = compute_glossary_freshness(version, current)
        assert result["glossary_freshness"] == FRESHNESS_FRESH
        assert result["glossary_stale"] is False
        assert result["glossary_stale_reason"] == STALE_REASON_FRESH

    def test_stale_when_revision_lower(self) -> None:
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        version = {"glossary_revision": 10, "glossary_hash": "sha256:old"}
        result = compute_glossary_freshness(version, current)
        assert result["glossary_freshness"] == FRESHNESS_STALE
        assert result["glossary_stale"] is True
        assert result["glossary_stale_reason"] == STALE_REASON_REVISION_MISMATCH

    def test_stale_when_hash_differs(self) -> None:
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        version = {"glossary_revision": 12, "glossary_hash": "sha256:old"}
        result = compute_glossary_freshness(version, current)
        assert result["glossary_freshness"] == FRESHNESS_STALE
        assert result["glossary_stale"] is True
        assert result["glossary_stale_reason"] == STALE_REASON_HASH_MISMATCH

    def test_legacy_unknown_when_revision_missing(self) -> None:
        current = GlossarySnapshot(revision=12, hash="sha256:abc")
        version = {"text": "old version without glossary metadata"}
        result = compute_glossary_freshness(version, current)
        assert result["glossary_freshness"] == FRESHNESS_LEGACY_UNKNOWN
        assert result["glossary_stale"] is True
        assert result["glossary_stale_reason"] == STALE_REASON_LEGACY_MISSING_REVISION

    def test_legacy_unknown_not_stale_when_current_revision_zero(self) -> None:
        current = GlossarySnapshot(revision=0, hash=None)
        version = {"text": "old version"}
        result = compute_glossary_freshness(version, current)
        assert result["glossary_freshness"] == FRESHNESS_LEGACY_UNKNOWN
        assert result["glossary_stale"] is False

    def test_unknown_when_current_snapshot_unavailable(self) -> None:
        version = {"glossary_revision": 12, "glossary_hash": "sha256:abc"}
        result = compute_glossary_freshness(version, None)
        assert result["glossary_freshness"] == FRESHNESS_UNKNOWN
        assert result["glossary_stale"] is False
        assert result["glossary_stale_reason"] == STALE_REASON_CURRENT_SNAPSHOT_UNAVAILABLE
        assert result["current_glossary_revision"] is None
        assert result["current_glossary_hash"] is None


# ---------------------------------------------------------------------------
# Task 7: Stale reason semantics
# ---------------------------------------------------------------------------


class TestStaleReasonSemantics:
    def test_revision_mismatch_takes_precedence_over_hash_mismatch(self) -> None:
        """When revision is lower, revision_mismatch wins even if hashes also differ."""
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        version = {"glossary_revision": 10, "glossary_hash": "sha256:old"}
        result = compute_glossary_freshness(version, current)
        assert result["glossary_stale_reason"] == STALE_REASON_REVISION_MISMATCH

    def test_hash_mismatch_only_when_revisions_match(self) -> None:
        """Hash mismatch is only used when revisions are equal."""
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        version = {"glossary_revision": 12, "glossary_hash": "sha256:old"}
        result = compute_glossary_freshness(version, current)
        assert result["glossary_stale_reason"] == STALE_REASON_HASH_MISMATCH

    def test_hash_mismatch_skipped_when_current_hash_missing(self) -> None:
        """If current hash is None, hash mismatch is not used."""
        current = GlossarySnapshot(revision=12, hash=None)
        version = {"glossary_revision": 12, "glossary_hash": "sha256:old"}
        result = compute_glossary_freshness(version, current)
        assert result["glossary_freshness"] == FRESHNESS_FRESH

    def test_hash_mismatch_skipped_when_version_hash_missing(self) -> None:
        """If version hash is missing, hash mismatch is not used."""
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        version = {"glossary_revision": 12}
        result = compute_glossary_freshness(version, current)
        assert result["glossary_freshness"] == FRESHNESS_FRESH

    def test_fresh_when_revisions_match_and_hashes_match(self) -> None:
        current = GlossarySnapshot(revision=12, hash="sha256:abc")
        version = {"glossary_revision": 12, "glossary_hash": "sha256:abc"}
        result = compute_glossary_freshness(version, current)
        assert result["glossary_freshness"] == FRESHNESS_FRESH
        assert result["glossary_stale_reason"] == STALE_REASON_FRESH


# ---------------------------------------------------------------------------
# Task 15: Non-mutating behavior
# ---------------------------------------------------------------------------


class TestNonMutatingBehavior:
    def test_does_not_mutate_version(self) -> None:
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        version = {"glossary_revision": 10, "glossary_hash": "sha256:old"}
        original = dict(version)
        compute_glossary_freshness(version, current)
        assert version == original

    def test_does_not_mutate_current_snapshot(self) -> None:
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        version = {"glossary_revision": 10}
        original_revision = current.revision
        original_hash = current.hash
        compute_glossary_freshness(version, current)
        assert current.revision == original_revision
        assert current.hash == original_hash

    def test_stale_detection_does_not_deactivate_active_version(self) -> None:
        """Stale detection is read-only; it never modifies the version."""
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        version = {
            "id": "v1",
            "active": True,
            "glossary_revision": 10,
            "glossary_hash": "sha256:old",
        }
        result = compute_glossary_freshness(version, current)
        assert result["glossary_freshness"] == FRESHNESS_STALE
        # Version is not deactivated
        assert version.get("active") is True
        assert "glossary_stale" not in version


# ---------------------------------------------------------------------------
# Task 8: Freshness fields in response
# ---------------------------------------------------------------------------


class TestFreshnessResponseFields:
    def test_response_includes_all_required_fields(self) -> None:
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        version = {"glossary_revision": 10, "glossary_hash": "sha256:old"}
        result = compute_glossary_freshness(version, current)
        for key in (
            "glossary_freshness",
            "glossary_stale",
            "glossary_stale_reason",
            "current_glossary_revision",
            "current_glossary_hash",
        ):
            assert key in result

    def test_response_is_additive(self) -> None:
        """Freshness fields are additive — they don't replace existing fields."""
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        version = {
            "id": "v1",
            "text": "translated text",
            "glossary_revision": 10,
            "glossary_hash": "sha256:old",
        }
        result = compute_glossary_freshness(version, current)
        # Original fields preserved
        assert result.get("id") is None  # result is freshness-only
        # But the version dict is unchanged
        assert version["id"] == "v1"
        assert version["text"] == "translated text"


# ---------------------------------------------------------------------------
# Task 9: Stale active translation counts
# ---------------------------------------------------------------------------


class TestStaleActiveTranslationCounts:
    def test_counts_all_fresh_versions(self) -> None:
        current = GlossarySnapshot(revision=12, hash="sha256:abc")
        versions = [
            {"glossary_revision": 12, "glossary_hash": "sha256:abc"},
            {"glossary_revision": 12, "glossary_hash": "sha256:abc"},
        ]
        result = compute_stale_active_translation_counts(versions, current)
        assert result["fresh_active_translation_count"] == 2
        assert result["stale_active_translation_count"] == 0
        assert result["legacy_unknown_translation_count"] == 0
        assert result["current_glossary_revision"] == 12

    def test_counts_mixed_freshness(self) -> None:
        current = GlossarySnapshot(revision=12, hash="sha256:new")
        versions = [
            {"glossary_revision": 12, "glossary_hash": "sha256:new"},  # fresh
            {"glossary_revision": 10, "glossary_hash": "sha256:old"},  # stale
            {"text": "no glossary metadata"},  # legacy_unknown
        ]
        result = compute_stale_active_translation_counts(versions, current)
        assert result["fresh_active_translation_count"] == 1
        assert result["stale_active_translation_count"] == 1
        assert result["legacy_unknown_translation_count"] == 1

    def test_returns_none_when_no_snapshot(self) -> None:
        versions = [{"glossary_revision": 12}]
        result = compute_stale_active_translation_counts(versions, None)
        assert result["current_glossary_revision"] is None

    def test_includes_current_revision(self) -> None:
        current = GlossarySnapshot(revision=42, hash="sha256:abc")
        versions = [{"glossary_revision": 42, "glossary_hash": "sha256:abc"}]
        result = compute_stale_active_translation_counts(versions, current)
        assert result["current_glossary_revision"] == 42


# ---------------------------------------------------------------------------
# Tasks 5, 18: Cache key regression tests
# ---------------------------------------------------------------------------


_CACHE_IDENTITY = {
    "provider_key": "gemini",
    "provider_model": "gemini-3.1-flash-lite",
    "prompt_version": "translation_request_v1",
}


class TestCacheKeyRegression:
    def test_cache_key_includes_glossary_hash(self) -> None:
        key_a = make_cache_key("text", "Japanese", "English", "hash_a", **_CACHE_IDENTITY)
        key_b = make_cache_key("text", "Japanese", "English", "hash_b", **_CACHE_IDENTITY)
        assert key_a != key_b

    def test_cache_key_different_per_source_text(self) -> None:
        key_a = make_cache_key("text_a", "Japanese", "English", "hash", **_CACHE_IDENTITY)
        key_b = make_cache_key("text_b", "Japanese", "English", "hash", **_CACHE_IDENTITY)
        assert key_a != key_b

    def test_cache_key_different_per_language(self) -> None:
        key_a = make_cache_key("text", "Japanese", "English", "hash", **_CACHE_IDENTITY)
        key_b = make_cache_key("text", "Chinese", "English", "hash", **_CACHE_IDENTITY)
        assert key_a != key_b

    def test_cache_key_different_per_provider(self) -> None:
        key_a = make_cache_key("text", "Japanese", "English", "hash", **_CACHE_IDENTITY)
        key_b = make_cache_key(
            "text", "Japanese", "English", "hash", **{**_CACHE_IDENTITY, "provider_key": "provider-b"}
        )
        assert key_a != key_b

    def test_cache_key_different_per_model(self) -> None:
        key_a = make_cache_key(
            "text", "Japanese", "English", "hash", **{**_CACHE_IDENTITY, "provider_model": "model-a"}
        )
        key_b = make_cache_key(
            "text", "Japanese", "English", "hash", **{**_CACHE_IDENTITY, "provider_model": "model-b"}
        )
        assert key_a != key_b

    def test_cache_key_different_per_prompt_version(self) -> None:
        key_a = make_cache_key("text", "Japanese", "English", "hash", **{**_CACHE_IDENTITY, "prompt_version": "v1"})
        key_b = make_cache_key("text", "Japanese", "English", "hash", **{**_CACHE_IDENTITY, "prompt_version": "v2"})
        assert key_a != key_b

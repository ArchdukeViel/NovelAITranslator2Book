"""Tests for novelai.sources.status.publication_status normalization (REQ-16, AC-16).

Added alongside the "cancelled" publication_status arm (2026-09-06) so the
normalizer's order-of-precedence rules are regression-protected.
"""

from __future__ import annotations

import pytest

from novelai.sources.status import (
    PUBLICATION_STATUS_VALUES,
    normalize_publication_status,
    publication_status_payload,
)


class TestPublicationStatusValues:
    def test_includes_cancelled_alongside_legacy_variants(self) -> None:
        assert {
            "ongoing",
            "completed",
            "hiatus",
            "cancelled",
            "unknown",
        } == PUBLICATION_STATUS_VALUES


class TestNormalizeCanonicalValues:
    @pytest.mark.parametrize(
        "value",
        ["ongoing", "completed", "hiatus", "cancelled", "unknown"],
    )
    def test_canonical_values_pass_through_case_insensitively(self, value: str) -> None:
        assert normalize_publication_status(value) == value
        assert normalize_publication_status(value.upper()) == value


class TestNormalizeCancelledMarkers:
    @pytest.mark.parametrize(
        "value",
        [
            "cancelled",
            "canceled",  # US spelling
            "abandoned",
            "discontinued",
            "dropped",
            "連載中止",
            "中止",
            "打ち切り",
            "休載中",
            "連載停止",
            "更新停止",
        ],
    )
    def test_author_dropped_markers_normalize_to_cancelled(self, value: str) -> None:
        assert normalize_publication_status(value) == "cancelled"


class TestNormalizeOrderOfPrecedence:
    def test_completed_beats_cancelled_when_both_phrases_present(self) -> None:
        # 完結 (completed) co-occurring with 打ち切り (cancelled) classifies
        # as completed, because the author finished the work even if the
        # colloquial label uses 打ち切り.
        assert normalize_publication_status("完結 (打ち切り)") == "completed"

    def test_cancelled_beats_hiatus_when_both_phrases_present(self) -> None:
        # 打ち切り is decisive — author-dropped is not "on break".
        assert normalize_publication_status("打ち切り (休載中)") == "cancelled"

    def test_hiatus_marker_without_cancelled_stays_hiatus(self) -> None:
        assert normalize_publication_status("休載") == "hiatus"

    def test_unknown_markers_remain_unknown(self) -> None:
        assert normalize_publication_status("definitely not a status") == "unknown"
        assert normalize_publication_status(None) == "unknown"
        assert normalize_publication_status(123) == "unknown"
        assert normalize_publication_status("") == "unknown"
        assert normalize_publication_status("   ") == "unknown"


class TestPublicationStatusPayload:
    def test_cancelled_round_trips_through_payload(self) -> None:
        payload = publication_status_payload("連載中止")
        assert payload == {
            "publication_status": "cancelled",
            "source_publication_status": "連載中止",
        }

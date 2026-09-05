"""Tests for R2 object immutability invariant under generations/ prefix."""

from __future__ import annotations

import pytest

from novelai.storage.content_addressing import generation_key


def test_generation_key_format_and_immutability() -> None:
    """Generation keys must conform to novels/{novel_id}/generations/{generation_id}.json.gz."""
    valid_hash = "a" * 64
    key = generation_key("123", "gen_123", valid_hash)
    assert key == "novels/123/generations/gen_123.json.gz"

    with pytest.raises(ValueError, match="logical_hash must be a lowercase SHA-256 hex digest"):
        generation_key("123", "gen_123", "invalid_hash")

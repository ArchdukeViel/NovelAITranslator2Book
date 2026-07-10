from __future__ import annotations

from novelai.storage.common import CheckpointInfo, _utc_now, _utc_now_iso


class TestCheckpointInfo:
    def test_is_typed_dict(self) -> None:
        info: CheckpointInfo = {
            "filename": "checkpoint.json",
            "timestamp": "2026-01-01T00:00:00Z",
            "checkpoint_name": "cp1",
        }
        assert info["filename"] == "checkpoint.json"
        assert info["timestamp"] == "2026-01-01T00:00:00Z"
        assert info["checkpoint_name"] == "cp1"


class TestUtcNow:
    def test_returns_datetime(self) -> None:
        from datetime import datetime

        result = _utc_now()
        assert isinstance(result, datetime)

    def test_is_timezone_aware(self) -> None:
        result = _utc_now()
        assert result.tzinfo is not None


class TestUtcNowIso:
    def test_returns_string(self) -> None:
        result = _utc_now_iso()
        assert isinstance(result, str)

    def test_ends_with_z(self) -> None:
        result = _utc_now_iso()
        assert result.endswith("Z")

    def test_no_plus_offset(self) -> None:
        result = _utc_now_iso()
        assert "+00:00" not in result

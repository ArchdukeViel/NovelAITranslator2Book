"""Tests for the UsageService."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.services.usage_service import UsageService

_TMP = Path(__file__).resolve().parent / ".tmp" / "usage"


@pytest.fixture()
def usage_dir() -> Path:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ts(hour: int = 12) -> str:
    return datetime(2025, 1, 15, hour, 0, 0, tzinfo=UTC).isoformat()


class TestUsageService:
    def test_record_and_list(self, usage_dir: Path) -> None:
        svc = UsageService(base_dir=usage_dir)
        svc.record({"timestamp": _ts(), "tokens": 100})
        assert len(svc.list(all_days=True)) == 1

    def test_summary_aggregates_tokens(self, usage_dir: Path) -> None:
        svc = UsageService(base_dir=usage_dir)
        svc.record({"timestamp": _ts(10), "tokens": 50})
        svc.record({"timestamp": _ts(11), "tokens": 150})
        summary = svc.summary(all_days=True)
        assert summary["total_tokens"] == 200
        assert summary["total_requests"] == 2

    def test_clear_empties_data(self, usage_dir: Path) -> None:
        svc = UsageService(base_dir=usage_dir)
        svc.record({"timestamp": _ts(), "tokens": 1})
        svc.clear()
        assert svc.list(all_days=True) == []

    def test_persists_across_instances(self, usage_dir: Path) -> None:
        s1 = UsageService(base_dir=usage_dir)
        s1.record({"timestamp": _ts(), "tokens": 42})
        s2 = UsageService(base_dir=usage_dir)
        assert len(s2.list(all_days=True)) == 1

    def test_corrupted_file_resets(self, usage_dir: Path) -> None:
        (usage_dir / "usage.json").write_text("BROKEN", encoding="utf-8")
        svc = UsageService(base_dir=usage_dir)
        assert svc.list(all_days=True) == []

    def test_daily_history(self, usage_dir: Path) -> None:
        svc = UsageService(base_dir=usage_dir)
        svc.record({"timestamp": _ts(10), "tokens": 100})
        svc.record({"timestamp": _ts(14), "tokens": 200})
        history = svc.daily_history()
        assert len(history) >= 1
        assert history[0]["total_tokens"] == 300

    def test_list_with_limit(self, usage_dir: Path) -> None:
        svc = UsageService(base_dir=usage_dir)
        for i in range(5):
            svc.record({"timestamp": _ts(i + 1), "tokens": i})
        assert len(svc.list(limit=2, all_days=True)) == 2

    def test_estimate_entries_separate_from_usage(self, usage_dir: Path) -> None:
        svc = UsageService(base_dir=usage_dir)
        svc.record({"timestamp": _ts(), "tokens": 50, "entry_type": "usage"})
        svc.record({
            "timestamp": _ts(),
            "entry_type": "estimate",
            "estimated_input_tokens": 100,
            "estimated_output_tokens": 200,
            "estimated_cost_usd": 0.05,
        })
        summary = svc.summary(all_days=True)
        assert summary["total_requests"] == 1
        assert summary["total_estimates"] == 1
        assert summary["estimated_total_tokens"] == 300

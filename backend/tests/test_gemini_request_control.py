from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from novelai.config.settings import settings
from novelai.services.gemini_request_control import (
    GeminiQuotaController,
    QuotaRejection,
    estimate_gemini_tokens,
)


class _Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs: int) -> None:
        self.value += timedelta(**kwargs)


@pytest.fixture()
def quota_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GEMINI_RPM_LIMIT", 15)
    monkeypatch.setattr(settings, "GEMINI_TPM_LIMIT", 250_000)
    monkeypatch.setattr(settings, "GEMINI_RPD_LIMIT", 500)


def _reserve(controller: GeminiQuotaController, *, input_tokens: int = 1, output_tokens: int = 1):
    return controller.reserve(
        purpose="body_translation",
        model="gemini-3.5-flash-lite",
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
    )


def test_estimator_is_conservative_and_does_not_call_provider() -> None:
    input_tokens, output_tokens = estimate_gemini_tokens("日本語" * 3, max_output_tokens=32)
    assert input_tokens >= 3
    assert output_tokens == 32


def test_sixteenth_request_is_rejected_by_rpm(tmp_path: Path, quota_limits: None) -> None:
    clock = _Clock()
    controller = GeminiQuotaController(tmp_path, clock=clock)
    for _ in range(15):
        reservation = _reserve(controller)
        assert not isinstance(reservation, QuotaRejection)

    rejection = _reserve(controller)
    assert isinstance(rejection, QuotaRejection)
    assert rejection.code == "rate_limited"
    assert rejection.dimension == "rpm"
    assert rejection.retry_after_seconds == 60

    clock.advance(seconds=61)
    assert not isinstance(_reserve(controller), QuotaRejection)


def test_tpm_exhaustion_uses_estimate_before_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GEMINI_RPM_LIMIT", 15)
    monkeypatch.setattr(settings, "GEMINI_TPM_LIMIT", 10)
    monkeypatch.setattr(settings, "GEMINI_RPD_LIMIT", 500)
    controller = GeminiQuotaController(tmp_path, clock=_Clock())
    assert not isinstance(_reserve(controller, input_tokens=6, output_tokens=4), QuotaRejection)
    rejection = _reserve(controller, input_tokens=1, output_tokens=1)
    assert isinstance(rejection, QuotaRejection)
    assert rejection.dimension == "tpm"


def test_daily_quota_exhaustion_defers_until_next_day(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GEMINI_RPM_LIMIT", 15)
    monkeypatch.setattr(settings, "GEMINI_TPM_LIMIT", 250_000)
    monkeypatch.setattr(settings, "GEMINI_RPD_LIMIT", 1)
    clock = _Clock()
    controller = GeminiQuotaController(tmp_path, clock=clock)
    assert not isinstance(_reserve(controller), QuotaRejection)
    rejection = _reserve(controller)
    assert isinstance(rejection, QuotaRejection)
    assert rejection.code == "quota_exhausted"
    assert rejection.dimension == "rpd"
    assert rejection.retry_after_seconds == 12 * 60 * 60


def test_actual_usage_reconciles_reserved_token_estimate(tmp_path: Path, quota_limits: None) -> None:
    controller = GeminiQuotaController(tmp_path, clock=_Clock())
    reservation = _reserve(controller, input_tokens=100, output_tokens=100)
    assert not isinstance(reservation, QuotaRejection)
    controller.reconcile(reservation, input_tokens=2, output_tokens=3, total_tokens=5, success=True)
    snapshot = controller.snapshot()
    assert snapshot["current_minute"] == {"requests": 1, "tokens": 5}

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.shared.pipeline import SchedulerModelStatus


class SchedulerPolicy(StrEnum):
    VOLUME_FIRST = "volume_first"
    QUALITY_FIRST = "quality_first"


class SelectionReason(StrEnum):
    PRIMARY_AVAILABLE = "primary_available"
    PREFERRED_MODEL_COOLING_DOWN = "preferred_model_cooling_down"
    PREFERRED_MODEL_DAILY_EXHAUSTED = "preferred_model_daily_exhausted"
    RETRY_AFTER_QA_FAILED = "retry_after_qa_failed"
    FALLBACK_AFTER_MODEL_UNAVAILABLE = "fallback_after_model_unavailable"
    ALL_MODELS_COOLING_DOWN = "all_models_cooling_down"
    ALL_MODELS_DAILY_EXHAUSTED = "all_models_daily_exhausted"
    NO_MODEL_AVAILABLE = "no_model_available"


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def iso_after_seconds(seconds: int | None, *, now: datetime | None = None) -> str | None:
    if seconds is None:
        return None
    return ((now or utc_now()) + timedelta(seconds=max(0, int(seconds)))).isoformat().replace("+00:00", "Z")


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass
class SchedulerModelConfig:
    provider_key: str
    provider_model: str
    priority_order: int = 0
    quality_priority_order: int | None = None
    rpm_limit: int | None = None
    rpd_limit: int | None = None

    def sort_key(self, policy: SchedulerPolicy) -> tuple[int, str, str]:
        priority = self.priority_order
        if policy == SchedulerPolicy.QUALITY_FIRST and self.quality_priority_order is not None:
            priority = self.quality_priority_order
        return priority, self.provider_key, self.provider_model


@dataclass
class SchedulerModelRuntimeState:
    provider_key: str
    provider_model: str
    priority_order: int = 0
    rpm_limit: int | None = None
    rpd_limit: int | None = None
    requests_this_minute: int = 0
    requests_today: int = 0
    window_started_at: str | None = None
    day_started_at: str | None = None
    cooldown_until: str | None = None
    exhausted_until: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    status: str = SchedulerModelStatus.AVAILABLE.value

    @classmethod
    def from_config_and_state(
        cls,
        config: SchedulerModelConfig,
        state: dict[str, Any] | None = None,
    ) -> SchedulerModelRuntimeState:
        payload = dict(state or {})
        return cls(
            provider_key=config.provider_key,
            provider_model=config.provider_model,
            priority_order=int(payload.get("priority_order", config.priority_order) or 0),
            rpm_limit=_optional_positive_int(payload.get("rpm_limit", config.rpm_limit)),
            rpd_limit=_optional_positive_int(payload.get("rpd_limit", config.rpd_limit)),
            requests_this_minute=int(payload.get("requests_this_minute", 0) or 0),
            requests_today=int(payload.get("requests_today", 0) or 0),
            window_started_at=_optional_str(payload.get("window_started_at")),
            day_started_at=_optional_str(payload.get("day_started_at")),
            cooldown_until=_optional_str(payload.get("cooldown_until")),
            exhausted_until=_optional_str(payload.get("exhausted_until")),
            last_error_code=_optional_str(payload.get("last_error_code")),
            last_error_message=_optional_str(payload.get("last_error_message")),
            status=_optional_str(payload.get("status")) or SchedulerModelStatus.AVAILABLE.value,
        )

    def key(self) -> tuple[str, str]:
        return self.provider_key, self.provider_model

    def refresh_windows(self, now: datetime | None = None) -> None:
        current = now or utc_now()
        window_start = parse_iso(self.window_started_at)
        if window_start is None or current - window_start >= timedelta(minutes=1):
            self.window_started_at = current.isoformat().replace("+00:00", "Z")
            self.requests_this_minute = 0

        day_start = parse_iso(self.day_started_at)
        if day_start is None or current.date() != day_start.date():
            self.day_started_at = current.isoformat().replace("+00:00", "Z")
            self.requests_today = 0

        cooldown = parse_iso(self.cooldown_until)
        exhausted = parse_iso(self.exhausted_until)
        if self.status == SchedulerModelStatus.COOLING_DOWN.value and (cooldown is None or cooldown <= current):
            self.cooldown_until = None
            self.status = SchedulerModelStatus.AVAILABLE.value
        if self.status == SchedulerModelStatus.DAILY_EXHAUSTED.value and exhausted is not None and exhausted <= current:
            self.exhausted_until = None
            self.status = SchedulerModelStatus.AVAILABLE.value

    def is_available(self, now: datetime | None = None) -> bool:
        self.refresh_windows(now)
        if self.status != SchedulerModelStatus.AVAILABLE.value:
            return False
        if self.rpm_limit is not None and self.requests_this_minute >= self.rpm_limit:
            self.status = SchedulerModelStatus.COOLING_DOWN.value
            self.cooldown_until = iso_after_seconds(60, now=now)
            self.last_error_code = SelectionReason.PREFERRED_MODEL_COOLING_DOWN.value
            return False
        if self.rpd_limit is not None and self.requests_today >= self.rpd_limit:
            self.status = SchedulerModelStatus.DAILY_EXHAUSTED.value
            self.exhausted_until = self.exhausted_until or _next_day_iso(now)
            self.last_error_code = SelectionReason.PREFERRED_MODEL_DAILY_EXHAUSTED.value
            return False
        return True

    def record_attempt(self, now: datetime | None = None) -> None:
        self.refresh_windows(now)
        self.requests_this_minute += 1
        self.requests_today += 1

    def apply_provider_error(self, error: ProviderError, now: datetime | None = None) -> None:
        current = now or utc_now()
        self.last_error_code = error.provider_error_code.value
        self.last_error_message = str(error)
        if error.provider_error_code == ProviderErrorCode.RATE_LIMITED:
            self.status = SchedulerModelStatus.COOLING_DOWN.value
            self.cooldown_until = error.cooldown_until or iso_after_seconds(error.retry_after_seconds or 60, now=current)
            return
        if error.provider_error_code == ProviderErrorCode.QUOTA_EXHAUSTED:
            self.status = SchedulerModelStatus.DAILY_EXHAUSTED.value
            self.exhausted_until = error.exhausted_until or _next_day_iso(current)
            return
        if error.provider_error_code in {
            ProviderErrorCode.MODEL_UNAVAILABLE,
            ProviderErrorCode.MODEL_DEPRECATED,
        }:
            self.status = SchedulerModelStatus.FAILED.value
            return
        if error.provider_error_code == ProviderErrorCode.CONTEXT_TOO_LARGE:
            self.status = SchedulerModelStatus.FAILED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_key": self.provider_key,
            "provider_model": self.provider_model,
            "priority_order": self.priority_order,
            "rpm_limit": self.rpm_limit,
            "rpd_limit": self.rpd_limit,
            "requests_this_minute": self.requests_this_minute,
            "requests_today": self.requests_today,
            "window_started_at": self.window_started_at,
            "day_started_at": self.day_started_at,
            "cooldown_until": self.cooldown_until,
            "exhausted_until": self.exhausted_until,
            "last_error_code": self.last_error_code,
            "last_error_message": self.last_error_message,
            "status": self.status,
        }


@dataclass(frozen=True)
class SchedulerSelection:
    provider_key: str | None
    provider_model: str | None
    reason: str
    paused_reason: str | None = None
    resume_after: str | None = None

    @property
    def paused(self) -> bool:
        return self.provider_key is None or self.provider_model is None


@dataclass
class TranslationScheduler:
    model_configs: list[SchedulerModelConfig]
    policy: SchedulerPolicy = SchedulerPolicy.VOLUME_FIRST
    model_states: dict[tuple[str, str], SchedulerModelRuntimeState] = field(default_factory=dict)

    @classmethod
    def from_configs(
        cls,
        configs: list[SchedulerModelConfig],
        *,
        policy: str | SchedulerPolicy = SchedulerPolicy.VOLUME_FIRST,
        existing_state: dict[str, Any] | None = None,
    ) -> TranslationScheduler:
        scheduler_policy = normalize_policy(policy)
        states_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for raw_state in _raw_model_states(existing_state):
            provider_key = raw_state.get("provider_key")
            provider_model = raw_state.get("provider_model")
            if isinstance(provider_key, str) and isinstance(provider_model, str):
                states_by_key[(provider_key, provider_model)] = raw_state

        model_states = {
            config_key(config): SchedulerModelRuntimeState.from_config_and_state(
                config,
                states_by_key.get(config_key(config)),
            )
            for config in configs
        }
        return cls(model_configs=list(configs), policy=scheduler_policy, model_states=model_states)

    def select_model(
        self,
        *,
        chapter_id: str | None = None,
        previous_attempts: set[tuple[str, str]] | None = None,
        qa_failed: bool = False,
        now: datetime | None = None,
    ) -> SchedulerSelection:
        current = now or utc_now()
        attempted = previous_attempts or set()
        configs = sorted(self.model_configs, key=lambda item: item.sort_key(self.policy))
        if qa_failed and self.policy == SchedulerPolicy.QUALITY_FIRST:
            reason_if_selected = SelectionReason.RETRY_AFTER_QA_FAILED.value
        else:
            reason_if_selected = SelectionReason.PRIMARY_AVAILABLE.value

        first_unavailable_reason: str | None = None
        for index, config in enumerate(configs):
            key = config_key(config)
            if key in attempted:
                continue
            state = self.model_states[key]
            available = state.is_available(current)
            if available:
                if index > 0 and first_unavailable_reason:
                    return SchedulerSelection(config.provider_key, config.provider_model, first_unavailable_reason)
                return SchedulerSelection(config.provider_key, config.provider_model, reason_if_selected)
            first_unavailable_reason = first_unavailable_reason or _reason_for_unavailable_state(state)

        pause_reason, resume_after = self._pause_reason_and_resume_after(current)
        return SchedulerSelection(
            None,
            None,
            pause_reason,
            paused_reason=pause_reason,
            resume_after=resume_after,
        )

    def record_attempt_start(self, provider_key: str, provider_model: str, now: datetime | None = None) -> None:
        state = self.model_states.get((provider_key, provider_model))
        if state is not None:
            state.record_attempt(now)

    def record_provider_error(self, error: ProviderError, now: datetime | None = None) -> None:
        state = self.model_states.get((error.provider_key, error.provider_model))
        if state is not None:
            state.apply_provider_error(error, now)

    def to_model_state_list(self) -> list[dict[str, Any]]:
        ordered = sorted(self.model_configs, key=lambda item: item.sort_key(self.policy))
        return [self.model_states[config_key(config)].to_dict() for config in ordered]

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy.value,
            "model_states": self.to_model_state_list(),
        }

    def _pause_reason_and_resume_after(self, now: datetime) -> tuple[str, str | None]:
        states = list(self.model_states.values())
        cooling = [state for state in states if state.status == SchedulerModelStatus.COOLING_DOWN.value]
        exhausted = [state for state in states if state.status == SchedulerModelStatus.DAILY_EXHAUSTED.value]
        if cooling and len(cooling) == len(states):
            return SelectionReason.ALL_MODELS_COOLING_DOWN.value, _earliest_future(
                [state.cooldown_until for state in cooling],
                now,
            )
        if exhausted and len(exhausted) == len(states):
            return SelectionReason.ALL_MODELS_DAILY_EXHAUSTED.value, _earliest_future(
                [state.exhausted_until for state in exhausted],
                now,
            )
        if cooling:
            return SelectionReason.ALL_MODELS_COOLING_DOWN.value, _earliest_future(
                [state.cooldown_until for state in cooling],
                now,
            )
        if exhausted:
            return SelectionReason.ALL_MODELS_DAILY_EXHAUSTED.value, _earliest_future(
                [state.exhausted_until for state in exhausted],
                now,
            )
        return SelectionReason.NO_MODEL_AVAILABLE.value, None


class SchedulerPausedError(RuntimeError):
    def __init__(
        self,
        *,
        reason: str,
        resume_after: str | None,
        model_states: list[dict[str, Any]],
        error_code: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.paused_reason = reason
        self.resume_after = resume_after
        self.model_states = model_states
        self.error_code = error_code or reason
        self.job_status = "paused"


def normalize_policy(value: str | SchedulerPolicy | None) -> SchedulerPolicy:
    if isinstance(value, SchedulerPolicy):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == SchedulerPolicy.QUALITY_FIRST.value:
            return SchedulerPolicy.QUALITY_FIRST
    return SchedulerPolicy.VOLUME_FIRST


def normalize_model_configs(raw_items: Any, *, default_provider_key: str, default_models: list[str]) -> list[SchedulerModelConfig]:
    configs: list[SchedulerModelConfig] = []
    if isinstance(raw_items, list):
        for index, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            provider_key = _optional_str(item.get("provider_key") or item.get("provider") or default_provider_key)
            provider_model = _optional_str(item.get("provider_model") or item.get("model"))
            if provider_key is None or provider_model is None:
                continue
            configs.append(
                SchedulerModelConfig(
                    provider_key=provider_key,
                    provider_model=provider_model,
                    priority_order=(
                        _optional_nonnegative_int(item.get("priority_order"))
                        if _optional_nonnegative_int(item.get("priority_order")) is not None
                        else index
                    ),
                    quality_priority_order=_optional_nonnegative_int(item.get("quality_priority_order")),
                    rpm_limit=_optional_positive_int(item.get("rpm_limit")),
                    rpd_limit=_optional_positive_int(item.get("rpd_limit")),
                )
            )

    if configs:
        return _dedupe_configs(configs)

    return [
        SchedulerModelConfig(
            provider_key=default_provider_key,
            provider_model=model,
            priority_order=index,
        )
        for index, model in enumerate(default_models)
        if model
    ]


def config_key(config: SchedulerModelConfig) -> tuple[str, str]:
    return config.provider_key, config.provider_model


def _dedupe_configs(configs: list[SchedulerModelConfig]) -> list[SchedulerModelConfig]:
    seen: set[tuple[str, str]] = set()
    deduped: list[SchedulerModelConfig] = []
    for config in configs:
        key = config_key(config)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(config)
    return deduped


def _raw_model_states(existing_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(existing_state, dict):
        return []
    raw_states = existing_state.get("model_states")
    if isinstance(raw_states, list):
        return [dict(item) for item in raw_states if isinstance(item, dict)]
    return []


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _optional_nonnegative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _reason_for_unavailable_state(state: SchedulerModelRuntimeState) -> str:
    if state.status == SchedulerModelStatus.COOLING_DOWN.value:
        return SelectionReason.PREFERRED_MODEL_COOLING_DOWN.value
    if state.status == SchedulerModelStatus.DAILY_EXHAUSTED.value:
        return SelectionReason.PREFERRED_MODEL_DAILY_EXHAUSTED.value
    if state.last_error_code in {
        ProviderErrorCode.MODEL_UNAVAILABLE.value,
        ProviderErrorCode.MODEL_DEPRECATED.value,
    }:
        return SelectionReason.FALLBACK_AFTER_MODEL_UNAVAILABLE.value
    return SelectionReason.NO_MODEL_AVAILABLE.value


def _earliest_future(values: list[str | None], now: datetime) -> str | None:
    parsed = [value for value in (parse_iso(item) for item in values) if value is not None and value >= now]
    if not parsed:
        return None
    return min(parsed).isoformat().replace("+00:00", "Z")


def _next_day_iso(now: datetime | None = None) -> str:
    current = now or utc_now()
    tomorrow = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return tomorrow.isoformat().replace("+00:00", "Z")

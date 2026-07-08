from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.shared.pipeline import SchedulerModelStatus

FAILED_MODEL_STATE_TTL_SECONDS = 60 * 60


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
    failed_at: str | None = None
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
            failed_at=_optional_str(payload.get("failed_at")),
            last_error_code=_optional_str(payload.get("last_error_code")),
            last_error_message=_optional_str(payload.get("last_error_message")),
            status=_optional_str(payload.get("status")) or SchedulerModelStatus.AVAILABLE.value,
        )

    def key(self) -> tuple[str, str]:
        return self.provider_key, self.provider_model

    def refresh_windows(self, now: datetime | None = None) -> None:
        current = now or utc_now()
        if self.status == SchedulerModelStatus.FAILED.value and self._failed_state_expired(current):
            self.status = SchedulerModelStatus.AVAILABLE.value
            self.failed_at = None
            self.last_error_code = None
            self.last_error_message = None

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

    def _failed_state_expired(self, current: datetime) -> bool:
        failed_at = parse_iso(self.failed_at)
        if failed_at is None:
            failed_at = parse_iso(self.window_started_at) or parse_iso(self.day_started_at)
        if failed_at is None:
            return False
        return current - failed_at >= timedelta(seconds=FAILED_MODEL_STATE_TTL_SECONDS)

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
            self.failed_at = current.isoformat().replace("+00:00", "Z")
            return
        if error.provider_error_code == ProviderErrorCode.CONTEXT_TOO_LARGE:
            self.status = SchedulerModelStatus.FAILED.value
            self.failed_at = current.isoformat().replace("+00:00", "Z")

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
            "failed_at": self.failed_at,
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


# Scheduler observability: decision records (REQ-1, REQ-2, REQ-3).
MAX_SCHEDULER_DECISION_CANDIDATES = 20


@dataclass
class SchedulerCandidateDecision:
    provider: str
    model: str
    status: str | None
    selected: bool
    skip_reason: str | None
    cooldown_until: str | None = None
    exhausted_until: str | None = None
    failed_at: str | None = None
    last_error_code: str | None = None


@dataclass
class SchedulerDecision:
    request_id: str | None = None
    activity_id: str | None = None
    job_id: str | None = None
    chapter_id: str | None = None
    checkpoint_id: str | None = None
    selected_provider: str | None = None
    selected_model: str | None = None
    policy: str = ""
    fallback_used: bool = False
    selected_at: str | None = None
    candidates: list[SchedulerCandidateDecision] | None = None
    failure_reason: str | None = None
    parallel_slot: int | None = None
    exact_memory_bytes: int | None = None
    memory_limit_bytes: int | None = None
    memory_pressure: bool | None = None
    candidate_count_total: int = 0
    candidate_count_recorded: int = 0
    candidate_list_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "policy": self.policy,
            "selected_at": self.selected_at,
        }
        if self.request_id:
            result["request_id"] = self.request_id
        if self.activity_id:
            result["activity_id"] = self.activity_id
        if self.job_id:
            result["job_id"] = self.job_id
        if self.chapter_id:
            result["chapter_id"] = self.chapter_id
        if self.checkpoint_id:
            result["checkpoint_id"] = self.checkpoint_id
        if self.selected_provider and self.selected_model:
            result["selected"] = {"provider": self.selected_provider, "model": self.selected_model}
        else:
            result["selected"] = None
        if self.fallback_used:
            result["fallback_used"] = True
        if self.failure_reason:
            result["failure_reason"] = self.failure_reason
        if self.candidates:
            result["candidates"] = [
                {
                    "provider": c.provider,
                    "model": c.model,
                    "status": c.status,
                    "selected": c.selected,
                    "skip_reason": c.skip_reason,
                }
                for c in self.candidates
            ]
        else:
            result["candidates"] = []
        result["candidate_count_total"] = self.candidate_count_total
        result["candidate_count_recorded"] = self.candidate_count_recorded
        result["candidate_list_truncated"] = self.candidate_list_truncated
        if self.parallel_slot is not None:
            result["parallel_slot"] = self.parallel_slot
        if self.exact_memory_bytes is not None:
            result["memory"] = {
                "exact_memory_bytes": self.exact_memory_bytes,
                "memory_limit_bytes": self.memory_limit_bytes,
                "memory_pressure": self.memory_pressure,
            }
        return result


def build_scheduler_summary(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate scheduler decisions into a compact activity summary (REQ-12).

    Returns a dict with:
        - ``chapters_with_decisions``
        - ``fallback_count``
        - ``no_capacity_count``
        - ``skip_reason_counts``
        - ``selected_model_counts``
        - ``provider_counts``
        - ``checkpoint_blocked_count``
        - ``memory_pressure_count``
        - ``peak_exact_memory_bytes``

    Thread-safe for parallel chapter processing since it operates on an
    already-collected list.
    """
    chapters_with_decisions = len(decisions)
    fallback_count = 0
    no_capacity_count = 0
    skip_reason_counts: dict[str, int] = {}
    selected_model_counts: dict[str, int] = {}
    provider_counts: dict[str, int] = {}
    checkpoint_blocked_count = 0
    memory_pressure_count = 0
    peak_exact_memory_bytes = 0

    for d in decisions:
        if d.get("fallback_used"):
            fallback_count += 1
        if d.get("failure_reason") == "no_capacity":
            no_capacity_count += 1

        selected = d.get("selected")
        if isinstance(selected, dict):
            provider = str(selected.get("provider") or "")
            model = str(selected.get("model") or "")
            if provider and model:
                key = f"{provider}:{model}"
                selected_model_counts[key] = selected_model_counts.get(key, 0) + 1
                provider_counts[provider] = provider_counts.get(provider, 0) + 1

        candidates = d.get("candidates")
        if isinstance(candidates, list):
            for c in candidates:
                if isinstance(c, dict):
                    reason = c.get("skip_reason")
                    if isinstance(reason, str) and reason:
                        skip_reason_counts[reason] = skip_reason_counts.get(reason, 0) + 1

        if d.get("checkpoint_id"):
            checkpoint_blocked_count += 1

        memory = d.get("memory")
        if isinstance(memory, dict):
            if memory.get("memory_pressure"):
                memory_pressure_count += 1
            peak = memory.get("exact_memory_bytes") or 0
            if isinstance(peak, (int, float)) and peak > peak_exact_memory_bytes:
                peak_exact_memory_bytes = int(peak)

    return {
        "chapters_with_decisions": chapters_with_decisions,
        "fallback_count": fallback_count,
        "no_capacity_count": no_capacity_count,
        "checkpoint_blocked_count": checkpoint_blocked_count,
        "memory_pressure_count": memory_pressure_count,
        "peak_exact_memory_bytes": peak_exact_memory_bytes,
        "skip_reason_counts": dict(sorted(skip_reason_counts.items())),
        "selected_model_counts": dict(sorted(selected_model_counts.items())),
        "provider_counts": dict(sorted(provider_counts.items())),
    }


class SchedulerDecisionRecorder:
    """Observes scheduler selection without influencing it.

    Records evaluated candidates, selected decision, and skip reasons.
    Must not change scheduler behavior.
    """

    def __init__(
        self,
        *,
        request_id: str | None = None,
        activity_id: str | None = None,
        job_id: str | None = None,
        chapter_id: str | None = None,
        checkpoint_id: str | None = None,
        parallel_slot: int | None = None,
    ) -> None:
        self._decision = SchedulerDecision(
            request_id=request_id,
            activity_id=activity_id,
            job_id=job_id,
            chapter_id=chapter_id,
            checkpoint_id=checkpoint_id,
            parallel_slot=parallel_slot,
        )
        self._candidates: list[SchedulerCandidateDecision] = []

    def record_candidate(
        self,
        *,
        provider: str,
        model: str,
        status: str | None,
        selected: bool,
        skip_reason: str | None = None,
        cooldown_until: str | None = None,
        exhausted_until: str | None = None,
        failed_at: str | None = None,
        last_error_code: str | None = None,
    ) -> None:
        if len(self._candidates) >= MAX_SCHEDULER_DECISION_CANDIDATES:
            self._decision.candidate_list_truncated = True
            return
        self._candidates.append(
            SchedulerCandidateDecision(
                provider=provider,
                model=model,
                status=status,
                selected=selected,
                skip_reason=skip_reason,
                cooldown_until=cooldown_until,
                exhausted_until=exhausted_until,
                failed_at=failed_at,
                last_error_code=last_error_code,
            )
        )

    def finalize(
        self,
        *,
        selection: SchedulerSelection,
        policy: str,
        total_candidates: int = 0,
        selected_at: str | None = None,
    ) -> SchedulerDecision:
        self._decision.policy = policy
        self._decision.selected_at = selected_at or utc_now_iso()
        self._decision.selected_provider = selection.provider_key
        self._decision.selected_model = selection.provider_model
        self._decision.fallback_used = (
            selection.reason != SelectionReason.PRIMARY_AVAILABLE.value
            and selection.provider_key is not None
        )
        self._decision.failure_reason = (
            "no_capacity" if selection.paused and "cooldown" not in (selection.reason or "") and "exhausted" not in (selection.reason or "") else None
        )
        self._decision.candidates = self._candidates
        self._decision.candidate_count_total = total_candidates
        self._decision.candidate_count_recorded = len(self._candidates)
        return self._decision


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
        decision_recorder: SchedulerDecisionRecorder | None = None,
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

            # Record candidate evaluation (REQ-5, REQ-6).
            if decision_recorder is not None:
                skip_reason = None if available else _reason_for_unavailable_state(state)
                decision_recorder.record_candidate(
                    provider=config.provider_key,
                    model=config.provider_model,
                    status=state.status,
                    selected=available and (index == 0 or first_unavailable_reason is not None),
                    skip_reason=skip_reason,
                    cooldown_until=state.cooldown_until,
                    exhausted_until=state.exhausted_until,
                    failed_at=state.failed_at,
                    last_error_code=state.last_error_code,
                )

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
        self.pipeline_context: Any | None = None


def normalize_policy(value: str | SchedulerPolicy | None) -> SchedulerPolicy:
    if isinstance(value, SchedulerPolicy):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == SchedulerPolicy.QUALITY_FIRST.value:
            return SchedulerPolicy.QUALITY_FIRST
    return SchedulerPolicy.VOLUME_FIRST


def normalize_model_configs(raw_items: Any, *, default_provider_key: str, default_models: list[str], allow_empty: bool = False) -> list[SchedulerModelConfig]:
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

    if allow_empty:
        return []

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

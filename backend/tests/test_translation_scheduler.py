from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.providers.base import TranslationProvider
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.shared.pipeline import ChunkAttemptStatus, ChunkTranslationStatus, SchedulerModelStatus
from novelai.storage.service import StorageService
from novelai.translation.pipeline.context import PipelineState, TranslationChunk
from novelai.translation.pipeline.stages.translate import TranslateStage
from novelai.translation.scheduler import (
    SchedulerModelConfig,
    SchedulerPausedError,
    SchedulerPolicy,
    SelectionReason,
    TranslationScheduler,
)
from tests.conftest import TESTS_TMP_ROOT


class ScheduledProvider(TranslationProvider):
    def __init__(
        self,
        *,
        provider_key: str = "mock",
        models: list[str] | None = None,
        failures: dict[str, ProviderError] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._key = provider_key
        self.models = models or ["fast", "slow", "strong"]
        self.failures = failures or {}
        self.metadata = metadata or {"usage": {"total_tokens": 12}}
        self.calls: list[str | None] = []

    @property
    def key(self) -> str:
        return self._key

    def available_models(self) -> list[str]:
        return list(self.models)

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        self.calls.append(model)
        if isinstance(model, str) and model in self.failures:
            raise self.failures[model]
        return {
            "text": f"translated by {model}: {prompt}",
            "metadata": dict(self.metadata),
        }


@pytest.fixture()
def scheduler_storage() -> StorageService:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"scheduler_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    storage = StorageService(data_dir)
    yield storage
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture()
def scheduler_services(scheduler_storage: StorageService) -> tuple[TranslationCache, PreferencesService, UsageService]:
    cache = TranslationCache(scheduler_storage.base_dir)
    preferences = PreferencesService(scheduler_storage.base_dir)
    usage = UsageService(scheduler_storage.base_dir)
    return cache, preferences, usage


def _configs() -> list[SchedulerModelConfig]:
    return [
        SchedulerModelConfig(provider_key="mock", provider_model="fast", priority_order=0, quality_priority_order=1),
        SchedulerModelConfig(provider_key="mock", provider_model="strong", priority_order=1, quality_priority_order=0),
        SchedulerModelConfig(provider_key="mock", provider_model="slow", priority_order=2, quality_priority_order=2),
    ]


def _chunk() -> TranslationChunk:
    return TranslationChunk(
        chunk_id="c0001",
        novel_id="novel1",
        chapter_ids=["chapter_001"],
        paragraph_ids=["p0001"],
        source_text="[CHAPTER chapter_001]\n[P p0001]\nSource text.",
        char_count=44,
        paragraph_refs=[("chapter_001", "p0001")],
    )


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _context(*, policy: str = "volume_first") -> PipelineState:
    context = PipelineState(
        chapter_url="test",
        job_id="job_1",
        activity_id="activity_1",
        novel_id="novel1",
        chapter_id="chapter_001",
        provider_key="mock",
        provider_model="fast",
    )
    context.translation_chunks = [_chunk()]
    context.chunks = [context.translation_chunks[0].source_text]
    context.metadata["scheduler_policy"] = policy
    context.metadata["scheduler_models"] = [
        {"provider_key": "mock", "provider_model": "fast", "priority_order": 0, "quality_priority_order": 1},
        {"provider_key": "mock", "provider_model": "strong", "priority_order": 1, "quality_priority_order": 0},
        {"provider_key": "mock", "provider_model": "slow", "priority_order": 2, "quality_priority_order": 2},
    ]
    return context


def _two_chunk_context() -> PipelineState:
    context = _context()
    first = context.translation_chunks[0]
    second = TranslationChunk(
        chunk_id="c0002",
        novel_id="novel1",
        chapter_ids=["chapter_001"],
        paragraph_ids=["p0002"],
        source_text="[CHAPTER chapter_001]\n[P p0002]\nSecond source text.",
        char_count=51,
        paragraph_refs=[("chapter_001", "p0002")],
    )
    context.translation_chunks = [first, second]
    context.chunks = [chunk.source_text for chunk in context.translation_chunks]
    return context


def test_scheduler_model_selection_volume_first_prefers_primary() -> None:
    scheduler = TranslationScheduler.from_configs(_configs(), policy=SchedulerPolicy.VOLUME_FIRST)

    selection = scheduler.select_model(chapter_id="chapter_001")

    assert selection.provider_model == "fast"
    assert selection.reason == SelectionReason.PRIMARY_AVAILABLE.value


def test_scheduler_model_selection_quality_first_prefers_quality_model() -> None:
    scheduler = TranslationScheduler.from_configs(_configs(), policy=SchedulerPolicy.QUALITY_FIRST)

    selection = scheduler.select_model(chapter_id="chapter_001", qa_failed=True)

    assert selection.provider_model == "strong"
    assert selection.reason == SelectionReason.RETRY_AFTER_QA_FAILED.value


def test_scheduler_falls_back_when_preferred_model_cooling_down() -> None:
    scheduler = TranslationScheduler.from_configs(_configs(), policy=SchedulerPolicy.VOLUME_FIRST)
    scheduler.model_states[("mock", "fast")].status = SchedulerModelStatus.COOLING_DOWN.value
    scheduler.model_states[("mock", "fast")].cooldown_until = "2999-01-01T00:00:00Z"

    selection = scheduler.select_model(chapter_id="chapter_001")

    assert selection.provider_model == "strong"
    assert selection.reason == SelectionReason.PREFERRED_MODEL_COOLING_DOWN.value


def test_scheduler_falls_back_when_preferred_model_daily_exhausted() -> None:
    scheduler = TranslationScheduler.from_configs(_configs(), policy=SchedulerPolicy.VOLUME_FIRST)
    scheduler.model_states[("mock", "fast")].status = SchedulerModelStatus.DAILY_EXHAUSTED.value
    scheduler.model_states[("mock", "fast")].exhausted_until = "2999-01-01T00:00:00Z"

    selection = scheduler.select_model(chapter_id="chapter_001")

    assert selection.provider_model == "strong"
    assert selection.reason == SelectionReason.PREFERRED_MODEL_DAILY_EXHAUSTED.value


def test_scheduler_all_models_cooling_down_pauses_with_resume_after() -> None:
    scheduler = TranslationScheduler.from_configs(_configs()[:2], policy=SchedulerPolicy.VOLUME_FIRST)
    for state in scheduler.model_states.values():
        state.status = SchedulerModelStatus.COOLING_DOWN.value
        state.cooldown_until = "2999-01-01T00:00:00Z"

    selection = scheduler.select_model(chapter_id="chapter_001")

    assert selection.paused
    assert selection.paused_reason == SelectionReason.ALL_MODELS_COOLING_DOWN.value
    assert selection.resume_after == "2999-01-01T00:00:00Z"


def test_scheduler_all_models_daily_exhausted_pauses_until_quota_reset() -> None:
    scheduler = TranslationScheduler.from_configs(_configs()[:2], policy=SchedulerPolicy.VOLUME_FIRST)
    for state in scheduler.model_states.values():
        state.status = SchedulerModelStatus.DAILY_EXHAUSTED.value
        state.exhausted_until = "2999-01-02T00:00:00Z"

    selection = scheduler.select_model(chapter_id="chapter_001")

    assert selection.paused
    assert selection.paused_reason == SelectionReason.ALL_MODELS_DAILY_EXHAUSTED.value
    assert selection.resume_after == "2999-01-02T00:00:00Z"


def test_scheduler_provider_errors_update_only_one_model() -> None:
    scheduler = TranslationScheduler.from_configs(_configs()[:2], policy=SchedulerPolicy.VOLUME_FIRST)
    error = ProviderError(
        ProviderErrorCode.QUOTA_EXHAUSTED,
        provider_key="mock",
        provider_model="fast",
        message="quota exhausted",
        exhausted_until="2999-01-01T00:00:00Z",
    )

    scheduler.record_provider_error(error)

    assert scheduler.model_states[("mock", "fast")].status == SchedulerModelStatus.DAILY_EXHAUSTED.value
    assert scheduler.model_states[("mock", "strong")].status == SchedulerModelStatus.AVAILABLE.value


@pytest.mark.asyncio
async def test_translate_stage_records_provider_request_and_chunk_output(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(models=["fast", "strong"])
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    context = await stage.run(_context())

    assert provider.calls == ["fast"]
    assert context.chunk_states["c0001"]["provider_model"] == "fast"
    request = scheduler_storage.list_provider_request_records(novel_id="novel1", success=True)[0]
    assert request["chunk_id"] == "c0001"
    assert request["chapter_ids"] == ["chapter_001"]
    assert request["paragraph_ids"] == ["p0001"]
    assert request["scheduler_policy"] == SchedulerPolicy.VOLUME_FIRST.value
    assert request["selection_reason"] == SelectionReason.PRIMARY_AVAILABLE.value
    assert request["attempt_number"] == 1
    outputs = scheduler_storage.read_translation_output("novel1", chunk_id="c0001")
    assert isinstance(outputs, list)
    assert outputs[0]["provider_model"] == "fast"
    assert outputs[0]["source_text_hash"] == _hash_text(_chunk().source_text)
    attempts = scheduler_storage.list_chunk_attempt_records(novel_id="novel1", chunk_id="c0001")
    assert [attempt["status"] for attempt in attempts] == [ChunkAttemptStatus.SUCCEEDED.value]


@pytest.mark.asyncio
async def test_translate_stage_rate_limit_fallback_records_failed_and_successful_requests(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(
        models=["fast", "strong"],
        failures={
            "fast": ProviderError(
                ProviderErrorCode.RATE_LIMITED,
                provider_key="mock",
                provider_model="fast",
                message="rate limited",
                retry_after_seconds=21,
            )
        },
    )
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    context = await stage.run(_context())

    assert provider.calls == ["fast", "strong"]
    assert context.chunk_states["c0001"]["provider_model"] == "strong"
    failed = scheduler_storage.list_provider_request_records(novel_id="novel1", success=False)
    assert failed[0]["provider_model"] == "fast"
    assert failed[0]["normalized_provider_error_code"] == ProviderErrorCode.RATE_LIMITED.value
    failed_attempts = scheduler_storage.list_chunk_attempt_records(
        novel_id="novel1",
        chunk_id="c0001",
        status=ChunkAttemptStatus.FAILED.value,
    )
    assert failed_attempts[0]["provider_model"] == "fast"
    assert failed_attempts[0]["error_code"] == ProviderErrorCode.RATE_LIMITED.value
    model_states = context.scheduler_state["model_states"]
    fast_state = next(state for state in model_states if state["provider_model"] == "fast")
    strong_state = next(state for state in model_states if state["provider_model"] == "strong")
    assert fast_state["status"] == SchedulerModelStatus.COOLING_DOWN.value
    assert strong_state["status"] == SchedulerModelStatus.AVAILABLE.value


@pytest.mark.asyncio
async def test_translate_stage_all_models_cooling_down_pauses(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(
        models=["fast", "strong"],
        failures={
            "fast": ProviderError(
                ProviderErrorCode.RATE_LIMITED,
                provider_key="mock",
                provider_model="fast",
                message="rate limited",
                retry_after_seconds=21,
            ),
            "strong": ProviderError(
                ProviderErrorCode.RATE_LIMITED,
                provider_key="mock",
                provider_model="strong",
                message="rate limited",
                retry_after_seconds=42,
            ),
        },
    )
    context = _context()
    context.metadata["scheduler_models"] = context.metadata["scheduler_models"][:2]
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    with pytest.raises(SchedulerPausedError) as caught:
        await stage.run(context)

    assert caught.value.paused_reason == SelectionReason.ALL_MODELS_COOLING_DOWN.value
    assert caught.value.resume_after is not None
    assert provider.calls == ["fast", "strong"]
    assert len(scheduler_storage.list_provider_request_records(novel_id="novel1", success=False)) == 2


@pytest.mark.asyncio
async def test_translate_stage_all_models_daily_exhausted_pauses_until_quota_reset(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(
        models=["fast", "strong"],
        failures={
            "fast": ProviderError(
                ProviderErrorCode.QUOTA_EXHAUSTED,
                provider_key="mock",
                provider_model="fast",
                message="daily quota exhausted",
                exhausted_until="2999-01-02T00:00:00Z",
            ),
            "strong": ProviderError(
                ProviderErrorCode.QUOTA_EXHAUSTED,
                provider_key="mock",
                provider_model="strong",
                message="daily quota exhausted",
                exhausted_until="2999-01-03T00:00:00Z",
            ),
        },
    )
    context = _context()
    context.metadata["scheduler_models"] = context.metadata["scheduler_models"][:2]
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    with pytest.raises(SchedulerPausedError) as caught:
        await stage.run(context)

    assert caught.value.paused_reason == SelectionReason.ALL_MODELS_DAILY_EXHAUSTED.value
    assert caught.value.resume_after == "2999-01-02T00:00:00Z"
    states = caught.value.model_states
    assert {state["status"] for state in states} == {SchedulerModelStatus.DAILY_EXHAUSTED.value}


@pytest.mark.asyncio
async def test_translate_stage_qa_failed_chunk_uses_quality_policy(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(models=["fast", "strong"])
    context = _context(policy="quality_first")
    context.chunk_states["c0001"] = {
        "chunk_id": "c0001",
        "novel_id": "novel1",
        "chapter_ids": ["chapter_001"],
        "paragraph_ids": ["p0001"],
        "status": ChunkTranslationStatus.QA_FAILED.value,
    }
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    await stage.run(context)

    assert provider.calls == ["strong"]
    assert context.chunk_states["c0001"]["selection_reason"] == SelectionReason.RETRY_AFTER_QA_FAILED.value


@pytest.mark.asyncio
async def test_translate_stage_reuses_successful_chunk_output_after_resume(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(models=["fast", "strong"])
    chunk = _chunk()
    scheduler_storage.upsert_chunk_state(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001"],
            "status": ChunkTranslationStatus.TRANSLATED.value,
            "provider_key": "mock",
            "provider_model": "fast",
        }
    )
    scheduler_storage.save_translation_output(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001"],
            "translated_text": "stored translated chunk",
            "source_text_hash": _hash_text(chunk.source_text),
            "provider_key": "mock",
            "provider_model": "fast",
            "prompt_version": "translation_request_v1",
            "glossary_hash": _hash_text(""),
            "style_preset": None,
            "json_output": False,
            "consistency_mode": False,
        }
    )
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    context = await stage.run(_context())

    assert provider.calls == []
    assert context.translations == ["stored translated chunk"]
    assert context.metadata["progress"]["completed"] == 1
    attempts = scheduler_storage.list_chunk_attempt_records(novel_id="novel1", chunk_id="c0001")
    assert attempts[-1]["status"] == ChunkAttemptStatus.SKIPPED_ALREADY_SUCCEEDED.value


@pytest.mark.asyncio
async def test_translate_stage_retries_incomplete_chunk_after_resume(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(models=["fast", "strong"])
    context = _two_chunk_context()
    first = context.translation_chunks[0]
    scheduler_storage.upsert_chunk_state(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001"],
            "status": ChunkTranslationStatus.TRANSLATED.value,
            "provider_key": "mock",
            "provider_model": "fast",
        }
    )
    scheduler_storage.upsert_chunk_state(
        {
            "chunk_id": "c0002",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0002"],
            "status": ChunkTranslationStatus.NEEDS_RETRY.value,
        }
    )
    scheduler_storage.save_translation_output(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001"],
            "translated_text": "stored first chunk",
            "source_text_hash": _hash_text(first.source_text),
            "provider_key": "mock",
            "provider_model": "fast",
            "prompt_version": "translation_request_v1",
            "glossary_hash": _hash_text(""),
            "style_preset": None,
            "json_output": False,
            "consistency_mode": False,
        }
    )
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    result = await stage.run(context)

    assert provider.calls == ["fast"]
    assert result.translations[0] == "stored first chunk"
    assert "Second source text" in result.translations[1]
    assert result.metadata["progress"]["completed"] == 2


@pytest.mark.asyncio
async def test_translate_stage_cache_hit_records_skipped_attempt_without_provider_request(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(models=["fast", "strong"])
    chunk = _chunk()
    cache.set(chunk.source_text, "mock", "fast", "cached translated chunk")
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    context = await stage.run(_context())

    assert provider.calls == []
    assert context.translations == ["cached translated chunk"]
    assert scheduler_storage.list_provider_request_records(novel_id="novel1") == []
    attempts = scheduler_storage.list_chunk_attempt_records(novel_id="novel1", chunk_id="c0001")
    assert [attempt["status"] for attempt in attempts] == [ChunkAttemptStatus.SKIPPED_CACHE_HIT.value]
    outputs = scheduler_storage.read_translation_output("novel1", chunk_id="c0001")
    assert isinstance(outputs, list)
    assert outputs[-1]["cache_hit"] is True


@pytest.mark.asyncio
async def test_translate_stage_force_retranslate_ignores_successful_chunk_output(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(models=["fast", "strong"])
    chunk = _chunk()
    scheduler_storage.upsert_chunk_state(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001"],
            "status": ChunkTranslationStatus.TRANSLATED.value,
            "provider_key": "mock",
            "provider_model": "fast",
        }
    )
    scheduler_storage.save_translation_output(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001"],
            "translated_text": "stored translated chunk",
            "source_text_hash": _hash_text(chunk.source_text),
            "provider_key": "mock",
            "provider_model": "fast",
            "prompt_version": "translation_request_v1",
            "glossary_hash": _hash_text(""),
            "style_preset": None,
            "json_output": False,
            "consistency_mode": False,
        }
    )
    context = _context()
    context.metadata["force_retranslate"] = True
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    result = await stage.run(context)

    assert provider.calls == ["fast"]
    assert result.translations != ["stored translated chunk"]


@pytest.mark.asyncio
async def test_translate_stage_does_not_reuse_successful_chunk_when_prompt_metadata_changes(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(models=["fast", "strong"])
    chunk = _chunk()
    scheduler_storage.upsert_chunk_state(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001"],
            "status": ChunkTranslationStatus.TRANSLATED.value,
            "provider_key": "mock",
            "provider_model": "fast",
        }
    )
    scheduler_storage.save_translation_output(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001"],
            "translated_text": "stale translated chunk",
            "source_text_hash": _hash_text(chunk.source_text),
            "provider_key": "mock",
            "provider_model": "fast",
            "prompt_version": "old_prompt",
            "glossary_hash": _hash_text(""),
            "style_preset": None,
            "json_output": False,
            "consistency_mode": False,
        }
    )
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    result = await stage.run(_context())

    assert provider.calls == ["fast"]
    assert result.translations != ["stale translated chunk"]


@pytest.mark.asyncio
async def test_translate_stage_redacts_secrets_from_provider_request_metadata(
    scheduler_storage: StorageService,
    scheduler_services: tuple[TranslationCache, PreferencesService, UsageService],
) -> None:
    cache, preferences, usage = scheduler_services
    provider = ScheduledProvider(
        models=["fast", "strong"],
        metadata={
            "usage": {"total_tokens": 12},
            "headers": {"authorization": "Bearer secret"},
            "api_key": "secret-key",
            "nested": {"token": "secret-token", "safe": "kept"},
        },
    )
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=cache,
        settings_service=preferences,
        usage_service=usage,
        storage=scheduler_storage,
    )

    await stage.run(_context())

    request = scheduler_storage.list_provider_request_records(novel_id="novel1", success=True)[0]
    assert "headers" not in request["usage_metadata"]
    assert "api_key" not in request["usage_metadata"]
    assert "token" not in request["usage_metadata"]["nested"]
    assert request["usage_metadata"]["nested"]["safe"] == "kept"

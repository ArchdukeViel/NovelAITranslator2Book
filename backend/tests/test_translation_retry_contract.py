"""Blocker C contract tests: retry-marked chunks are re-translated fresh.

Accepted-output-only contract under test:

1. A chunk marked ``needs_retry``/``needs_review``/``qa_failed`` must never
   reuse existing output, never read either cache, and always issue a fresh
   provider request (requirements 2-6).
2. A persisted ``translated`` chunk state must never overwrite an in-memory
   retry marker (requirement: persisted state must not overwrite
   ``needs_retry``).
3. QA dispositions (incl. ``needs_retry``/``needs_review``/``qa_failed``) are
   persisted so markers survive re-runs and restarts.
4. No output is written to either cache before QA passes (requirement 5):
   the legacy ``TranslationCache`` pre-QA write is removed; pending entries
   carry ``chunk_id``/``attempt_number``/``translation_run_id``/``output_hash``
   (requirement 11) and are flushed only after QA accepts the chunk.
5. ``CacheFlushStage`` drops rejected entries and dedupes by key so only the
   final accepted attempt is cached.
6. ``LLM_QA_POLICY=blocking_retry`` re-runs deterministic + LLM QA on the
   fresh output (requirement 7), accepts/caches only after QA passes
   (requirement 8), and marks ``needs_review`` when the retry budget is
   exhausted (requirement 9).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from novelai.config.settings import settings
from novelai.services.glossary_apply import _hash_text
from novelai.services.translation_cache import CacheEntry, TranslationCacheService, make_cache_key
from novelai.translation.pipeline.context import PipelineState, TranslationChunk
from novelai.translation.pipeline.pipeline import TranslationPipeline
from novelai.translation.pipeline.stages.cache_flush import CacheFlushStage
from novelai.translation.pipeline.stages.translate import TranslateStage
from novelai.translation.pipeline.stages.translate_cache_lookup import (
    load_persisted_chunk_states,
)
from novelai.translation.pipeline.stages.translate_result_assembly import hash_text
from novelai.translation.pipeline.stages.translation_qa import TranslationQAStage
from novelai.translation.qa import TranslationQAError
from tests.conftest import create_test_fixture


def _chunk(chunk_id: str = "c0001", novel_id: str = "novel1") -> TranslationChunk:
    return TranslationChunk(
        chunk_id=chunk_id,
        novel_id=novel_id,
        chapter_ids=["chapter_001"],
        paragraph_ids=["p0001", "p0002"],
        source_text=(
            "[CHAPTER chapter_001]\n"
            "[P p0001]\n"
            "Source paragraph chapter_001/p0001.\n"
            "[P p0002]\n"
            "Source paragraph chapter_001/p0002."
        ),
        char_count=120,
    )


def _context(novel_id: str = "novel1", run_id: str = "run_blc") -> PipelineState:
    ctx = PipelineState(
        chapter_url="https://example.com/c1",
        novel_id=novel_id,
        chapter_id="chapter_001",
        provider_key="mock",
        provider_model="mock-model",
    )
    ctx.metadata["translation_run_id"] = run_id
    ctx.metadata["source_language"] = "ja"
    ctx.metadata["target_language"] = "en"
    ctx.metadata["prompt_version"] = "translation_request_v1"
    ctx.metadata["progress"] = {}
    return ctx


def _cache_key(source_text: str) -> str:
    return make_cache_key(
        source_text,
        "ja",
        "en",
        _hash_text(""),
        provider_key="mock",
        provider_model="mock-model",
        prompt_version="translation_request_v1",
    )


def _seed_service_entry(svc: TranslationCacheService, chunk: TranslationChunk, translated_text: str) -> str:
    key = _cache_key(chunk.source_text)
    svc.set(
        key,
        CacheEntry(
            key=key,
            source_text=chunk.source_text,
            translated_text=translated_text,
            source_language="ja",
            target_language="en",
            glossary_hash=_hash_text(""),
            provider_key="mock",
            provider_model="mock-model",
            created_at=datetime.now(UTC).isoformat(),
            novel_id=chunk.novel_id,
            chunk_id=chunk.chunk_id,
        ),
    )
    return key


class AttemptCountingProvider:
    """Returns a distinct acceptable translation per provider call."""

    key = "mock"

    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.calls = 0

    def available_models(self) -> list[str]:
        return ["mock-model"]

    async def translate(self, prompt: str, model: str | None = None, request=None):
        index = min(self.calls, len(self.outputs) - 1)
        self.calls += 1
        return {"text": self.outputs[index], "metadata": {}}


class ScoreGrader:
    """Fake LLM QA grader returning scripted scores."""

    key = "grader"

    def __init__(self, scores: list[float]) -> None:
        self.scores = list(scores)

    async def translate(self, prompt: str, model: str | None = None, request=None):
        score = self.scores.pop(0) if self.scores else 1.0
        return {"text": json.dumps({"score": score}), "metadata": {}}


def _build_stage(fixture, cache_service: TranslationCacheService, provider: AttemptCountingProvider) -> TranslateStage:
    return TranslateStage(
        provider_factory=lambda key: provider,  # type: ignore[arg-type]
        cache=fixture.cache,
        cache_service=cache_service,
        settings_service=fixture.settings_service,
        usage_service=fixture.usage_service,
        storage=fixture.storage,
    )


class KeyedProvider:
    """Provider with a distinct key per instance (model identity)."""

    def __init__(self, key: str, outputs: list[str]) -> None:
        self.key = key
        self.outputs = list(outputs)
        self.calls = 0

    def available_models(self) -> list[str]:
        return [self.key]

    async def translate(self, prompt: str, model: str | None = None, request=None):
        index = min(self.calls, len(self.outputs) - 1)
        self.calls += 1
        return {"text": self.outputs[index], "metadata": {}}


@pytest.mark.asyncio
async def test_cross_model_rejected_attempt_never_enters_cache() -> None:
    """Section 9: model A attempt 1 is QA-rejected; model B attempt 2 is
    accepted. Exactly one provider call per model, two distinct cache keys,
    the rejected key absent, the accepted key present, exactly one final
    cache entry — driven through the real Translate/QA/Flush stages."""
    fixture = create_test_fixture()
    try:
        chunk = _chunk()
        svc = TranslationCacheService(cache_dir=fixture.data_dir / "cache")
        # Attempt 1 output is byte-identical to the source: deterministic QA
        # rejects it (translation_same_as_source). Attempt 2 is a clean
        # translation.
        provider_a = KeyedProvider("model_a", [chunk.source_text])
        provider_b = KeyedProvider("model_b", ["Chapter one.\n\nThe scene continues."])
        providers = {"model_a": provider_a, "model_b": provider_b}

        stage = TranslateStage(
            provider_factory=lambda key: providers[key],  # type: ignore[arg-type]
            cache=fixture.cache,
            cache_service=svc,
            settings_service=fixture.settings_service,
            usage_service=fixture.usage_service,
            storage=fixture.storage,
        )
        qa = TranslationQAStage(storage=fixture.storage)
        flush = CacheFlushStage(cache_service=svc)

        ctx = _context()
        ctx.translation_chunks = [chunk]
        ctx.provider_key = "model_a"
        ctx.provider_model = "model_a"

        # Attempt 1 (model A): translated, then QA rejects.
        res1 = await stage.run(ctx)
        assert provider_a.calls == 1
        with pytest.raises(TranslationQAError):
            res1 = await qa.run(res1)
        assert ctx.chunk_states[chunk.chunk_id]["status"] == "qa_failed"
        # The rejected attempt's pending entry was invalidated immediately.
        assert ctx.metadata["_pending_cache_entries"] == []
        rejected_key = ctx.chunk_states[chunk.chunk_id]["rejected_cache_keys"][0]
        assert rejected_key == make_cache_key(
            chunk.source_text,
            "ja",
            "en",
            _hash_text(""),
            provider_key="model_a",
            provider_model="model_a",
            prompt_version="translation_request_v1",
        )

        # Attempt 2 (model B): fresh request, QA accepts.
        ctx.provider_key = "model_b"
        ctx.provider_model = "model_b"
        res2 = await stage.run(ctx)
        assert provider_b.calls == 1
        res2 = await qa.run(res2)
        state = res2.chunk_states[chunk.chunk_id]
        assert state["status"] == "translated"
        assert state["accepted_attempt_number"] == 2
        assert state["accepted_provider_key"] == "model_b"
        assert state["accepted_cache_key"] != ctx.chunk_states[chunk.chunk_id]["rejected_cache_keys"][0]

        # Flush: only the accepted attempt's entry is written.
        await flush.run(res2)
        rejected_key = ctx.chunk_states[chunk.chunk_id]["rejected_cache_keys"][0]
        accepted_key = state["accepted_cache_key"]
        assert rejected_key != accepted_key
        assert svc.get(rejected_key) is None
        accepted = svc.get(accepted_key)
        assert accepted is not None
        assert accepted.translated_text == "Chapter one.\n\nThe scene continues."
        assert accepted.attempt_number == 2
        assert accepted.provider_key == "model_b"
        assert svc.stats()["total_entries"] == 1
        assert res2.metadata["progress"]["cache_flush_written"] == 1
        assert res2.metadata["progress"]["cache_flush_dropped"] == 0
    finally:
        fixture.cleanup()


@pytest.mark.asyncio
async def test_retry_marked_chunk_bypasses_both_caches_and_fetches_fresh() -> None:
    """needs_retry chunks never reuse output or read either cache: fresh request."""
    """needs_retry chunks never reuse output or read either cache: fresh request."""
    fixture = create_test_fixture()
    try:
        chunk = _chunk()
        svc = TranslationCacheService(cache_dir=fixture.data_dir / "cache")
        # Warm BOTH caches with stale (rejected) output for this exact chunk key.
        fixture.cache.set(chunk.source_text, "mock", "mock-model", "stale-legacy-output")
        _seed_service_entry(svc, chunk, "stale-service-output")
        # Persisted state from an older run says TRANSLATED — must not win over
        # the in-memory retry marker.
        fixture.storage.upsert_chunk_state(
            {
                "chunk_id": chunk.chunk_id,
                "novel_id": "novel1",
                "chapter_ids": list(chunk.chapter_ids),
                "paragraph_ids": list(chunk.paragraph_ids),
                "provider_key": "mock",
                "provider_model": "mock-model",
                "attempt_number": 1,
                "status": "translated",
                "translation_run_id": "run_blc",
            }
        )
        provider = AttemptCountingProvider(
            ["Chapter one.\n\nThe scene continues.", "Chapter one.\n\nThen the scene moves onward."]
        )
        stage = _build_stage(fixture, svc, provider)
        ctx = _context()
        ctx.translation_chunks = [chunk]
        ctx.chunk_states[chunk.chunk_id] = {
            "chunk_id": chunk.chunk_id,
            "novel_id": "novel1",
            "status": "needs_retry",
            "attempt_number": 1,
        }

        res = await stage.run(ctx)

        assert provider.calls == 1, "retry-marked chunk must issue a fresh provider request"
        assert res.translations[0] == "Chapter one.\n\nThe scene continues."
        state = res.chunk_states[chunk.chunk_id]
        assert state["status"] == "translated"
        assert state["attempt_number"] == 2
        # The legacy cache must not have been polluted with the fresh output
        # before QA (pre-QA writes removed).
        assert fixture.cache.get(chunk.source_text, "mock", "mock-model") == "stale-legacy-output"
        # Pending entry carries full provenance of the accepted attempt.
        pending = res.metadata["_pending_cache_entries"]
        assert len(pending) == 1
        _, entry = pending[0]
        assert entry.chunk_id == chunk.chunk_id
        assert entry.attempt_number == 2
        assert entry.translation_run_id == "run_blc"
        assert entry.output_hash == hash_text("Chapter one.\n\nThe scene continues.")
    finally:
        fixture.cleanup()


def test_persisted_translated_state_does_not_overwrite_in_memory_retry_marker() -> None:
    """A stored 'translated' state must never clobber an in-memory needs_retry marker."""
    fixture = create_test_fixture()
    try:
        chunk = _chunk()
        fixture.storage.upsert_chunk_state(
            {
                "chunk_id": chunk.chunk_id,
                "novel_id": "novel1",
                "chapter_ids": list(chunk.chapter_ids),
                "paragraph_ids": list(chunk.paragraph_ids),
                "provider_key": "mock",
                "provider_model": "old-model",
                "attempt_number": 3,
                "status": "translated",
                "translation_run_id": "run_blc",
            }
        )
        ctx = PipelineState(chapter_url="x", novel_id="novel1", chapter_id="chapter_001")
        ctx.metadata["translation_run_id"] = "run_blc"
        ctx.chunk_states[chunk.chunk_id] = {
            "chunk_id": chunk.chunk_id,
            "novel_id": "novel1",
            "status": "needs_retry",
        }

        load_persisted_chunk_states(fixture.storage, ctx)

        state = ctx.chunk_states[chunk.chunk_id]
        assert state["status"] == "needs_retry"
        # Non-status fields still merge from the persisted record.
        assert state["attempt_number"] == 3
        assert state["provider_model"] == "old-model"
    finally:
        fixture.cleanup()


@pytest.mark.asyncio
async def test_qa_stage_persists_failed_disposition() -> None:
    """QA dispositions are persisted so markers survive re-runs and restarts."""
    fixture = create_test_fixture()
    try:
        chunk = _chunk()
        ctx = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
        ctx.translation_chunks = [chunk]
        ctx.translations = [""]
        ctx.metadata["translation_run_id"] = "run_blc"
        ctx.chunk_states[chunk.chunk_id] = {
            "chunk_id": chunk.chunk_id,
            "novel_id": "novel1",
            "status": "translated",
        }

        with pytest.raises(TranslationQAError):
            await TranslationQAStage(storage=fixture.storage).run(ctx)

        states = fixture.storage.load_chunk_states(
            novel_id="novel1",
            chapter_id="chapter_001",
            translation_run_id="run_blc",
        )
        assert any(state.get("chunk_id") == chunk.chunk_id and state.get("status") == "qa_failed" for state in states)
    finally:
        fixture.cleanup()


@pytest.mark.asyncio
async def test_qa_stage_persists_needs_review_when_llm_policy_is_review(monkeypatch) -> None:
    """LLM policy 'review' persists needs_review (accepted-output-only markers)."""
    monkeypatch.setattr(settings, "LLM_QA_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_QA_POLICY", "review")
    monkeypatch.setattr(settings, "LLM_QA_MIN_SCORE", 0.99)
    fixture = create_test_fixture()
    try:
        chunk = _chunk()
        grader = ScoreGrader([0.1])
        monkeypatch.setattr("novelai.translation.pipeline.stages.translation_qa._resolve_llm_grader", lambda: grader)
        ctx = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
        ctx.translation_chunks = [chunk]
        ctx.translations = ["Chapter one.\n\nThe scene continues."]
        ctx.metadata["translation_run_id"] = "run_blc"
        ctx.chunk_states[chunk.chunk_id] = {
            "chunk_id": chunk.chunk_id,
            "novel_id": "novel1",
            "status": "translated",
        }

        await TranslationQAStage(storage=fixture.storage).run(ctx)

        assert ctx.chunk_states[chunk.chunk_id]["status"] == "needs_review"
        states = fixture.storage.load_chunk_states(
            novel_id="novel1",
            chapter_id="chapter_001",
            translation_run_id="run_blc",
        )
        assert any(
            state.get("chunk_id") == chunk.chunk_id and state.get("status") == "needs_review" for state in states
        )
    finally:
        fixture.cleanup()


@pytest.mark.asyncio
async def test_no_pre_qa_cache_write_and_flush_writes_only_after_acceptance() -> None:
    """No output reaches either cache before QA; flush persists the accepted entry."""
    fixture = create_test_fixture()
    try:
        chunk = _chunk()
        svc = TranslationCacheService(cache_dir=fixture.data_dir / "cache")
        provider = AttemptCountingProvider(["Chapter one.\n\nThe scene continues."])
        stage = _build_stage(fixture, svc, provider)
        ctx = _context()
        ctx.translation_chunks = [chunk]

        res = await stage.run(ctx)

        # Legacy simple cache has no entry and the sharded service has none:
        # TranslateStage defers all writes behind QA.
        assert fixture.cache.get(chunk.source_text, "mock", "mock-model") is None
        assert svc.stats()["total_entries"] == 0
        pending = res.metadata["_pending_cache_entries"]
        assert len(pending) == 1
        _, entry = pending[0]
        assert entry.chunk_id == chunk.chunk_id
        assert entry.attempt_number == 1
        assert entry.translation_run_id == "run_blc"
        assert entry.output_hash == hash_text(entry.translated_text)

        # After QA accepts (status translated + accepted tuple), flush writes
        # exactly the accepted entry.
        assert res.chunk_states[chunk.chunk_id]["status"] == "translated"
        res = await TranslationQAStage(storage=fixture.storage).run(res)
        assert res.chunk_states[chunk.chunk_id]["accepted_attempt_number"] == 1
        await CacheFlushStage(cache_service=svc).run(res)
        got = svc.get(entry.key)
        assert got is not None
        assert got.translated_text == entry.translated_text
        assert got.attempt_number == 1
        assert got.translation_run_id == "run_blc"
        assert got.output_hash == entry.output_hash
        assert res.metadata["_pending_cache_entries"] == []
    finally:
        fixture.cleanup()


@pytest.mark.asyncio
async def test_cache_flush_drops_rejected_entries_and_keeps_last_attempt() -> None:
    """Rejected entries are invalidated; retry duplicates are deduped (last attempt wins)."""
    fixture = create_test_fixture()
    try:
        svc = TranslationCacheService(cache_dir=fixture.data_dir / "cache")
        key = _cache_key("some text")

        def entry_for(translated_text: str, attempt: int) -> CacheEntry:
            return CacheEntry(
                key=key,
                source_text="some text",
                translated_text=translated_text,
                source_language="ja",
                target_language="en",
                glossary_hash=_hash_text(""),
                provider_key="mock",
                provider_model="mock-model",
                created_at=datetime.now(UTC).isoformat(),
                novel_id="novel1",
                chunk_id="c0001",
                attempt_number=attempt,
                translation_run_id="run_blc",
                output_hash=hash_text(translated_text),
            )

        # Rejected chunk: every pending entry is dropped, nothing is cached.
        ctx = PipelineState(chapter_url="x", novel_id="novel1", chapter_id="chapter_001")
        ctx.chunk_states["c0001"] = {"status": "needs_review"}
        ctx.metadata["_pending_cache_entries"] = [
            (key, entry_for("attempt-one", 1)),
            (key, entry_for("attempt-two", 2)),
        ]
        ctx.metadata["progress"] = {}
        await CacheFlushStage(cache_service=svc).run(ctx)
        assert svc.get(key) is None
        assert ctx.metadata["progress"]["cache_flush_dropped"] == 2

        # Accepted chunk: same key across attempts; only the exact
        # QA-accepted attempt (2) is flushed, attempt 1 is dropped.
        ctx2 = PipelineState(chapter_url="x", novel_id="novel1", chapter_id="chapter_001")
        ctx2.chunk_states["c0001"] = {
            "status": "translated",
            "qa_status": "passed",
            "accepted_attempt_number": 2,
            "accepted_provider_key": "mock",
            "accepted_provider_model": "mock-model",
            "accepted_cache_key": key,
            "accepted_output_hash": hash_text("attempt-two"),
        }
        ctx2.metadata["_pending_cache_entries"] = [
            (key, entry_for("attempt-one", 1)),
            (key, entry_for("attempt-two", 2)),
        ]
        ctx2.metadata["progress"] = {}
        await CacheFlushStage(cache_service=svc).run(ctx2)
        got = svc.get(key)
        assert got is not None
        assert got.translated_text == "attempt-two"
        assert got.attempt_number == 2
        assert ctx2.metadata["progress"]["cache_flush_dropped"] == 1
    finally:
        fixture.cleanup()


@pytest.mark.asyncio
async def test_pipeline_blocking_retry_refetches_and_caches_accepted_output_only(monkeypatch) -> None:
    """End-to-end: rejected attempt is re-fetched fresh, re-QA'd, and only the accepted output is cached."""
    monkeypatch.setattr(settings, "LLM_QA_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_QA_POLICY", "blocking_retry")
    monkeypatch.setattr(settings, "LLM_QA_MIN_SCORE", 0.99)
    monkeypatch.setattr(settings, "LLM_QA_MAX_RETRY_ATTEMPTS", 3)
    fixture = create_test_fixture()
    try:
        chunk = _chunk()
        grader = ScoreGrader([0.1, 1.0])
        monkeypatch.setattr("novelai.translation.pipeline.stages.translation_qa._resolve_llm_grader", lambda: grader)
        svc = TranslationCacheService(cache_dir=fixture.data_dir / "cache")
        provider = AttemptCountingProvider(
            ["Chapter one.\n\nThe scene continues.", "Chapter one.\n\nThen the scene moves onward."]
        )
        pipeline = TranslationPipeline(
            stages=[
                _build_stage(fixture, svc, provider),
                TranslationQAStage(storage=fixture.storage),
                CacheFlushStage(cache_service=svc),
            ]
        )
        ctx = _context()
        ctx.translation_chunks = [chunk]

        result = await pipeline.run(ctx)

        # Requirement 6: a fresh provider request was issued for the retried chunk.
        assert provider.calls == 2
        # Requirement 7: deterministic + LLM QA re-ran and accepted the fresh output.
        assert result.translations[0] == "Chapter one.\n\nThen the scene moves onward."
        state = result.chunk_states[chunk.chunk_id]
        assert state["status"] == "translated"
        assert state["llm_qa_retry_count"] == 1
        # Requirement 8: only the accepted output reaches the cache.
        entry = svc.get(_cache_key(chunk.source_text))
        assert entry is not None
        assert entry.translated_text == "Chapter one.\n\nThen the scene moves onward."
        assert entry.attempt_number == 2
        assert entry.output_hash == hash_text("Chapter one.\n\nThen the scene moves onward.")
        assert result.metadata["_pending_cache_entries"] == []
    finally:
        fixture.cleanup()


@pytest.mark.asyncio
async def test_pipeline_blocking_retry_marks_needs_review_when_budget_exhausted(monkeypatch) -> None:
    """Requirement 9: retry budget exhaustion leaves the chunk needs_review, never cached."""
    monkeypatch.setattr(settings, "LLM_QA_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_QA_POLICY", "blocking_retry")
    monkeypatch.setattr(settings, "LLM_QA_MIN_SCORE", 0.99)
    monkeypatch.setattr(settings, "LLM_QA_MAX_RETRY_ATTEMPTS", 1)
    fixture = create_test_fixture()
    try:
        chunk = _chunk()
        grader = ScoreGrader([0.1, 0.1])
        monkeypatch.setattr("novelai.translation.pipeline.stages.translation_qa._resolve_llm_grader", lambda: grader)
        svc = TranslationCacheService(cache_dir=fixture.data_dir / "cache")
        provider = AttemptCountingProvider(
            ["Chapter one.\n\nThe scene continues.", "Chapter one.\n\nThen the scene moves onward."]
        )
        pipeline = TranslationPipeline(
            stages=[
                _build_stage(fixture, svc, provider),
                TranslationQAStage(storage=fixture.storage),
                CacheFlushStage(cache_service=svc),
            ]
        )
        ctx = _context()
        ctx.translation_chunks = [chunk]

        result = await pipeline.run(ctx)

        assert provider.calls == 2
        state = result.chunk_states[chunk.chunk_id]
        assert state["status"] == "needs_review"
        assert svc.get(_cache_key(chunk.source_text)) is None
        assert result.metadata["_pending_cache_entries"] == []
    finally:
        fixture.cleanup()

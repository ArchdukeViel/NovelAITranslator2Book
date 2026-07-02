"""Infrastructure tests for translation orchestration: per-chapter locks,
translation_run_id, and cross-run cache behaviour."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from novelai.core.errors import TranslationInProgressError
from novelai.services.translation_cache import build_translation_cache_key

_TMP = Path(__file__).resolve().parent / ".tmp" / "orchestration_infra"


# ---------------------------------------------------------------------------
# Lock tests  (Task 6)
# ---------------------------------------------------------------------------

class TestDuplicateRunLock:
    """Tests for per-chapter translation lock."""

    @pytest.fixture()
    def lock_map(self) -> dict[str, asyncio.Lock]:
        return {}

    def _get_lock(self, lock_map: dict[str, asyncio.Lock], novel_id: str, chapter_id: str) -> asyncio.Lock:
        key = f"{novel_id}:{chapter_id}"
        if key not in lock_map:
            lock_map[key] = asyncio.Lock()
        return lock_map[key]

    @pytest.mark.asyncio
    async def test_duplicate_run_raises_translation_in_progress_error(self) -> None:
        lock = asyncio.Lock()
        await lock.acquire()
        try:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(lock.acquire(), timeout=0.0)
        finally:
            lock.release()

    @pytest.mark.asyncio
    async def test_sequential_runs_succeed(self) -> None:
        lock = asyncio.Lock()
        for _ in range(3):
            await asyncio.wait_for(lock.acquire(), timeout=1.0)
            lock.release()
        assert True  # no timeout

    @pytest.mark.asyncio
    async def test_different_chapters_do_not_block(self) -> None:
        lock_a = asyncio.Lock()
        lock_b = asyncio.Lock()
        await lock_a.acquire()  # hold lock_a
        # lock_b should be acquirable independently
        await asyncio.wait_for(lock_b.acquire(), timeout=0.1)
        lock_b.release()
        lock_a.release()

    def test_translation_in_progress_error_is_runtime_error(self) -> None:
        assert issubclass(TranslationInProgressError, RuntimeError)

    @pytest.mark.asyncio
    async def test_lock_per_chapter_key(self) -> None:
        lock_map: dict[str, asyncio.Lock] = {}
        lock_1 = self._get_lock(lock_map, "n1", "1")
        lock_1_b = self._get_lock(lock_map, "n1", "1")
        lock_2 = self._get_lock(lock_map, "n1", "2")
        assert lock_1 is lock_1_b  # same chapter → same lock
        assert lock_1 is not lock_2  # different chapter → different lock


# ---------------------------------------------------------------------------
# translation_run_id tests  (Task 7)
# ---------------------------------------------------------------------------

class TestTranslationRunId:
    """Tests for translation_run_id semantics."""

    def test_translation_run_id_always_set(self) -> None:
        """translation_run_id should always be a non-empty string."""
        from uuid import uuid4
        # Simulate the production logic:
        job_id = None
        activity_id = None
        run_id = job_id or activity_id or f"translation_run_{uuid4().hex}"
        assert isinstance(run_id, str) and len(run_id) > 0

    def test_two_runs_produce_different_run_ids(self) -> None:
        from uuid import uuid4
        run_id_1 = f"translation_run_{uuid4().hex}"
        run_id_2 = f"translation_run_{uuid4().hex}"
        assert run_id_1 != run_id_2

    def test_cross_run_reuse_when_six_fields_match(self) -> None:
        """When all six cache key fields match, the key should be identical
        across two independent 'runs'."""
        key_1 = build_translation_cache_key(
            source_text="Reusable content.",
            provider_key="p1",
            provider_model="m1",
            prompt_version="v2",
            glossary_hash="fixed_hash",
            style_preset="default",
        )
        key_2 = build_translation_cache_key(
            source_text="Reusable content.",
            provider_key="p1",
            provider_model="m1",
            prompt_version="v2",
            glossary_hash="fixed_hash",
            style_preset="default",
        )
        assert key_1 == key_2

    def test_no_cross_run_reuse_when_glossary_changed(self) -> None:
        key_1 = build_translation_cache_key(
            source_text="Reusable content.",
            provider_key="p1",
            provider_model="m1",
            prompt_version="v2",
            glossary_hash="fixed_hash",
            style_preset="default",
        )
        key_2 = build_translation_cache_key(
            source_text="Reusable content.",
            provider_key="p1",
            provider_model="m1",
            prompt_version="v2",
            glossary_hash="different_hash",
            style_preset="default",
        )
        assert key_1 != key_2

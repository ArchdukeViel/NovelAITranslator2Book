# F811: pytest fixture `orchestration_env` imported at module scope shadows the same name as a
#       parameter on many test functions - this is the standard pytest pattern.
# F821: module-level test helpers (_s6_orchestrator, etc.) are referenced before their definition
#       within this file; Python resolves them at test-call time after module-level definitions run.
from __future__ import annotations

import json
import re
from typing import Any
from unittest.mock import patch

import pytest

from novelai.config.settings import GEMINI_DEFAULT_MODEL, settings
from novelai.core.chapter_state import ChapterState
from novelai.core.errors import ProviderConfigError, ProviderErrorCode
from novelai.db.models.novel import Novel
from novelai.providers.base import TranslationProvider
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCacheService
from novelai.storage.service import StorageService
from novelai.translation.pipeline.context import paragraph_source_hash
from novelai.translation.pipeline.pipeline import TranslationPipeline
from novelai.translation.pipeline.stages.cache_flush import CacheFlushStage
from novelai.translation.pipeline.stages.fetch import FetchStage
from novelai.translation.pipeline.stages.parse import ParseStage
from novelai.translation.pipeline.stages.post_process import PostProcessStage
from novelai.translation.pipeline.stages.segment import SmartSegmentStage
from novelai.translation.pipeline.stages.translate import TranslateStage
from novelai.translation.pipeline.stages.translation_qa import TranslationQAStage
from novelai.translation.service import TranslationService
from tests.conftest import MockTranslationProvider
from tests.test_novel_orchestration_service import (
    GlossarySchemaCaptureProvider,
    MarkerAwareStubTranslationService,
    StubSource,
    StubTranslationService,
    UnusedTranslationService,
    _run_delta_translate,
    _s6_orchestrator,
    _save_delta_execution_fixture,
)


@pytest.mark.asyncio
async def test_translate_chapters_preflight_blocks_when_nothing_to_translate(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_translated_chapter(
        "novel-1", "1", "already translated", provider_key="mock", provider_model="mock-1.0"
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with pytest.raises(RuntimeError, match="nothing_to_translate"):
        await orchestrator.translate_chapters("stub", "novel-1", "1")


@pytest.mark.asyncio
async def test_extract_glossary_llm_mode_enforces_json_schema(orchestration_env) -> None:
    provider = GlossarySchemaCaptureProvider()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-llm",
        {
            "title": "Glossary LLM Novel",
            "source_language": "Japanese",
            "input_adapter_key": "web",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-llm/1"},
            ],
        },
    )
    storage.save_chapter("novel-llm", "1", "魔導具は王都で使われる。")

    settings = orchestration_env["settings"]
    settings.set_llm_step_config(
        "glossary_extraction",
        provider_key="mock",
        provider_model="mock-1.0",
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=settings,
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.extract_glossary_terms(
        "novel-llm",
        config={
            "mode": "llm",
            "provider": "mock",
            "model": "mock-1.0",
        },
    )

    assert summary["config"]["mode"] == "llm"
    assert summary["config"]["llm_candidates"] == 2
    json_schema = provider.last_kwargs.get("json_schema")
    assert isinstance(json_schema, dict)
    assert json_schema.get("required") == ["terms"]
    assert "terms" in (json_schema.get("properties") or {})

    glossary = storage.load_glossary("novel-llm")
    sources = {str(entry.get("source")) for entry in glossary if isinstance(entry, dict)}
    assert "魔導具" in sources
    assert "王都" in sources


@pytest.mark.asyncio
async def test_translate_chapters_attempts_checkpoint_restore_after_error_state(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "raw text", source_key="stub", source_url="https://example.com/novel-1/1")
    storage.update_chapter_state("novel-1", "1", ChapterState.SEGMENTED, error="old failure")
    storage.create_checkpoint("novel-1", "1", "resume")

    restore_calls: list[tuple[str, str, str]] = []
    original_restore = storage.restore_from_checkpoint

    def _tracking_restore(novel_id: str, chapter_id: str, checkpoint_name: str) -> bool:
        restore_calls.append((novel_id, chapter_id, checkpoint_name))
        return original_restore(novel_id, chapter_id, checkpoint_name)

    storage.restore_from_checkpoint = _tracking_restore  # type: ignore[method-assign]

    translation = StubTranslationService(final_text="translated ok")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with patch(
        "novelai.services.novel_orchestration_service.safely_refresh_catalog_projection_after_storage_write"
    ) as refresh_projection:
        await orchestrator.translate_chapters("stub", "novel-1", "1", force=True)

    assert restore_calls
    assert restore_calls[-1] == ("novel-1", "1", "resume")
    refresh_projection.assert_called_once_with(
        "novel-1",
        storage,
        context="checkpoint_restore",
    )
    translated = storage.load_translated_chapter("novel-1", "1")
    assert translated is not None
    assert translated["text"] == "translated ok"


@pytest.mark.asyncio
async def test_translate_chapters_preflight_blocks_pending_glossary_terms(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_glossary(
        "novel-1",
        [{"source": "英雄", "target": "hero", "status": "pending", "locked": True}],
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with pytest.raises(RuntimeError, match="pending_glossary_terms"):
        await orchestrator.translate_chapters("stub", "novel-1", "1")


@pytest.mark.asyncio
async def test_translate_chapters_preflight_blocks_pending_db_glossary_status(orchestration_env) -> None:
    source = StubSource()
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "glossary-gate",
        {
            "title": "Glossary Gate",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/glossary-gate/1"},
            ],
        },
    )
    with SessionLocal() as session:
        novel = Novel(slug="glossary-gate", title="Glossary Gate", language="ja", publication_status="ongoing")
        session.add(novel)
        session.flush()
        GlossaryRepository(session).create_glossary_entry(
            novel_id=novel.id,
            canonical_term="Pocott",
            term_type="place",
            status="candidate",
        )
        session.commit()

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with pytest.raises(RuntimeError, match="glossary_gate_pending"):
        await orchestrator.translate_chapters("stub", "glossary-gate", "1")


@pytest.mark.asyncio
async def test_translate_chapters_allows_ready_status_and_skip_override(orchestration_env) -> None:
    source = StubSource()
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    for novel_id in ("glossary-ready", "glossary-override"):
        storage.save_metadata(
            novel_id,
            {
                "title": novel_id,
                "source_language": "Japanese",
                "onboarding_status": "ready_for_translation",
                "chapters": [
                    {"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{novel_id}/1"},
                ],
            },
        )
    with SessionLocal() as session:
        session.add(
            Novel(
                slug="glossary-ready",
                title="Glossary Ready",
                language="ja",
                publication_status="ongoing",
                glossary_status="glossary_ready",
            )
        )
        session.add(
            Novel(
                slug="glossary-override",
                title="Glossary Override",
                language="ja",
                publication_status="ongoing",
                glossary_status="glossary_pending",
            )
        )
        session.commit()

    translation = StubTranslationService(final_text="translated ok")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "glossary-ready", "1")
    await orchestrator.translate_chapters("stub", "glossary-override", "1", skip_glossary_gate=True)

    assert [call["novel_id"] for call in translation.calls] == ["glossary-ready", "glossary-override"]


@pytest.mark.asyncio
async def test_translate_chapters_preflight_blocks_missing_ocr_review(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "raw text", source_key="stub", source_url="https://example.com/novel-1/1")
    storage.save_chapter_media_state(
        "novel-1",
        "1",
        ocr_required=True,
        ocr_text="OCR text",
        ocr_status="pending",
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with pytest.raises(RuntimeError, match="missing_ocr_review"):
        await orchestrator.translate_chapters("stub", "novel-1", "1")


@pytest.mark.asyncio
async def test_translate_chapters_allows_when_ocr_reviewed(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "raw text", source_key="stub", source_url="https://example.com/novel-1/1")
    storage.save_chapter_media_state(
        "novel-1",
        "1",
        ocr_required=True,
        ocr_text="Corrected OCR text",
        ocr_status="reviewed",
    )

    translation = StubTranslationService(final_text="translated ok")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "novel-1", "1")

    translated = storage.load_translated_chapter("novel-1", "1")
    assert translated is not None
    assert translated["text"] == "translated ok"


@pytest.mark.asyncio
async def test_retranslate_chapter_forces_single_chapter_translation(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
                {"id": "2", "num": 2, "title": "Chapter Two", "url": "https://example.com/novel-1/2"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "raw text 1", source_key="stub", source_url="https://example.com/novel-1/1")
    storage.save_chapter("novel-1", "2", "raw text 2", source_key="stub", source_url="https://example.com/novel-1/2")
    storage.save_translated_chapter("novel-1", "1", "old translation", provider_key="mock", provider_model="mock-1.0")

    translation = StubTranslationService(final_text="new translation")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.retranslate_chapter("stub", "novel-1", "1")

    assert len(translation.calls) == 1
    assert str(translation.calls[0].get("chapter_url")) == "https://example.com/novel-1/1"
    translated_1 = storage.load_translated_chapter("novel-1", "1")
    translated_2 = storage.load_translated_chapter("novel-1", "2")
    assert translated_1 is not None
    assert translated_1["text"] == "new translation"
    assert translated_2 is None


@pytest.mark.asyncio
async def test_ingest_ocr_candidates_updates_media_state_from_images(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter(
        "novel-1",
        "1",
        "Body text",
        source_key="stub",
        source_url="https://example.com/novel-1/1",
        images=[
            {
                "index": 0,
                "placeholder": "[Image: inscription]",
                "original_url": "https://assets.example.com/inscription.jpg",
                "alt": "Ancient inscription",
            }
        ],
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.ingest_ocr_candidates("novel-1", "1")

    assert summary["selected"] == 1
    assert summary["updated"] == 1
    assert summary["skipped_no_images"] == 0
    assert summary["skipped_reviewed"] == 0
    assert summary["failed"] == []

    media = storage.load_chapter_media_state("novel-1", "1")
    assert media is not None
    assert media["ocr_required"] is True
    assert media["ocr_status"] == "pending"
    assert isinstance(media["ocr_text"], str)
    assert "Ancient inscription" in media["ocr_text"]


@pytest.mark.asyncio
async def test_ingest_ocr_candidates_skips_reviewed_when_not_overwriting(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter(
        "novel-1",
        "1",
        "Body text",
        source_key="stub",
        source_url="https://example.com/novel-1/1",
        images=[
            {
                "index": 0,
                "placeholder": "[Image: inscription]",
                "original_url": "https://assets.example.com/inscription.jpg",
                "alt": "Ancient inscription",
            }
        ],
    )
    storage.save_chapter_media_state(
        "novel-1",
        "1",
        ocr_required=True,
        ocr_text="Hand reviewed OCR",
        ocr_status="reviewed",
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.ingest_ocr_candidates("novel-1", "1", overwrite=False)

    assert summary["selected"] == 1
    assert summary["updated"] == 0
    assert summary["skipped_reviewed"] == 1

    media = storage.load_chapter_media_state("novel-1", "1")
    assert media is not None
    assert media["ocr_status"] == "reviewed"
    assert media["ocr_text"] == "Hand reviewed OCR"


@pytest.mark.asyncio
async def test_ingest_ocr_candidates_skips_chapter_without_images(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "Body text", source_key="stub", source_url="https://example.com/novel-1/1")

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.ingest_ocr_candidates("novel-1", "1")

    assert summary["selected"] == 1
    assert summary["updated"] == 0
    assert summary["skipped_no_images"] == 1

    media = storage.load_chapter_media_state("novel-1", "1")
    assert media is not None
    assert media["ocr_required"] is False
    assert media["ocr_status"] == "skipped"


@pytest.mark.asyncio
async def test_review_glossary_terms_auto_approves_translated_targets(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata("novel-1", {"title": "Original", "chapters": []})
    storage.save_glossary(
        "novel-1",
        [
            {"source": "勇者", "target": "hero", "status": "pending", "locked": True, "confidence": 0.9},
            {"source": "魔王", "target": "", "status": "pending", "locked": True},
        ],
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.review_glossary_terms("novel-1")

    assert summary["approved"] == 1
    assert summary["pending"] == 1
    entries = storage.load_glossary("novel-1")
    by_source = {str(item.get("source")): item for item in entries if isinstance(item, dict)}
    assert by_source["勇者"]["status"] == "approved"
    assert by_source["魔王"]["status"] == "pending"


@pytest.mark.asyncio
async def test_translate_chapters_persists_confidence_metadata(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "raw text", source_key="stub", source_url="https://example.com/novel-1/1")

    translation = StubTranslationService(final_text="raw text")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "novel-1", "1", confidence_threshold=0.55)

    assert storage.load_translated_chapter("novel-1", "1") is None
    versions = storage.list_translated_chapter_versions("novel-1", "1")
    assert len(versions) == 1
    assert versions[0]["active"] is False
    assert isinstance(versions[0].get("confidence_score"), float)
    assert versions[0].get("polish_needed") is True
    assert isinstance(versions[0].get("confidence_details"), dict)


@pytest.mark.asyncio
async def test_pipeline_phase_two_blocks_when_pending_glossary(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "raw text", source_key="stub", source_url="https://example.com/novel-1/1")
    storage.save_glossary("novel-1", [{"source": "勇者", "target": "hero", "status": "pending", "locked": True}])

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(final_text="translated"),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    summary = await orchestrator.run_phased_translation_pipeline(
        source_key="stub",
        novel_id="novel-1",
        chapters="1",
        phase="2",
    )

    assert summary["status"] == "blocked"
    assert summary["blocked"] is True


# ---------------------------------------------------------------------------
# S6 — resume-path validity (REQ-3.1) and delta-path output-contract parity
# ---------------------------------------------------------------------------
#
# With ``TRANSLATION_DELTA_RETRANSLATION_ENABLED`` at its default ``True`` the
# resume gate (``_check_chapter_resume_state``) skips its ``is_translation_valid``
# branch and the delta retranslation path decides reuse vs. retranslation. The
# delta path now mirrors the gate's output-shaping contract (style preset,
# consistency mode, JSON output, honorific policy) and the Section 8 generation
# provenance requirement, so a change to any of those dimensions invalidates a
# previously-stored whole-chapter translation instead of silently reusing it.
#
# Tests run the real ``translate_chapters`` path twice with a counting stub and
# assert the provider was/was not called (no ``is_translation_valid`` patching).
# Gate-level tests additionally exercise ``_check_chapter_resume_state`` with
# delta retranslation disabled, where the validity branch is the production
# reuse decision.


def _s6_stage_commit_generation(storage: StorageService, generation_id: str) -> None:
    """Stage a single-chapter generation with the minimal calls commit_generation
    requires (mirrors the pr41 dispositions helper) and activate it."""
    # Use the existing raw chapter text so paragraph hashes are unchanged.
    raw_chapter = storage.load_chapter("novel-delta", "1") or {}
    raw_text = raw_chapter.get("text", "raw 1")
    storage.create_generation_stage(
        "novel-delta",
        generation_id,
        source_key="stub",
        source_work_id="novel-delta",
        mode="update",
        expected_chapters=1,
    )
    storage.stage_generation_metadata(
        "novel-delta",
        generation_id,
        {
            "title": "T",
            "source_novel_id": "novel-delta",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-delta/1"}],
        },
    )
    storage.stage_generation_source_state(
        "novel-delta",
        generation_id,
        {"chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-delta/1"}]},
    )
    storage.stage_generation_chapter_index(
        "novel-delta",
        generation_id,
        [{"id": "1", "chapter_id": "1", "title": "C1", "url": "https://example.com/novel-delta/1"}],
    )
    storage.stage_generation_chapter("novel-delta", generation_id, "1", {"id": "1", "raw": {"text": raw_text}})
    storage.commit_generation("novel-delta", generation_id, chapter_dispositions={"1": "fetched_new"})


def _s6_legacy_seed(storage: StorageService, *, paragraphs: list[str], translated_text: str) -> None:
    """Seed a pre-S4 legacy translation version with NO output-shaping lineage,
    so validity must fail closed. Structured paragraph chunks are present so the
    delta path does not bail on ``missing_lineage`` before the contract check."""
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-delta/1"}],
        },
    )
    storage.save_chapter("novel-delta", "1", "\n\n".join(paragraphs))
    lineage = [
        {
            "chapter_id": "1",
            "paragraph_id": f"p{index:04d}",
            "paragraph_index": index,
            "source_hash": paragraph_source_hash(text),
            "char_count": len(text),
        }
        for index, text in enumerate(paragraphs, start=1)
    ]
    storage.save_translation_chunks(
        "novel-delta",
        [
            {
                "chunk_id": "c0001",
                "chapter_ids": ["1"],
                "paragraph_ids": [item["paragraph_id"] for item in lineage],
                "paragraph_hashes": [item["source_hash"] for item in lineage],
                "paragraph_lineage": lineage,
                "source_text": "\n\n".join(paragraphs),
                "status": "translated",
            }
        ],
    )
    # Deliberately NO lineage kwargs: legacy record (no style/consistency/json/
    # honorific/raw_generation_id stored).
    storage.save_translated_chapter("novel-delta", "1", translated_text, provider_key="mock", provider_model="mock-1.0")


def _s6_gate_contract_kwargs(
    storage: StorageService,
    *,
    style_preset: str | None = None,
    consistency_mode: bool | None = False,
    json_output: bool | None = False,
    honorific_policy: str | None = "contextual",
    active_raw_generation_id: str | None = None,
    qa_policy_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Build the exact effective-contract kwargs translate_chapters passes to
    _check_chapter_resume_state, computed from storage so hashes match the
    stored lineage written by _translation_lineage_kwargs."""
    from novelai.glossary import canonical_glossary_hash as _gate_canonical_glossary_hash
    from novelai.services.orchestration.translation import _qa_policy_fingerprint as _gate_qa_fp
    from novelai.services.orchestration.translation import _resolve_effective_prompt_version as _gate_prompt_ver

    raw_chapter = storage.load_chapter("novel-delta", "1") or {}
    current_raw_text = raw_chapter.get("text") if isinstance(raw_chapter.get("text"), str) else ""
    current_source_text_hash = storage._hash_text(current_raw_text) if current_raw_text else ""
    current_source_structure_hash = storage._hash_text(
        json.dumps(raw_chapter.get("source_blocks") or [], ensure_ascii=False, sort_keys=True, default=str)
    )
    current_source_image_manifest_hash = storage._hash_text(
        json.dumps(raw_chapter.get("images") or [], ensure_ascii=False, sort_keys=True, default=str)
    )
    gate_prompt_version = _gate_prompt_ver(storage, storage.load_metadata("novel-delta") or {})
    return {
        "source_text_hash": current_source_text_hash,
        "effective_glossary_hash": _gate_canonical_glossary_hash(None),
        "prompt_template_version": gate_prompt_version,
        "provider_key": "mock",
        "provider_model": "mock-1.0",
        "active_raw_generation_id": active_raw_generation_id,
        "source_structure_hash": current_source_structure_hash,
        "source_image_manifest_hash": current_source_image_manifest_hash,
        "qa_policy_fingerprint": (
            _gate_qa_fp(prompt_template_version=gate_prompt_version)
            if qa_policy_fingerprint is None
            else qa_policy_fingerprint
        ),
        "source_language": "Japanese",
        "target_language": "English",
        "style_preset": style_preset,
        "consistency_mode": consistency_mode,
        "json_output": json_output,
        "honorific_policy": honorific_policy,
    }


@pytest.mark.asyncio
async def test_s6_unchanged_contract_reuses_without_provider_call(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old whole chapter",
        structured=False,
    )
    translation = StubTranslationService(final_text="should not be called")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = orchestration_env["storage"].load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "old whole chapter"
    assert translation.calls == []
    # Section 6: true no-op — reuse records no new version.
    versions = orchestration_env["storage"].list_translated_chapter_versions("novel-delta", "1")
    assert len(versions) == 1
    assert saved["version_id"] == versions[0]["version_id"]


@pytest.mark.asyncio
async def test_s6_style_preset_change_retranslates(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old literary text",
        translated_chapter_lineage_overrides={"style_preset": "literary"},
        structured=False,
    )
    translation = StubTranslationService(final_text="new casual text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        style_preset="casual",
    )

    saved = orchestration_env["storage"].load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new casual text"
    assert len(translation.calls) == 1
    assert translation.calls[0]["style_preset"] == "casual"
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"


@pytest.mark.asyncio
async def test_s6_consistency_mode_change_retranslates(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old consistent text",
        translated_chapter_lineage_overrides={"consistency_mode": True},
        structured=False,
    )
    translation = StubTranslationService(final_text="new standalone text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        consistency_mode=False,
    )

    saved = orchestration_env["storage"].load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new standalone text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"


@pytest.mark.asyncio
async def test_s6_honorific_policy_change_retranslates(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old honorific text",
        translated_chapter_lineage_overrides={"honorific_policy": "default_honorifics"},
        structured=False,
    )
    translation = StubTranslationService(final_text="new no-honorific text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        honorific_policy="none",
    )

    saved = orchestration_env["storage"].load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new no-honorific text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"


@pytest.mark.asyncio
async def test_s6_missing_lineage_field_retranslates(orchestration_env) -> None:
    _s6_legacy_seed(
        orchestration_env["storage"],
        paragraphs=["A.", "B."],
        translated_text="legacy whole chapter",
    )
    translation = StubTranslationService(final_text="fresh full text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = orchestration_env["storage"].load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "fresh full text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"


@pytest.mark.asyncio
async def test_s6_generation_change_identical_source_reuses(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="gen-a translation",
        translated_chapter_lineage_overrides={"raw_generation_id": "gen-a"},
        structured=False,
    )
    _s6_stage_commit_generation(storage, "gen-b")
    assert storage.resolve_active_generation_id("novel-delta") == "gen-b"

    translation = StubTranslationService(final_text="should not be called")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "gen-a translation"  # provenance-only: gen changed, source identical
    assert translation.calls == []
    # Section 6: true no-op — the reuse never creates a new version.
    versions = storage.list_translated_chapter_versions("novel-delta", "1")
    assert len(versions) == 1
    assert saved["version_id"] == versions[0]["version_id"]
    assert saved["raw_generation_id"] == "gen-a"


@pytest.mark.asyncio
async def test_s6_changed_source_text_retranslates_delta_window(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "B.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole",
        translated_chapter_lineage_overrides=None,
        structured=True,
    )
    # Change the novel-root raw text so paragraph B differs.
    storage.save_chapter("novel-delta", "1", "A.\n\nBee.\n\nC.")
    translation = StubTranslationService(paragraph_prefix="new:")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["mode"] == "delta"


@pytest.mark.asyncio
async def test_s6_history_retained_after_retranslation(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="literary chapter",
        translated_chapter_lineage_overrides={"style_preset": "literary"},
        structured=False,
    )
    versions_before = storage.list_translated_chapter_versions("novel-delta", "1")
    assert len(versions_before) == 1
    assert versions_before[0]["text"] == "literary chapter"

    translation = StubTranslationService(final_text="casual chapter")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        style_preset="casual",
    )

    versions_after = storage.list_translated_chapter_versions("novel-delta", "1")
    assert len(versions_after) == 2
    # The prior version survives with its old (literary) text.
    prior = [v for v in versions_after if not v["active"]]
    assert len(prior) == 1
    assert prior[0]["text"] == "literary chapter"
    active = [v for v in versions_after if v["active"]]
    assert len(active) == 1
    assert active[0]["text"] == "casual chapter"


# Gate-level tests: delta retranslation disabled so the resume gate's
# ``is_translation_valid`` branch is the production reuse decision.


@pytest.mark.asyncio
async def test_s6_gate_valid_contract_skips(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="valid text",
        translated_chapter_lineage_overrides=None,
        structured=False,
    )
    orchestrator = _s6_orchestrator(orchestration_env, StubTranslationService())

    from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

    result = _check_chapter_resume_state(
        orchestrator,
        novel_id="novel-delta",
        chapter_id="1",
        force=False,
        **_s6_gate_contract_kwargs(storage),
    )
    assert result is not None
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_s6_gate_style_change_retranslates(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="literary text",
        translated_chapter_lineage_overrides={"style_preset": "literary"},
        structured=False,
    )
    orchestrator = _s6_orchestrator(orchestration_env, StubTranslationService())

    from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

    kwargs = _s6_gate_contract_kwargs(storage, style_preset="casual")
    result = _check_chapter_resume_state(orchestrator, novel_id="novel-delta", chapter_id="1", force=False, **kwargs)
    assert result is None


@pytest.mark.asyncio
async def test_s6_gate_consistency_change_retranslates(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="consistent text",
        translated_chapter_lineage_overrides={"consistency_mode": True},
        structured=False,
    )
    orchestrator = _s6_orchestrator(orchestration_env, StubTranslationService())

    from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

    kwargs = _s6_gate_contract_kwargs(storage, consistency_mode=False)
    result = _check_chapter_resume_state(orchestrator, novel_id="novel-delta", chapter_id="1", force=False, **kwargs)
    assert result is None


@pytest.mark.asyncio
async def test_s6_gate_honorific_change_retranslates(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="honorific text",
        translated_chapter_lineage_overrides={"honorific_policy": "default_honorifics"},
        structured=False,
    )
    orchestrator = _s6_orchestrator(orchestration_env, StubTranslationService())

    from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

    kwargs = _s6_gate_contract_kwargs(storage, honorific_policy="none")
    result = _check_chapter_resume_state(orchestrator, novel_id="novel-delta", chapter_id="1", force=False, **kwargs)
    assert result is None


@pytest.mark.asyncio
async def test_s6_gate_missing_lineage_field_fails_closed(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    _s6_legacy_seed(storage, paragraphs=["A.", "B."], translated_text="legacy text")
    orchestrator = _s6_orchestrator(orchestration_env, StubTranslationService())

    from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

    kwargs = _s6_gate_contract_kwargs(storage, qa_policy_fingerprint="")
    result = _check_chapter_resume_state(orchestrator, novel_id="novel-delta", chapter_id="1", force=False, **kwargs)
    assert result is None


@pytest.mark.asyncio
async def test_s6_gate_generation_identical_source_skips_provenance_only(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="gen-a text",
        translated_chapter_lineage_overrides={"raw_generation_id": "gen-a"},
        structured=False,
    )
    _s6_stage_commit_generation(storage, "gen-b")
    assert storage.resolve_active_generation_id("novel-delta") == "gen-b"
    orchestrator = _s6_orchestrator(orchestration_env, StubTranslationService())

    from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

    kwargs = _s6_gate_contract_kwargs(storage, active_raw_generation_id="gen-b")
    result = _check_chapter_resume_state(orchestrator, novel_id="novel-delta", chapter_id="1", force=False, **kwargs)
    # Provenance-only: raw_generation_id differs (gen-a stored vs gen-b active)
    # but source hash is identical — valid, so skip.
    assert result is not None
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_s6_gate_changed_source_hash_retranslates(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="gen-a text",
        translated_chapter_lineage_overrides={"raw_generation_id": "gen-a"},
        structured=False,
    )
    # Mutate the novel-root raw text AFTER seeding so the stored source_hash
    # no longer matches the current chapter content.
    storage.save_chapter("novel-delta", "1", "A.\n\nBee.\n\nC.")
    orchestrator = _s6_orchestrator(orchestration_env, StubTranslationService())

    from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

    kwargs = _s6_gate_contract_kwargs(storage, active_raw_generation_id="gen-a")
    result = _check_chapter_resume_state(orchestrator, novel_id="novel-delta", chapter_id="1", force=False, **kwargs)
    assert result is None


# ---------------------------------------------------------------------------
# PR-41 Final contract closure: production-path delta reuse matrix
# ---------------------------------------------------------------------------
# These tests use the real translate_chapters() entry point with a counting
# translation stub. They prove delta reuse bails (and provider is called)
# whenever the global translation contract changes, and only source-only
# changes (under an identical global contract) can use paragraph-level delta.


@pytest.mark.asyncio
async def test_pr41_delta_target_language_change_calls_provider(orchestration_env) -> None:
    """Case 2: target language English -> Indonesian forces full translation."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="english chapter",
        translated_chapter_lineage_overrides={"target_language": "English"},
        structured=False,
    )
    translation = StubTranslationService(final_text="indonesian chapter")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        target_language="Indonesian",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "indonesian chapter"
    assert len(translation.calls) > 0


@pytest.mark.asyncio
async def test_pr41_delta_glossary_hash_change_calls_provider(orchestration_env) -> None:
    """Case 3: glossary hash changes -> provider called, full translation."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="gloss-v1 text",
        translated_chapter_lineage_overrides={"glossary_hash": "gloss-v1"},
        structured=False,
    )
    # Override metadata glossary_hash so _translation_lineage_kwargs writes new value.
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "stub",
            "source_language": "Japanese",
            "glossary_hash": "gloss-v2",
            "chapters": [{"id": "1", "num": 1, "title": "C1", "url": "u"}],
        },
    )
    translation = StubTranslationService(final_text="gloss-v2 text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "gloss-v2 text"
    assert len(translation.calls) > 0


@pytest.mark.asyncio
async def test_pr41_delta_provider_change_calls_provider(orchestration_env) -> None:
    """Case 6: provider change -> provider called, full translation."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="mock text",
        translated_chapter_lineage_overrides={"provider_key": "mock"},
        structured=False,
    )
    translation = StubTranslationService(final_text="other-provider text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="other-provider",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "other-provider text"
    assert len(translation.calls) > 0


@pytest.mark.asyncio
async def test_pr41_delta_style_change_default_to_literary_calls_provider(orchestration_env) -> None:
    """Case 9: default style -> literary -> provider called."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="default style text",
        translated_chapter_lineage_overrides={"style_preset": None},
        structured=False,
    )
    translation = StubTranslationService(final_text="literary text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        style_preset="literary",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "literary text"
    assert len(translation.calls) > 0


@pytest.mark.asyncio
async def test_pr41_delta_style_change_literary_to_default_calls_provider(orchestration_env) -> None:
    """Case 10: literary -> default style -> provider called (symmetric)."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="literary text",
        translated_chapter_lineage_overrides={"style_preset": "literary"},
        structured=False,
    )
    translation = StubTranslationService(final_text="default text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        style_preset=None,
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "default text"
    assert len(translation.calls) > 0


@pytest.mark.asyncio
async def test_pr41_delta_honorific_change_retain_to_default_calls_provider(orchestration_env) -> None:
    """Case 12: retain -> default honorific -> provider called (symmetric)."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="retain honorific text",
        translated_chapter_lineage_overrides={"honorific_policy": "retain"},
        structured=False,
    )
    translation = StubTranslationService(final_text="default honorific text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        honorific_policy=None,
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "default honorific text"
    assert len(translation.calls) > 0


@pytest.mark.asyncio
async def test_pr41_delta_consistency_true_to_false_calls_provider(orchestration_env) -> None:
    """Case 13: consistency_mode True -> False -> provider called."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="consistency-true text",
        translated_chapter_lineage_overrides={"consistency_mode": True},
        structured=False,
    )
    translation = StubTranslationService(final_text="consistency-false text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        consistency_mode=False,
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "consistency-false text"
    assert len(translation.calls) > 0


@pytest.mark.asyncio
async def test_pr41_delta_json_output_true_to_false_calls_provider(orchestration_env) -> None:
    """Case 14: json_output True -> False -> provider called."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="json-on text",
        translated_chapter_lineage_overrides={"json_output": True},
        structured=False,
    )
    translation = StubTranslationService(final_text="json-off text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        json_output=False,
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "json-off text"
    assert len(translation.calls) > 0


@pytest.mark.asyncio
async def test_pr41_paragraph_change_with_target_language_change_full_translate(orchestration_env) -> None:
    """Case 16: middle paragraph change + target-language change -> full translation, no old-language paragraphs."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "B.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole",
        translated_chapter_lineage_overrides={"target_language": "English"},
        structured=True,
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nBee.\n\nC.")
    translation = StubTranslationService(final_text="indonesian retranslation")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        target_language="Indonesian",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "indonesian retranslation"
    assert len(translation.calls) > 0
    # No old English paragraphs present.
    assert "old:" not in saved["text"]


@pytest.mark.asyncio
async def test_pr41_unchanged_contract_skips_provider_zero_calls(orchestration_env) -> None:
    """Case 1: same source + same contract -> reuse, zero provider calls."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old whole chapter",
        translated_chapter_lineage_overrides=None,
        structured=False,
    )
    translation = StubTranslationService(final_text="should not be called")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "old whole chapter"
    assert translation.calls == []
    # Section 6: true no-op — no new version; stored identity preserved and
    # the reuse is recorded in the run manifest with its own status.
    versions = storage.list_translated_chapter_versions("novel-delta", "1")
    assert len(versions) == 1
    assert saved["version_id"] == versions[0]["version_id"]
    assert summary["reused"] == 1
    assert summary["chapter_progress"]["1"]["status"] == "reused"
    manifest = storage.load_translation_run_manifest("novel-delta", summary["translation_run_id"])
    assert manifest is not None
    assert manifest.reused_chapter_ids == ["1"]
    assert manifest.reused_count == 1
    assert manifest.completed_count == 0


@pytest.mark.asyncio
async def test_pr41_delta_disabled_complete_contract_skips(orchestration_env, monkeypatch) -> None:
    """Case 22: delta disabled + complete valid persisted contract -> gate skips, zero calls."""
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="valid translation",
        translated_chapter_lineage_overrides=None,
        structured=False,
    )
    orchestrator = _s6_orchestrator(orchestration_env, StubTranslationService(final_text="should not be called"))

    from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

    kwargs = _s6_gate_contract_kwargs(storage)
    result = _check_chapter_resume_state(orchestrator, novel_id="novel-delta", chapter_id="1", force=False, **kwargs)
    assert result is not None
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_pr41_delta_disabled_target_language_change_calls_provider(orchestration_env, monkeypatch) -> None:
    """Case 25: delta disabled + target language change -> gate retranslates."""
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="english chapter",
        translated_chapter_lineage_overrides={"target_language": "English"},
        structured=False,
    )
    orchestrator = _s6_orchestrator(orchestration_env, StubTranslationService(final_text="indonesian chapter"))

    from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

    kwargs = _s6_gate_contract_kwargs(storage)
    kwargs["target_language"] = "Indonesian"
    result = _check_chapter_resume_state(orchestrator, novel_id="novel-delta", chapter_id="1", force=False, **kwargs)
    assert result is None  # not skipped; translation proceeds


@pytest.mark.asyncio
async def test_pr41_stored_version_contains_complete_lineage(orchestration_env) -> None:
    """Section 12: production-path stored overlay version has complete lineage fields."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text=None,
        structured=False,
    )
    # Provide glossary hash in metadata so the version can carry it as lineage.
    # The orchestrator records the canonical hash of the actual glossary used
    # (empty here), which is what the resume validator compares against.
    from novelai.glossary import canonical_glossary_hash

    expected_glossary_hash = canonical_glossary_hash(None)
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "stub",
            "source_language": "Japanese",
            "glossary_hash": "gloss-test",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-delta/1"}],
        },
    )
    translation = StubTranslationService(final_text="final translated text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        target_language="English",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    # The stored lineage carries the effective glossary hash of the run — the
    # same value the resume validator compares — not the raw metadata marker.
    assert saved.get("glossary_hash") == expected_glossary_hash
    assert saved.get("glossary_hash") is not None
    assert saved.get("prompt_template_version") is not None
    assert saved.get("translation_run_id") is not None
    assert saved.get("source_hash") is not None
    assert saved.get("source_structure_hash") is not None
    assert saved.get("source_image_manifest_hash") is not None
    assert saved.get("qa_policy_fingerprint") is not None
    assert saved.get("provider_key") == "mock"
    assert saved.get("provider_model") == "mock-1.0"
    assert saved.get("source_language") == "Japanese"
    assert saved.get("target_language") == "English"
    assert saved.get("output_hash") is not None
    assert saved.get("activation_disposition") is not None


@pytest.mark.asyncio
async def test_pr41_whole_chapter_reuse_preserves_original_provenance(orchestration_env) -> None:
    """Section 6: unchanged reuse preserves original provider/model.

    When source and the COMPLETE contract (including provider/model) are
    unchanged, whole_chapter_unchanged reuse returns the existing translation
    text and the saved reuse-record preserves the original producer's
    provider_key / provider_model — it does NOT stamp the current run's
    provider as the producer of reused text it never generated.
    """
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="original translation",
        translated_chapter_lineage_overrides={
            "provider_key": "original-provider",
            "provider_model": "original-model",
        },
        structured=False,
    )
    translation = StubTranslationService(final_text="should not be called")
    orchestrator = _s6_orchestrator(orchestration_env, translation)

    # Same provider/model as the stored lineage keeps the global contract identical.
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="original-provider",
        provider_model="original-model",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert translation.calls == []
    assert saved.get("text") == "original translation"
    # Original producer must be preserved (not stamped as new contract).
    assert saved.get("provider_key") == "original-provider"
    assert saved.get("provider_model") == "original-model"
    # Section 6: the reuse is a no-op — no reuse-record version was created,
    # so the stored version count is unchanged.
    versions = storage.list_translated_chapter_versions("novel-delta", "1")
    assert len(versions) == 1
    assert saved.get("version_id") == versions[0]["version_id"]


# ---------------------------------------------------------------------------
# PR-41 FINAL: production-path contract matrix (section 7) — every case runs
# the real orchestrator (translate_chapters) so validation AND execution are
# both exercised. Cases use the delta-enabled production path.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pr41_matrix_prompt_template_change_full_retranslate(orchestration_env) -> None:
    """Matrix: prompt template version change -> contract mismatch -> full retranslate."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old prompt text",
        translated_chapter_lineage_overrides={"prompt_template_version": "prompt-v1"},
        structured=False,
    )
    # The effective prompt version resolves from novel metadata.
    storage.save_metadata("novel-delta", {"prompt_template_version": "prompt-v2"})

    translation = StubTranslationService(final_text="new prompt text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new prompt text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"
    assert saved["prompt_template_version"] == "prompt-v2"


@pytest.mark.asyncio
async def test_pr41_matrix_qa_policy_change_full_retranslate(orchestration_env, monkeypatch) -> None:
    """Matrix: QA policy fingerprint change -> contract mismatch -> full retranslate."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old qa text",
        structured=False,
    )
    from novelai.services.orchestration.translation import _qa_policy_fingerprint
    from novelai.services.orchestration.translation import _resolve_effective_prompt_version as _resolve_prompt

    meta = storage.load_metadata("novel-delta") or {}
    seed_prompt = _resolve_prompt(storage, meta)
    old_fingerprint = _qa_policy_fingerprint(prompt_template_version=seed_prompt)
    monkeypatch.setattr(settings, "LLM_QA_MIN_SCORE", 0.9)
    new_fingerprint = _qa_policy_fingerprint(prompt_template_version=seed_prompt)
    assert new_fingerprint != old_fingerprint

    translation = StubTranslationService(final_text="new qa text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new qa text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"
    assert saved["qa_policy_fingerprint"] == new_fingerprint


@pytest.mark.asyncio
async def test_pr41_matrix_model_only_change_full_retranslate(orchestration_env) -> None:
    """Matrix: provider model change alone -> contract mismatch -> full retranslate."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old model text",
        structured=False,
    )

    translation = StubTranslationService(final_text="new model text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-2.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new model text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"
    # Stored identity is the EFFECTIVE REQUESTED contract identity, so the
    # new model must land on the stored lineage as well as on the provider call.
    assert saved["provider_model"] == "mock-2.0"
    assert translation.calls[0]["provider_model"] == "mock-2.0"


@pytest.mark.asyncio
async def test_pr41_matrix_source_structure_change_full_retranslate(orchestration_env) -> None:
    """Matrix: source structure change only -> contract mismatch -> full retranslate."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old structure text",
        structured=False,
    )
    # Identical text, changed source structure: only the structure dimension
    # differs. Use canonical line blocks — ``_normalize_source_blocks`` drops
    # any non-line/break block, so an arbitrary dict would vanish and the
    # structure hash would stay ``hash([])`` (matching the seeded baseline).
    storage.save_chapter(
        "novel-delta",
        "1",
        "A.\n\nB.",
        source_blocks=[{"type": "line", "text": "A."}, {"type": "line", "text": "B."}],
    )

    translation = StubTranslationService(final_text="new structure text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new structure text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"
    # The stored hash is computed over the NORMALIZED blocks; read them back
    # from storage so the expectation matches the production computation.
    normalized_blocks = storage.load_chapter("novel-delta", "1")["source_blocks"]
    expected_structure = storage._hash_text(
        json.dumps(normalized_blocks, ensure_ascii=False, sort_keys=True, default=str)
    )
    assert saved["source_structure_hash"] == expected_structure


@pytest.mark.asyncio
async def test_pr41_matrix_source_image_change_full_retranslate(orchestration_env) -> None:
    """Matrix: source image manifest change only -> contract mismatch -> full retranslate."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old image text",
        structured=False,
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nB.", images=[{"url": "https://example.com/panel.png"}])

    translation = StubTranslationService(final_text="new image text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new image text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"
    expected_image = storage._hash_text(
        json.dumps([{"url": "https://example.com/panel.png"}], ensure_ascii=False, sort_keys=True, default=str)
    )
    assert saved["source_image_manifest_hash"] == expected_image


@pytest.mark.asyncio
async def test_pr41_matrix_ocr_reviewed_text_change_delta_window(orchestration_env) -> None:
    """Matrix: reviewed OCR text changes the effective source -> delta window."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        old_translations=["old:A.", "old:B."],
        translated_chapter_text="old whole",
        structured=True,
    )
    storage.save_chapter_media_state(
        "novel-delta",
        "1",
        ocr_required=True,
        ocr_text="A.\n\nBee.",
        ocr_status="reviewed",
    )

    translation = StubTranslationService(paragraph_prefix="new:")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert len(translation.calls) == 1
    assert "Bee." in translation.calls[0]["raw_text"]
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    # The stored source_hash lineage is the effective (OCR) source, not the raw text.
    assert saved["source_hash"] == storage._hash_text("A.\n\nBee.")


@pytest.mark.asyncio
async def test_pr41_matrix_ocr_reviewed_text_identical_reuses(orchestration_env) -> None:
    """Matrix: reviewed OCR text identical to raw text -> reuse no-op."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old whole chapter",
        structured=False,
    )
    storage.save_chapter_media_state(
        "novel-delta",
        "1",
        ocr_required=True,
        ocr_text="A.\n\nB.",
        ocr_status="reviewed",
    )

    translation = StubTranslationService(final_text="should not be called")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "old whole chapter"
    assert translation.calls == []
    assert summary["reused"] == 1
    versions = storage.list_translated_chapter_versions("novel-delta", "1")
    assert len(versions) == 1


@pytest.mark.asyncio
async def test_pr41_matrix_unchanged_contract_creates_no_version(orchestration_env) -> None:
    """Matrix: fully unchanged contract -> reuse no-op, zero new versions."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="stable chapter",
        structured=False,
    )
    version_id_before = storage.list_translated_chapter_versions("novel-delta", "1")[0]["version_id"]

    translation = StubTranslationService(final_text="should not be called")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    assert summary["reused"] == 1
    assert summary["succeeded"] == 0
    assert summary["skipped"] == 0
    versions = storage.list_translated_chapter_versions("novel-delta", "1")
    assert [version["version_id"] for version in versions] == [version_id_before]
    manifest = storage.load_translation_run_manifest("novel-delta", summary["translation_run_id"])
    assert manifest is not None
    assert manifest.reused_chapter_ids == ["1"]
    assert manifest.reused_count == 1
    assert manifest.completed_count == 0


@pytest.mark.asyncio
async def test_pr41_matrix_source_and_qa_change_full_retranslate(orchestration_env, monkeypatch) -> None:
    """Matrix: source text AND QA policy change -> full retranslate with new lineage."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old combo text",
        structured=False,
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nBee.")
    # 0.9 differs from the default 0.75, so the QA-policy dimension changes;
    # patching AFTER the fixture seeds the baseline with the old fingerprint.
    monkeypatch.setattr(settings, "LLM_QA_MIN_SCORE", 0.9)

    translation = StubTranslationService(final_text="combo new text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "combo new text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"
    assert saved["source_hash"] == storage._hash_text("A.\n\nBee.")
    from novelai.services.orchestration.translation import _qa_policy_fingerprint

    assert saved["qa_policy_fingerprint"] == _qa_policy_fingerprint(
        prompt_template_version=saved["prompt_template_version"]
    )


@pytest.mark.asyncio
async def test_pr41_matrix_source_and_prompt_change_full_retranslate(orchestration_env) -> None:
    """Matrix: source text AND prompt change -> full retranslate with new lineage."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old combo prompt text",
        structured=False,
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nBee.")
    storage.save_metadata("novel-delta", {"prompt_template_version": "prompt-v9"})

    translation = StubTranslationService(final_text="combo prompt new text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "combo prompt new text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"
    assert saved["source_hash"] == storage._hash_text("A.\n\nBee.")
    assert saved["prompt_template_version"] == "prompt-v9"


@pytest.mark.asyncio
async def test_pr41_matrix_source_and_model_change_full_retranslate(orchestration_env) -> None:
    """Matrix: source text AND provider model change -> full retranslate."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old combo model text",
        structured=False,
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nBee.")

    translation = StubTranslationService(final_text="combo model new text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-2.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "combo model new text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"
    assert saved["source_hash"] == storage._hash_text("A.\n\nBee.")
    # Stored identity is the EFFECTIVE REQUESTED contract identity.
    assert saved["provider_model"] == "mock-2.0"
    assert translation.calls[0]["provider_model"] == "mock-2.0"


@pytest.mark.asyncio
async def test_pr41_stored_provider_identity_always_effective(orchestration_env) -> None:
    """A divergent result identity never poisons stored lineage.

    The full path stores the EFFECTIVE (requested) provider identity even when
    the pipeline result reports a different producer — future reuse decisions
    compare the stored identity against the current contract, so a lying
    result must never be recorded as the producer.
    """
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old identity text",
        structured=False,
    )

    translation = StubTranslationService(
        final_text="identity new text",
        reported_provider_key="rogue",
        reported_provider_model="rogue-9",
    )
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-2.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "identity new text"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"
    assert saved["provider_key"] == "mock"
    assert saved["provider_model"] == "mock-2.0"


@pytest.mark.asyncio
async def test_pr41_matrix_honorific_policy_applied_in_delta_window(orchestration_env) -> None:
    """Matrix: honorific policy is EXECUTED in the changed-window call."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "Bee."],
        old_translations=["old:A.", "old:B."],
        translated_chapter_text="old whole h",
        translated_chapter_lineage_overrides={"honorific_policy": "default_honorifics"},
        structured=True,
    )

    translation = StubTranslationService(paragraph_prefix="new:")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        honorific_policy="default_honorifics",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    # The effective honorific policy reached the provider call.
    assert translation.calls[0]["honorific_policy"] == "default_honorifics"
    assert saved["honorific_policy"] == "default_honorifics"


@pytest.mark.asyncio
async def test_pr41_matrix_json_output_policy_applied_in_delta_window(orchestration_env) -> None:
    """Matrix: effective json_output policy is EXECUTED in the changed-window call."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "Bee."],
        old_translations=["old:A.", "old:B."],
        translated_chapter_text="old whole j",
        translated_chapter_lineage_overrides={"json_output": True},
        structured=True,
    )

    translation = StubTranslationService(paragraph_prefix="new:")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        json_output=True,
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    assert translation.calls[0]["json_output"] is True
    assert saved["json_output"] is True


@pytest.mark.asyncio
async def test_pr41_matrix_leftover_ocr_without_required_uses_raw_text(orchestration_env) -> None:
    """Matrix: stale OCR text without ocr_required never hijacks the source."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old whole chapter",
        structured=False,
    )
    storage.save_chapter_media_state(
        "novel-delta",
        "1",
        ocr_required=False,
        ocr_text="A.\n\nDIFFERENT.",
        ocr_status="skipped",
    )

    translation = StubTranslationService(final_text="should not be called")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    assert translation.calls == []
    assert summary["reused"] == 1
    versions = storage.list_translated_chapter_versions("novel-delta", "1")
    assert len(versions) == 1


# ---------------------------------------------------------------------------
# PR-41 FINAL: exact stored lineage values (section 8) + output-hash
# self-consistency on the production path (section 10).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pr41_stored_lineage_exact_values(orchestration_env) -> None:
    """Section 8: stored lineage carries the EXACT effective contract values."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text=None,
        structured=False,
    )
    from novelai.glossary import canonical_glossary_hash
    from novelai.services.orchestration.translation import (
        _qa_policy_fingerprint,
        _resolve_effective_prompt_version,
    )

    translation = StubTranslationService(final_text="exact lineage text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        target_language="English",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    meta = storage.load_metadata("novel-delta") or {}
    expected_prompt = _resolve_effective_prompt_version(storage, meta)
    raw_text = "A.\n\nB."

    def json_dumps(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    assert saved["source_hash"] == storage._hash_text(raw_text)
    assert saved["source_structure_hash"] == storage._hash_text(json_dumps([]))
    assert saved["source_image_manifest_hash"] == storage._hash_text(json_dumps([]))
    assert saved["glossary_hash"] == canonical_glossary_hash(None)
    assert saved["prompt_template_version"] == expected_prompt
    assert saved["qa_policy_fingerprint"] == _qa_policy_fingerprint(prompt_template_version=expected_prompt)
    assert saved["provider_key"] == "mock"
    assert saved["provider_model"] == "mock-1.0"
    assert saved["source_language"] == "Japanese"
    assert saved["target_language"] == "English"
    assert saved["style_preset"] is None
    assert saved["consistency_mode"] is False
    assert saved["json_output"] is False
    assert saved["honorific_policy"] == "contextual"
    assert saved["source_episode_id"] == "1"
    assert saved["translation_run_id"] is not None
    assert saved["output_hash"] == storage._hash_text("exact lineage text")
    assert saved["activation_disposition"] == "auto_activate"


@pytest.mark.asyncio
async def test_pr41_output_hash_corruption_fails_closed(orchestration_env) -> None:
    """Section 10: stored text mutated without re-hash -> reuse fails closed."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="original text",
        structured=False,
    )
    # Corrupt the stored version: change the text but NOT the output_hash.
    overlay = storage._load_translation_overlay("novel-delta", "1")
    assert overlay is not None
    version = overlay["translation_versions"][0]
    assert version["output_hash"] == storage._hash_text("original text")
    version["text"] = "mutated text"
    assert version["output_hash"] != storage._hash_text("mutated text")
    storage._persist_translation_overlay("novel-delta", "1", overlay)

    translation = StubTranslationService(final_text="fresh retranslation")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "fresh retranslation"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "output_contract_changed"
    assert saved["output_hash"] == storage._hash_text("fresh retranslation")


# ---------------------------------------------------------------------------
# PR-41 FINAL: authoritative provider contract resolution (section 3).
# The contract identity is resolved ONCE with strict precedence
# (explicit caller > workflow profile > global preferred), never None, and is
# what the manifest / resume gate / delta / execution / lineage all record.
# ---------------------------------------------------------------------------


def _seed_fresh_provider_novel(storage: StorageService, novel_id: str = "novel-provider") -> None:
    storage.save_metadata(
        novel_id,
        {
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{novel_id}/1"}],
        },
    )
    storage.save_chapter(novel_id, "1", "A.\n\nB.")


class AuthoritativeListProvider(MockTranslationProvider):
    """Test provider with an authoritative ``available_models()`` contract.

    A non-empty ``available_models()`` list is the provider's declared model
    contract: a model not on the list is unsupported and must fail closed at
    resolution time (it is never silently swapped for another model).
    """

    def __init__(self, key: str, models: list[str], default_model: str) -> None:
        super().__init__(key=key, model=default_model)
        self._models = list(models)

    def available_models(self) -> list[str]:
        return list(self._models)


def _authoritative_orchestrator(
    orchestration_env, translation: Any, *, settings_service: PreferencesService | None = None
) -> NovelOrchestrationService:
    """Orchestrator over authoritative-list test providers plus one free-form.

    - ``alpha`` declares ``["alpha-1.0", "alpha-1.1"]``;
    - ``beta`` declares ``["beta-1.0", "beta-2.0"]``;
    - ``gamma`` is free-form (``available_models() == []``) and accepts any
      non-empty explicit model.
    """
    providers = {
        "alpha": AuthoritativeListProvider("alpha", ["alpha-1.0", "alpha-1.1"], "alpha-1.0"),
        "beta": AuthoritativeListProvider("beta", ["beta-1.0", "beta-2.0"], "beta-1.0"),
        "gamma": MockTranslationProvider(key="gamma", model="gamma-free"),
    }
    return NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: providers[key],
        settings_service=settings_service or orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )


@pytest.mark.asyncio
async def test_pr41_provider_contract_implicit_resolution_uses_global_preferred(orchestration_env) -> None:
    """Section 3: omitted caller + omitted profile resolve to global preferred.

    The contract identity is resolved BEFORE execution: the pipeline call, the
    stored version and the run manifest all record the same non-None identity.
    """
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)

    translation = StubTranslationService(final_text="implicit text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        source_language="Japanese",
    )

    assert len(translation.calls) == 1
    assert translation.calls[0]["provider_key"] == "mock"
    assert translation.calls[0]["provider_model"] == "mock-1.0"
    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert saved["provider_key"] == "mock"
    assert saved["provider_model"] == "mock-1.0"
    manifest = storage.load_translation_run_manifest("novel-provider", summary["translation_run_id"])
    assert manifest is not None
    assert manifest.provider_key == "mock"
    assert manifest.provider_model == "mock-1.0"


@pytest.mark.asyncio
async def test_pr41_provider_contract_implicit_rerun_reuses_without_calls(orchestration_env) -> None:
    """Section 3: a stable implicit contract reuses the stored version with no
    new provider calls (identity resolved identically on both runs)."""
    storage = orchestration_env["storage"]
    # Seed a stored version whose lineage carries the SAME implicit contract
    # (mock / mock-1.0 from the global preferred preferences) so the delta
    # path can whole-chapter reuse it — exactly what a prior implicit run
    # would have produced.
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old whole chapter",
        structured=False,
    )
    version_id_before = storage.list_translated_chapter_versions("novel-delta", "1")[0]["version_id"]

    translation = StubTranslationService(final_text="should not be called")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        source_language="Japanese",
    )

    assert translation.calls == []
    assert summary["reused"] == 1
    versions = storage.list_translated_chapter_versions("novel-delta", "1")
    assert [version["version_id"] for version in versions] == [version_id_before]
    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["provider_key"] == "mock"
    assert saved["provider_model"] == "mock-1.0"


@pytest.mark.asyncio
async def test_pr41_provider_contract_preferred_model_change_retranslates(orchestration_env) -> None:
    """Section 3: changing the global preferred model invalidates the stored
    version and retranslates with the NEW identity recorded in the contract."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)

    translation = StubTranslationService(final_text="model change text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        source_language="Japanese",
    )
    first_version = storage.list_translated_chapter_versions("novel-provider", "1")[0]["version_id"]

    orchestration_env["settings"].set_preferred_model("mock-2.0")
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        source_language="Japanese",
    )

    assert len(translation.calls) == 2
    assert translation.calls[1]["provider_key"] == "mock"
    assert translation.calls[1]["provider_model"] == "mock-2.0"
    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert saved["provider_model"] == "mock-2.0"
    versions = storage.list_translated_chapter_versions("novel-provider", "1")
    assert [version["version_id"] for version in versions] != [first_version]
    assert len(versions) == 2


@pytest.mark.asyncio
async def test_pr41_provider_contract_preferred_provider_change_retranslates(orchestration_env) -> None:
    """Section 3: changing the global preferred provider invalidates the stored
    version and retranslates with the NEW provider identity recorded."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)

    translation = StubTranslationService(final_text="provider change text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        source_language="Japanese",
    )
    first_version = storage.list_translated_chapter_versions("novel-provider", "1")[0]["version_id"]

    orchestration_env["settings"].set_preferred_provider("mock-other")
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        source_language="Japanese",
    )

    assert len(translation.calls) == 2
    assert translation.calls[1]["provider_key"] == "mock-other"
    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert saved["provider_key"] == "mock-other"
    versions = storage.list_translated_chapter_versions("novel-provider", "1")
    assert [version["version_id"] for version in versions] != [first_version]
    assert len(versions) == 2


@pytest.mark.asyncio
async def test_pr41_provider_contract_workflow_profile_overrides_global(orchestration_env) -> None:
    """Section 3: with caller omitted, the body-translation workflow profile
    wins over the global preferred provider/model."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)
    orchestration_env["settings"].set_llm_step_config(
        "body_translation",
        provider_key="wf-provider",
        provider_model="wf-model",
    )

    translation = StubTranslationService(final_text="profile text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        source_language="Japanese",
    )

    assert len(translation.calls) == 1
    assert translation.calls[0]["provider_key"] == "wf-provider"
    assert translation.calls[0]["provider_model"] == "wf-model"
    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert saved["provider_key"] == "wf-provider"
    assert saved["provider_model"] == "wf-model"
    manifest = storage.load_translation_run_manifest("novel-provider", summary["translation_run_id"])
    assert manifest is not None
    assert manifest.provider_key == "wf-provider"


@pytest.mark.asyncio
async def test_pr41_provider_contract_explicit_overrides_workflow(orchestration_env) -> None:
    """Section 3: explicit caller values win over the workflow profile."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)
    orchestration_env["settings"].set_llm_step_config(
        "body_translation",
        provider_key="wf-provider",
        provider_model="wf-model",
    )

    translation = StubTranslationService(final_text="explicit text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    assert len(translation.calls) == 1
    assert translation.calls[0]["provider_key"] == "mock"
    assert translation.calls[0]["provider_model"] == "mock-1.0"
    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert saved["provider_key"] == "mock"
    assert saved["provider_model"] == "mock-1.0"


@pytest.mark.asyncio
async def test_pr41_provider_contract_never_records_none_identity(orchestration_env) -> None:
    """Section 3 negative invariant: no successful translation version is ever
    created with a missing provider identity — the pipeline stage must not
    silently execute an identity the contract does not record."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)

    translation = StubTranslationService(final_text="non-none text")
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert saved["provider_key"] is not None
    assert saved["provider_model"] is not None
    manifest = storage.load_translation_run_manifest("novel-provider", summary["translation_run_id"])
    assert manifest is not None
    assert manifest.provider_key is not None
    assert manifest.provider_model is not None
    # The executed call carried exactly the contract identity.
    assert translation.calls[0]["provider_key"] == saved["provider_key"]
    assert translation.calls[0]["provider_model"] == saved["provider_model"]


@pytest.mark.asyncio
async def test_pr41_contract_explicit_provider_only_uses_provider_default_model(orchestration_env) -> None:
    """Section 5.1: an explicit provider with an omitted model resolves the
    provider's OWN default model — never a model configured for a different
    provider (the cross-provider leak from the reproduction)."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)
    # Global preferred provider/model belong to a DIFFERENT provider (alpha);
    # with explicit provider "beta" they must not bleed into the pair.
    orchestration_env["settings"].set_preferred_provider("alpha")
    orchestration_env["settings"].set_preferred_model("alpha-1.0")

    translation = StubTranslationService(final_text="beta default text")
    orchestrator = _authoritative_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        provider_key="beta",
        source_language="Japanese",
    )

    assert len(translation.calls) == 1
    assert translation.calls[0]["provider_key"] == "beta"
    assert translation.calls[0]["provider_model"] == "beta-1.0"
    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert (saved["provider_key"], saved["provider_model"]) == ("beta", "beta-1.0")
    manifest = storage.load_translation_run_manifest("novel-provider", summary["translation_run_id"])
    assert manifest is not None
    assert (manifest.provider_key, manifest.provider_model) == ("beta", "beta-1.0")


@pytest.mark.asyncio
async def test_pr41_contract_explicit_provider_and_supported_model_exact_pair(orchestration_env) -> None:
    """Section 5.2: an explicit provider + an explicit model from its
    authoritative list resolve to exactly that pair."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)

    translation = StubTranslationService(final_text="beta 2.0 text")
    orchestrator = _authoritative_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        provider_key="beta",
        provider_model="beta-2.0",
        source_language="Japanese",
    )

    assert len(translation.calls) == 1
    assert translation.calls[0]["provider_key"] == "beta"
    assert translation.calls[0]["provider_model"] == "beta-2.0"
    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert (saved["provider_key"], saved["provider_model"]) == ("beta", "beta-2.0")
    manifest = storage.load_translation_run_manifest("novel-provider", summary["translation_run_id"])
    assert manifest is not None
    assert (manifest.provider_key, manifest.provider_model) == ("beta", "beta-2.0")


@pytest.mark.asyncio
async def test_pr41_contract_workflow_profile_model_never_carried_across_providers(orchestration_env) -> None:
    """Section 5.3: a workflow-profile model is coherent only with the
    workflow-profile provider. Explicit provider "beta" + a body-translation
    profile (alpha / alpha-1.0) must resolve beta's own model — the profile
    model is never validated against or carried into another provider."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)
    orchestration_env["settings"].set_llm_step_config(
        "body_translation",
        provider_key="alpha",
        provider_model="alpha-1.0",
    )

    translation = StubTranslationService(final_text="profile leak text")
    orchestrator = _authoritative_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        provider_key="beta",
        source_language="Japanese",
    )

    assert len(translation.calls) == 1
    assert translation.calls[0]["provider_key"] == "beta"
    assert translation.calls[0]["provider_model"] == "beta-1.0"
    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert (saved["provider_key"], saved["provider_model"]) == ("beta", "beta-1.0")
    manifest = storage.load_translation_run_manifest("novel-provider", summary["translation_run_id"])
    assert manifest is not None
    assert (manifest.provider_key, manifest.provider_model) == ("beta", "beta-1.0")


@pytest.mark.asyncio
async def test_pr41_contract_unsupported_explicit_model_fails_closed(orchestration_env) -> None:
    """Section 5.4: an explicit model outside the selected provider's
    authoritative list is a configuration error — it fails closed before any
    manifest or execution, never silently swapped for a supported model."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)

    translation = StubTranslationService(final_text="must not run")
    orchestrator = _authoritative_orchestrator(orchestration_env, translation)
    with pytest.raises(ProviderConfigError) as exc_info:
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-provider",
            chapters="1",
            provider_key="beta",
            provider_model="alpha-1.0",
            source_language="Japanese",
        )

    assert exc_info.value.provider_error_code == ProviderErrorCode.CONFIGURATION
    assert exc_info.value.provider_key == "beta"
    assert translation.calls == []
    assert storage.list_translated_chapter_versions("novel-provider", "1") == []


@pytest.mark.asyncio
async def test_pr41_contract_unknown_provider_fails_closed_before_manifest(orchestration_env) -> None:
    """Section 5.5: a provider key no factory can produce is a configuration
    error at resolution time — no manifest, no stored version, no call."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)

    translation = StubTranslationService(final_text="must not run")
    orchestrator = _authoritative_orchestrator(orchestration_env, translation)
    with pytest.raises(ProviderConfigError) as exc_info:
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-provider",
            chapters="1",
            provider_key="no-such-provider",
            source_language="Japanese",
        )

    assert exc_info.value.provider_error_code == ProviderErrorCode.CONFIGURATION
    assert translation.calls == []
    assert storage.list_translated_chapter_versions("novel-provider", "1") == []


@pytest.mark.asyncio
async def test_pr41_contract_whitespace_identity_normalized(orchestration_env) -> None:
    """Section 5.6: surrounding whitespace is stripped from provider/model
    inputs; empty / whitespace-only values are treated as absent."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)

    translation = StubTranslationService(final_text="normalized text")
    orchestrator = _authoritative_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        provider_key=" beta ",
        provider_model=" beta-2.0 ",
        source_language="Japanese",
    )

    assert len(translation.calls) == 1
    assert (translation.calls[0]["provider_key"], translation.calls[0]["provider_model"]) == ("beta", "beta-2.0")
    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert (saved["provider_key"], saved["provider_model"]) == ("beta", "beta-2.0")
    manifest = storage.load_translation_run_manifest("novel-provider", summary["translation_run_id"])
    assert manifest is not None
    assert (manifest.provider_key, manifest.provider_model) == ("beta", "beta-2.0")


@pytest.mark.asyncio
async def test_pr41_contract_gemini_without_api_key_fails_closed(orchestration_env) -> None:
    """Section 5.7: Gemini without a configured API key fails closed before a
    manifest is created — even with a valid explicit model."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)
    orchestration_env["settings"].clear_api_key("gemini")

    def factory(key: str) -> TranslationProvider:
        return MockTranslationProvider(key=key, model=GEMINI_DEFAULT_MODEL)

    translation = StubTranslationService(final_text="must not run")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=factory,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )
    with pytest.raises(ProviderConfigError) as exc_info:
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-provider",
            chapters="1",
            provider_key="gemini",
            provider_model=GEMINI_DEFAULT_MODEL,
            source_language="Japanese",
        )

    assert exc_info.value.provider_error_code == ProviderErrorCode.CONFIGURATION
    assert exc_info.value.provider_key == "gemini"
    assert translation.calls == []
    assert storage.list_translated_chapter_versions("novel-provider", "1") == []


@pytest.mark.asyncio
async def test_pr41_contract_dummy_provider_outside_test_environment_fails_closed(
    orchestration_env, monkeypatch
) -> None:
    """Section 5.8: the dummy provider is available only when ENV=test; outside
    test the guard fails closed at resolution time."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)
    monkeypatch.setattr(settings, "ENV", "production")

    translation = StubTranslationService(final_text="must not run")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key=key, model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )
    with pytest.raises(ProviderConfigError) as exc_info:
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-provider",
            chapters="1",
            provider_key="dummy",
            provider_model="dummy",
            source_language="Japanese",
        )

    assert exc_info.value.provider_error_code == ProviderErrorCode.CONFIGURATION
    assert exc_info.value.provider_key == "dummy"
    assert translation.calls == []
    assert storage.list_translated_chapter_versions("novel-provider", "1") == []


@pytest.mark.asyncio
async def test_pr41_contract_free_form_provider_accepts_explicit_model(orchestration_env) -> None:
    """Section 5.9: a provider with ``available_models() == []`` is free-form —
    any non-empty explicit model is valid and passes through exactly."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)

    translation = StubTranslationService(final_text="free form text")
    orchestrator = _authoritative_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-provider",
        chapters="1",
        provider_key="gamma",
        provider_model="gamma-custom-model",
        source_language="Japanese",
    )

    assert len(translation.calls) == 1
    assert (translation.calls[0]["provider_key"], translation.calls[0]["provider_model"]) == (
        "gamma",
        "gamma-custom-model",
    )
    saved = storage.load_translated_chapter("novel-provider", "1")
    assert saved is not None
    assert (saved["provider_key"], saved["provider_model"]) == ("gamma", "gamma-custom-model")
    manifest = storage.load_translation_run_manifest("novel-provider", summary["translation_run_id"])
    assert manifest is not None
    assert (manifest.provider_key, manifest.provider_model) == ("gamma", "gamma-custom-model")


@pytest.mark.asyncio
async def test_pr41_contract_no_provider_configured_fails_closed(orchestration_env) -> None:
    """Section 5.10: with no explicit, profile, or global preferred provider,
    resolution fails closed instead of inventing an identity."""
    storage = orchestration_env["storage"]
    _seed_fresh_provider_novel(storage)
    fresh_settings = PreferencesService(orchestration_env["data_dir"])

    translation = StubTranslationService(final_text="must not run")
    orchestrator = _authoritative_orchestrator(orchestration_env, translation, settings_service=fresh_settings)
    with pytest.raises(ProviderConfigError) as exc_info:
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-provider",
            chapters="1",
            source_language="Japanese",
        )

    assert exc_info.value.provider_error_code == ProviderErrorCode.CONFIGURATION
    assert translation.calls == []
    assert storage.list_translated_chapter_versions("novel-provider", "1") == []


@pytest.mark.asyncio
async def test_pr41_contract_identity_identical_across_all_consumers_and_resume(orchestration_env) -> None:
    """Section 5.11: one authoritative pair is recorded identically in the
    executed call, the stored version and the run manifest — and the resume
    gate reuses on the same contract instead of calling the provider again.

    The stored version's lineage carries the exact effective contract (here
    seeded with the explicit alpha / alpha-1.1 pair, as a prior production run
    would have written it); the second run's delta path compares the SAME pair
    and performs a true whole-chapter no-op reuse (no new version, no call).
    """
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old whole chapter",
        structured=False,
        translated_chapter_lineage_overrides={"provider_key": "alpha", "provider_model": "alpha-1.1"},
    )
    version_id_before = storage.list_translated_chapter_versions("novel-delta", "1")[0]["version_id"]

    translation = StubTranslationService(final_text="should not be called")
    orchestrator = _authoritative_orchestrator(orchestration_env, translation)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="alpha",
        provider_model="alpha-1.1",
        source_language="Japanese",
    )

    assert translation.calls == []
    assert summary["reused"] == 1
    # The reuse preserved the stored contract identity untouched — no new
    # version, no divergence, the same pair the contract would have executed.
    versions = storage.list_translated_chapter_versions("novel-delta", "1")
    assert [version["version_id"] for version in versions] == [version_id_before]
    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert (saved["provider_key"], saved["provider_model"]) == ("alpha", "alpha-1.1")


# ---------------------------------------------------------------------------
# PR-41 FINAL: REAL-pipeline delta-window evidence (section 5/6/7 closure).
# The stub-based tests above prove the orchestrator's delta decision. These
# tests wire the orchestrator to the REAL production pipeline (Fetch → Parse →
# SmartSegment → Translate → QA → CacheFlush → PostProcess) with a
# deterministic provider that parses the ``[P ...]`` markers out of the
# TranslationRequest and echoes them back — so marker handling, QA coverage
# and fail-closed behavior are proven against the actual stages, including
# the section-6 absolute-paragraph-id stamping and the strict marker parser.
# ---------------------------------------------------------------------------


def _parse_marker_source(source_text: str) -> tuple[str | None, list[tuple[str, str]]]:
    """Parse ``[CHAPTER <id>]`` / ``[P <id>]`` blocks out of a prompt source.

    Returns ``(chapter_id, occurrences)`` where ``occurrences`` is a list of
    ``(paragraph_id, body_text)`` preserving exact ordered occurrences.
    """
    chapter_id: str | None = None
    occurrences: list[tuple[str, str]] = []
    current_id: str | None = None
    current_body: list[str] = []
    for line in (source_text or "").splitlines():
        paragraph_match = re.match(r"^\[P\s+([^\]]+)\]\s*$", line)
        if paragraph_match:
            if current_id is not None:
                occurrences.append((current_id, "\n".join(current_body).strip()))
            matched_paragraph_id = paragraph_match.group(1)
            if matched_paragraph_id is None:
                continue
            current_id = matched_paragraph_id.strip()
            current_body = []
            continue
        chapter_match = re.match(r"^\[CHAPTER\s+([^\]]+)\]\s*$", line)
        if chapter_match:
            if chapter_id is None:
                matched_chapter_id = chapter_match.group(1)
                if matched_chapter_id is not None:
                    chapter_id = matched_chapter_id.strip()
            continue
        if current_id is not None:
            current_body.append(line)
    if current_id is not None:
        occurrences.append((current_id, "\n".join(current_body).strip()))
    return chapter_id, occurrences


class DeterministicTranslationProvider(TranslationProvider):
    """Real-pipeline deterministic provider.

    Copies every ``[P <id>]`` marker from the ``TranslationRequest`` text
    (the delta window's ABSOLUTE paragraph ids) exactly once with a ``tr:``
    body, mirroring the production prompt contract. Malformed-output knobs
    (drop / duplicate / extra / reorder / preamble) exercise the strict marker
    parser's fail-closed behavior through the REAL stages. Every call records
    the requested model, schema and prompt so tests can assert the requested
    identity and paragraph ids reached the provider verbatim.
    """

    def __init__(
        self,
        key: str = "mock",
        model: str = "mock-1.0",
        *,
        prefix: str = "tr:",
        drop_paragraph_ids: set[str] | None = None,
        drop_occurrence: tuple[str, int] | None = None,
        duplicate_paragraph_id: str | None = None,
        extra_paragraph_id: str | None = None,
        reorder: bool = False,
        preamble: str | None = None,
    ) -> None:
        super().__init__()
        self._key = key
        self.model = model
        self.prefix = prefix
        self.drop_paragraph_ids = drop_paragraph_ids or set()
        self.drop_occurrence = drop_occurrence
        self.duplicate_paragraph_id = duplicate_paragraph_id
        self.extra_paragraph_id = extra_paragraph_id
        self.reorder = reorder
        self.preamble = preamble
        self.calls: list[dict[str, Any]] = []

    @property
    def key(self) -> str:
        return self._key

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        request = kwargs.get("request")
        source_text = getattr(request, "text", None) if request is not None else None
        if not isinstance(source_text, str) or not source_text.strip():
            source_text = prompt
        json_output = bool(getattr(request, "json_output", False)) if request is not None else False
        self.calls.append(
            {
                "model": model,
                "json_output": json_output,
                "request": request,
                "source_text": source_text,
            }
        )
        chapter_id, occurrences = _parse_marker_source(source_text)

        emitted_occurrences: list[tuple[str, str]] = []
        seen_counts: dict[str, int] = {}
        for pid, body in occurrences:
            if pid in self.drop_paragraph_ids:
                continue
            count = seen_counts.get(pid, 0) + 1
            seen_counts[pid] = count
            if self.drop_occurrence and self.drop_occurrence == (pid, count):
                continue
            emitted_occurrences.append((pid, body))
            if pid == self.duplicate_paragraph_id:
                emitted_occurrences.append((pid, body))
        if self.reorder:
            emitted_occurrences = list(reversed(emitted_occurrences))
        extra_id = self.extra_paragraph_id
        if extra_id:
            emitted_occurrences.append((extra_id, extra_id))

        if json_output:
            paragraph_map = [
                {
                    "chapter_id": chapter_id or "1",
                    "paragraph_id": pid,
                    "translated_text": f"{self.prefix}{body or pid}",
                }
                for pid, body in emitted_occurrences
            ]
            raw = json.dumps(
                {
                    "translated_text": "\n\n".join(item["translated_text"] for item in paragraph_map),
                    "paragraph_map": paragraph_map,
                }
            )
            return {"text": raw, "metadata": {}}

        lines: list[str] = []
        if self.preamble:
            lines.append(self.preamble)
        if chapter_id:
            lines.append(f"[CHAPTER {chapter_id}]")
            lines.append("")
        for pid, body in emitted_occurrences:
            lines.append(f"[P {pid}]")
            lines.append(f"{self.prefix}{body or pid}")
            lines.append("")
        return {"text": "\n".join(lines).strip(), "metadata": {}}


def _real_pipeline_orchestrator(
    orchestration_env, provider: TranslationProvider, *, settings_service: PreferencesService | None = None
) -> NovelOrchestrationService:
    """Orchestrator wired to the REAL production translation pipeline.

    The same stage set the production container builds (Fetch, Parse,
    SmartSegment, Translate with the provider factory, QA, CacheFlush,
    PostProcess) — so delta-window evidence runs through actual marker
    parsing, QA coverage, chunk persistence and cache flush. The sharded
    ``TranslationCacheService`` is isolated per test (the production default
    points at the shared library directory, which would leak cache entries
    between tests).
    """
    cache_service = TranslationCacheService(cache_dir=orchestration_env["data_dir"] / "translation_cache")
    service = TranslationService(
        pipeline=TranslationPipeline(
            stages=[
                FetchStage(),
                ParseStage(),
                SmartSegmentStage(),
                TranslateStage(
                    provider_factory=lambda key: provider,
                    cache=orchestration_env["cache"],
                    cache_service=cache_service,
                    settings_service=settings_service or orchestration_env["settings"],
                    usage_service=orchestration_env["usage"],
                    storage=orchestration_env["storage"],
                ),
                TranslationQAStage(),
                CacheFlushStage(cache_service=cache_service),
                PostProcessStage(),
            ]
        )
    )
    return NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=service,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=settings_service or orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )


@pytest.mark.asyncio
async def test_pr41_real_pipeline_plain_delta_uses_absolute_paragraph_ids(orchestration_env) -> None:
    """Section 6/7 real pipeline: with the default json_output=False policy,
    the delta window executes through the REAL stages; the provider receives
    the chapter's ABSOLUTE paragraph ids verbatim in the prompt and the saved
    chapter reuses + translates by exactly those identities."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole rp",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    summary = await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    assert len(provider.calls) == 1
    call = provider.calls[0]
    # The requested contract identity reached the real TranslateStage verbatim.
    assert call["model"] == "mock-1.0"
    assert call["json_output"] is False
    assert "[P p0001]" in call["source_text"]
    assert "[P p0002]" in call["source_text"]
    assert "[P p0003]" in call["source_text"]
    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "tr:A.\n\ntr:Bee.\n\ntr:C."
    assert saved["json_output"] is False
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    assert saved["confidence_details"]["delta"]["newly_translated_paragraph_ids"] == ["p0001", "p0002", "p0003"]
    manifest = storage.load_translation_run_manifest("novel-delta", summary["translation_run_id"])
    assert manifest is not None
    assert (manifest.provider_key, manifest.provider_model) == ("mock", "mock-1.0")


@pytest.mark.asyncio
async def test_pr41_real_pipeline_json_paragraph_map_regression(orchestration_env) -> None:
    """Section 6/7 real pipeline: with json_output=True the REAL provider JSON
    ``paragraph_map`` drives the changed window (regression guard for the
    structured path through the actual stages)."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole jr",
        translated_chapter_lineage_overrides={"json_output": True},
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        json_output=True,
    )

    assert len(provider.calls) == 1
    assert provider.calls[0]["json_output"] is True
    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "tr:A.\n\ntr:Bee.\n\ntr:C."
    assert saved["json_output"] is True
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    assert saved["confidence_details"]["delta"]["newly_translated_paragraph_ids"] == ["p0001", "p0002", "p0003"]


@pytest.mark.asyncio
async def test_pr41_real_pipeline_missing_marker_fails_closed(orchestration_env, monkeypatch) -> None:
    """Section 6 real pipeline fail-closed: a dropped marker fails the REAL QA
    gate (paragraph_missing) on the window AND the full retranslation; the
    chapter run fails and no new version with a wrong mapping is ever stored."""
    monkeypatch.setattr(settings, "TRANSLATION_MAX_ATTEMPTS_PER_CHUNK", 1)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole mrp",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0", drop_paragraph_ids={"p0002"})
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    with pytest.raises(RuntimeError):
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-delta",
            chapters="1",
            provider_key="mock",
            provider_model="mock-1.0",
            source_language="Japanese",
        )

    # The malformed window never produced a stored chapter: the seeded version
    # is preserved untouched (no wrong mapping was persisted).
    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "old whole mrp"
    assert len(storage.list_translated_chapter_versions("novel-delta", "1")) == 1


@pytest.mark.asyncio
async def test_pr41_real_pipeline_duplicate_marker_fails_closed(orchestration_env, monkeypatch) -> None:
    """Section 6 real pipeline fail-closed: a duplicated marker is
    ``paragraph_duplicate`` — QA rejects it and nothing is stored."""
    monkeypatch.setattr(settings, "TRANSLATION_MAX_ATTEMPTS_PER_CHUNK", 1)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole drp",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0", duplicate_paragraph_id="p0002")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    with pytest.raises(RuntimeError):
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-delta",
            chapters="1",
            provider_key="mock",
            provider_model="mock-1.0",
            source_language="Japanese",
        )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "old whole drp"
    assert len(storage.list_translated_chapter_versions("novel-delta", "1")) == 1


@pytest.mark.asyncio
async def test_pr41_real_pipeline_extra_marker_fails_closed(orchestration_env, monkeypatch) -> None:
    """Section 6 real pipeline fail-closed: an unknown extra marker is
    ``paragraph_unexpected`` — QA rejects it and nothing is stored."""
    monkeypatch.setattr(settings, "TRANSLATION_MAX_ATTEMPTS_PER_CHUNK", 1)
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole erp",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0", extra_paragraph_id="p0099")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    with pytest.raises(RuntimeError):
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-delta",
            chapters="1",
            provider_key="mock",
            provider_model="mock-1.0",
            source_language="Japanese",
        )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "old whole erp"
    assert len(storage.list_translated_chapter_versions("novel-delta", "1")) == 1


@pytest.mark.asyncio
async def test_pr41_real_pipeline_reordered_markers_fall_back_to_full(orchestration_env) -> None:
    """Section 6 real pipeline fail-closed: reordered markers pass the QA
    warning-level check but the STRICT lineage parser rejects the window —
    the delta path falls back to a full retranslation."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole rrp",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0", reorder=True)
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_pr41_real_pipeline_preamble_falls_back_to_full(orchestration_env) -> None:
    """Section 6 real pipeline fail-closed: preamble text before the first
    marker is rejected by the strict parser -> full retranslation."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole prp",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0", preamble="Here is the translation:")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_pr41_real_pipeline_oversized_paragraph_applies_window(orchestration_env) -> None:
    """Section 6 real pipeline: an oversized paragraph in the changed window
    is split by SmartSegmentStage into multiple chunks while preserving the
    source paragraph_id on every piece. Each chunk output is parsed strictly
    against its own ids and the pieces are merged back onto the single source
    paragraph, so the delta window applies instead of failing closed."""
    storage = orchestration_env["storage"]
    oversized = "B." + ("x" * 9000)
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", oversized, "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole orp",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    assert saved["confidence_details"]["delta"]["newly_translated_paragraph_ids"] == ["p0001", "p0002", "p0003"]
    # One window executed (one provider call per pipeline chunk); the
    # oversized paragraph reached the provider split across several chunks
    # with its absolute paragraph id repeated on every piece.
    assert len(provider.calls) >= 2
    assert sum(1 for call in provider.calls if "[P p0002]" in call["source_text"]) >= 2
    # The window applied with the split pieces merged back onto the single
    # source paragraph: exactly three chapter paragraphs, the middle one
    # longer than any single chunk budget (proof the pieces were merged).
    parts = saved["text"].split("\n\n")
    assert parts[0] == "tr:A."
    assert parts[-1] == "tr:C."
    middle = "\n\n".join(parts[1:-1])
    assert middle.startswith("tr:B.")
    assert len(middle) > 7000
    assert len(parts) >= 3


@pytest.mark.asyncio
async def test_pr41_real_pipeline_oversized_paragraph_json_applies_window(orchestration_env) -> None:
    """Section 6 real pipeline, json_output=True: the split oversized window
    is mapped through the per-chunk structured ``paragraph_map`` path and the
    pieces are merged back onto the single source paragraph."""
    storage = orchestration_env["storage"]
    oversized = "B." + ("x" * 9000)
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", oversized, "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole orp",
        structured=True,
        translated_chapter_lineage_overrides={"json_output": True},
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        json_output=True,
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    assert all(call["json_output"] is True for call in provider.calls)
    parts = saved["text"].split("\n\n")
    assert parts[0] == "tr:A."
    assert parts[-1] == "tr:C."
    middle = "\n\n".join(parts[1:-1])
    assert middle.startswith("tr:B.")
    assert len(middle) > 7000
    assert len(parts) >= 3


# ---------------------------------------------------------------------------
# PR-41 FINAL: plain-output delta windows (section 6/7).
# Default policy is json_output=False; a strict ``[P ...]`` marker parser maps
# plain provider output onto the window's absolute paragraph ids. Any
# ambiguity fails closed to a full translation.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pr41_plain_delta_default_policy_applies_window(orchestration_env) -> None:
    """Section 6/7: with the default json_output=False policy, a realistic
    provider's plain marker output drives the changed window; the full path is
    not used and reuse/order are preserved."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole c",
        structured=True,
    )

    storage, translation = await _run_delta_translate(orchestration_env, MarkerAwareStubTranslationService())

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "tr:A.\n\ntr:Bee.\n\ntr:C."
    assert len(translation.calls) == 1
    # The changed window executes the effective policy (False, not hard-coded)
    # and carries the chapter's ABSOLUTE paragraph ids in the prompt.
    assert translation.calls[0]["json_output"] is False
    assert translation.calls[0]["paragraph_ids"] == ["p0001", "p0002", "p0003"]
    assert saved["json_output"] is False
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    assert saved["confidence_details"]["delta"]["newly_translated_paragraph_ids"] == ["p0001", "p0002", "p0003"]


@pytest.mark.asyncio
async def test_pr41_plain_delta_json_output_true_uses_json_path(orchestration_env) -> None:
    """Section 6/7: with json_output=True the realistic provider emits a JSON
    paragraph_map and the structured path still drives the window."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole j",
        translated_chapter_lineage_overrides={"json_output": True},
        structured=True,
    )

    translation = MarkerAwareStubTranslationService()
    orchestrator = _s6_orchestrator(orchestration_env, translation)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        json_output=True,
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "tr:A.\n\ntr:Bee.\n\ntr:C."
    assert len(translation.calls) == 1
    assert translation.calls[0]["json_output"] is True
    assert saved["json_output"] is True
    assert saved["confidence_details"]["delta"]["mode"] == "delta"


@pytest.mark.asyncio
async def test_pr41_plain_delta_blank_paragraph_marker_preserved(orchestration_env) -> None:
    """Section 6: a blank translated paragraph KEEPS its marker and maps to an
    empty body — the parser must not reject it."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole b",
        structured=True,
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, MarkerAwareStubTranslationService(blank_paragraph_ids={"p0002"})
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    # p0002 translated but blank: marker preserved, empty body kept in order
    # (the two "\n\n" separators around the empty body yield 4 newlines).
    assert saved["text"] == "tr:A.\n\n\n\ntr:C."
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["newly_translated_paragraph_ids"] == ["p0001", "p0002", "p0003"]


@pytest.mark.asyncio
async def test_pr41_plain_delta_missing_marker_falls_back_to_full(orchestration_env) -> None:
    """Section 6 fail-closed: a dropped marker is missing from the expected set
    -> the window result is rejected and the chapter is fully retranslated."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole m",
        structured=True,
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, MarkerAwareStubTranslationService(drop_paragraph_ids={"p0002"})
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"
    assert len(translation.calls) == 2
    assert "[P p0001]" in saved["text"]
    assert "[P p0003]" in saved["text"]


@pytest.mark.asyncio
async def test_pr41_plain_delta_duplicate_marker_falls_back_to_full(orchestration_env) -> None:
    """Section 6 fail-closed: a duplicated marker breaks uniqueness -> full."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole d",
        structured=True,
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, MarkerAwareStubTranslationService(duplicate_paragraph_id="p0002")
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"
    assert len(translation.calls) == 2
    assert "[P p0001]" in saved["text"]


@pytest.mark.asyncio
async def test_pr41_plain_delta_reordered_markers_fail_closed(orchestration_env) -> None:
    """Section 6 fail-closed: markers out of source order -> full."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole r",
        structured=True,
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, MarkerAwareStubTranslationService(reorder=True)
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"
    assert len(translation.calls) == 2


@pytest.mark.asyncio
async def test_pr41_plain_delta_extra_marker_falls_back_to_full(orchestration_env) -> None:
    """Section 6 fail-closed: an unknown extra marker is ambiguity -> full."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole e",
        structured=True,
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, MarkerAwareStubTranslationService(extra_paragraph_id="p0099")
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"
    assert len(translation.calls) == 2


@pytest.mark.asyncio
async def test_pr41_plain_delta_preamble_falls_back_to_full(orchestration_env) -> None:
    """Section 6 fail-closed: non-marker preamble text before the first
    paragraph marker is ambiguity -> full."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole p",
        structured=True,
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, MarkerAwareStubTranslationService(preamble="Here is the translation:")
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"
    assert len(translation.calls) == 2


@pytest.mark.asyncio
async def test_pr41_real_pipeline_same_chunk_repeated_ids_plain_markers(orchestration_env) -> None:
    """Section 9.1: prove oversized sentence-split paragraph producing repeated
    paragraph_ids in ONE chunk passes QA and applies via plain markers."""
    storage = orchestration_env["storage"]
    sentence1 = "A" * 3000 + "。"
    sentence2 = "B" * 3000 + "。"
    sentence3 = "C" * 3000 + "。"
    oversized_p2 = sentence1 + sentence2 + sentence3

    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", oversized_p2, "C."],
        new_paragraphs=["A.", oversized_p2 + "D。", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole same chunk",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    delta_info = saved["confidence_details"]["delta"]
    assert delta_info["mode"] == "delta"
    assert delta_info["newly_translated_paragraph_ids"] == ["p0001", "p0002", "p0003"]
    assert len(provider.calls) >= 2

    chunk_with_repeats = False
    for call in provider.calls:
        src = call.get("source_text") or ""
        if src.count("[P p0002]") >= 2:
            chunk_with_repeats = True
            break
    assert chunk_with_repeats, "At least one provider call chunk must contain >= 2 occurrences of [P p0002]"

    text = saved["text"]
    assert "tr:A." in text
    assert f"tr:{sentence1}" in text
    assert f"tr:{sentence2}" in text
    assert f"tr:{sentence3}" in text
    assert text.index(f"tr:{sentence1}") < text.index(f"tr:{sentence2}") < text.index(f"tr:{sentence3}")


@pytest.mark.asyncio
async def test_pr41_real_pipeline_same_chunk_repeated_ids_json(orchestration_env) -> None:
    """Section 9.2: prove oversized sentence-split paragraph producing repeated
    paragraph_ids in ONE chunk passes QA and applies via JSON paragraph_map."""
    storage = orchestration_env["storage"]
    sentence1 = "A" * 3000 + "。"
    sentence2 = "B" * 3000 + "。"
    sentence3 = "C" * 3000 + "。"
    oversized_p2 = sentence1 + sentence2 + sentence3

    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", oversized_p2, "C."],
        new_paragraphs=["A.", oversized_p2 + "D。", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole same chunk json",
        structured=True,
        translated_chapter_lineage_overrides={"json_output": True},
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        json_output=True,
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    delta_info = saved["confidence_details"]["delta"]
    assert delta_info["mode"] == "delta"
    assert delta_info["newly_translated_paragraph_ids"] == ["p0001", "p0002", "p0003"]
    assert len(provider.calls) >= 2

    text = saved["text"]
    assert f"tr:{sentence1}" in text
    assert f"tr:{sentence2}" in text
    assert f"tr:{sentence3}" in text


@pytest.mark.asyncio
async def test_pr41_real_pipeline_same_chunk_missing_occurrence_fails_closed(orchestration_env) -> None:
    """Section 9.3: expected p0002 repeat x2 in chunk, provider drops one occurrence -> fail closed."""
    from novelai.translation.pipeline.pipeline import PipelineStageError

    storage = orchestration_env["storage"]
    sentence1 = "A" * 3000 + "。"
    sentence2 = "B" * 3000 + "。"
    sentence3 = "C" * 3000 + "。"
    oversized_p2 = sentence1 + sentence2 + sentence3

    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", oversized_p2, "C."],
        new_paragraphs=["A.", oversized_p2 + "D。", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole missing occ",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0", drop_occurrence=("p0002", 2))
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)

    with pytest.raises(PipelineStageError):
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-delta",
            chapters="1",
            provider_key="mock",
            provider_model="mock-1.0",
            source_language="Japanese",
        )


@pytest.mark.asyncio
async def test_pr41_real_pipeline_same_chunk_excess_occurrence_fails_closed(orchestration_env) -> None:
    """Section 9.4: provider emits an excess occurrence beyond expected count -> fail closed."""
    from novelai.translation.pipeline.pipeline import PipelineStageError

    storage = orchestration_env["storage"]
    sentence1 = "A" * 3000 + "。"
    sentence2 = "B" * 3000 + "。"
    sentence3 = "C" * 3000 + "。"
    oversized_p2 = sentence1 + sentence2 + sentence3

    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", oversized_p2, "C."],
        new_paragraphs=["A.", oversized_p2 + "D。", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole excess occ",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0", duplicate_paragraph_id="p0002")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)

    with pytest.raises(PipelineStageError):
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-delta",
            chapters="1",
            provider_key="mock",
            provider_model="mock-1.0",
            source_language="Japanese",
        )


@pytest.mark.asyncio
async def test_pr41_real_pipeline_same_chunk_reordered_occurrences_fails_closed(orchestration_env) -> None:
    """Section 9.5: provider reorders occurrences -> fail closed."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole reorder occ",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0", reorder=True)
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"


def test_pr41_strict_structured_map_matrix() -> None:
    """Section 11 matrix for _json_map_for_expected_ids."""
    from novelai.services.orchestration.translation_lineage import _json_map_for_expected_ids

    def _make_json(items: list[dict[str, str]]) -> str:
        return json.dumps(
            {"paragraph_map": items, "translated_text": "\n\n".join(i.get("translated_text", "") for i in items)}
        )

    # A. exact unique sequence -> pass
    res_a = _json_map_for_expected_ids(
        _make_json([{"paragraph_id": "p1", "translated_text": "T1"}, {"paragraph_id": "p2", "translated_text": "T2"}]),
        ["p1", "p2"],
    )
    assert res_a == ["T1", "T2"]

    # B. exact expected repeated sequence -> pass
    res_b = _json_map_for_expected_ids(
        _make_json(
            [{"paragraph_id": "p2", "translated_text": "T2a"}, {"paragraph_id": "p2", "translated_text": "T2b"}]
        ),
        ["p2", "p2"],
    )
    assert res_b == ["T2a", "T2b"]

    # C. missing entry -> reject
    assert (
        _json_map_for_expected_ids(_make_json([{"paragraph_id": "p1", "translated_text": "T1"}]), ["p1", "p2"]) is None
    )

    # D. extra entry -> reject
    assert (
        _json_map_for_expected_ids(
            _make_json(
                [
                    {"paragraph_id": "p1", "translated_text": "T1"},
                    {"paragraph_id": "p2", "translated_text": "T2"},
                    {"paragraph_id": "p3", "translated_text": "T3"},
                ]
            ),
            ["p1", "p2"],
        )
        is None
    )

    # E. reordered entry -> reject
    assert (
        _json_map_for_expected_ids(
            _make_json(
                [{"paragraph_id": "p2", "translated_text": "T2"}, {"paragraph_id": "p1", "translated_text": "T1"}]
            ),
            ["p1", "p2"],
        )
        is None
    )

    # F. wrong paragraph id with correct length -> reject
    assert (
        _json_map_for_expected_ids(
            _make_json(
                [{"paragraph_id": "p1", "translated_text": "T1"}, {"paragraph_id": "p99", "translated_text": "T99"}]
            ),
            ["p1", "p2"],
        )
        is None
    )

    # G. wrong chapter id -> reject
    assert (
        _json_map_for_expected_ids(
            _make_json([{"chapter_id": "999", "paragraph_id": "p1", "translated_text": "T1"}]),
            ["p1"],
            expected_chapter_id="1",
        )
        is None
    )

    # H. repeated occurrence beyond expected count -> reject
    assert (
        _json_map_for_expected_ids(
            _make_json(
                [
                    {"paragraph_id": "p2", "translated_text": "T2a"},
                    {"paragraph_id": "p2", "translated_text": "T2b"},
                    {"paragraph_id": "p2", "translated_text": "T2c"},
                ]
            ),
            ["p2", "p2"],
        )
        is None
    )

    # I. raw malformed entry in paragraph_map -> rejected directly before identity acceptance
    assert (
        _json_map_for_expected_ids(
            _make_json(
                [
                    {"paragraph_id": "p1", "translated_text": "T1"},
                    {"paragraph_id": "junk"},
                    {"paragraph_id": "p2", "translated_text": "T2"},
                ]
            ),
            ["p1", "p2"],
        )
        is None
    )


@pytest.mark.asyncio
async def test_pr41_provider_available_models_exception_fails_closed(orchestration_env, caplog) -> None:
    """Section 12: provider.available_models() exception raises ProviderConfigError and does not leak secrets into logs or error."""
    import logging

    from novelai.core.errors import ProviderConfigError

    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A."],
        new_paragraphs=["A."],
        old_translations=["old:A."],
        translated_chapter_text="old",
        structured=True,
    )

    class RaisingProvider(TranslationProvider):
        @property
        def key(self) -> str:
            return "raising-mock"

        def available_models(self) -> list[str]:
            raise RuntimeError("API error with secret_api_key_12345 querying model list")

        async def translate(
            self, prompt: str, model: str | None = None, max_tokens: int | None = None, **kwargs: Any
        ) -> dict[str, Any]:
            raise AssertionError("translate() must never be called when available_models() raises")

    provider = RaisingProvider()
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)

    with caplog.at_level(logging.WARNING), pytest.raises(ProviderConfigError) as exc_info:
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-delta",
            chapters="1",
            provider_key="raising-mock",
            provider_model="some-model",
            source_language="Japanese",
        )

    assert "raising-mock" in str(exc_info.value)
    assert "secret_api_key_12345" not in str(exc_info.value)
    assert "secret_api_key_12345" not in caplog.text
    assert exc_info.value.__cause__ is None


@pytest.mark.asyncio
async def test_pr41_provider_instance_exception_sanitizes_logs(orchestration_env, caplog) -> None:
    """Section 12: provider factory exception raises ProviderConfigError and sanitizes caplog text."""
    import logging

    from novelai.core.errors import ProviderConfigError

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0")
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)

    def raising_factory(key: str) -> TranslationProvider:
        raise RuntimeError("Authorization: Bearer secret_provider_token_67890")

    orchestrator._provider_factory = raising_factory

    with caplog.at_level(logging.WARNING), pytest.raises(ProviderConfigError) as exc_info:
        orchestrator._provider_instance("raising-factory")

    assert "raising-factory" in str(exc_info.value)
    assert "secret_provider_token_67890" not in str(exc_info.value)
    assert "secret_provider_token_67890" not in caplog.text
    assert exc_info.value.__cause__ is None


@pytest.mark.asyncio
async def test_pr41_fresh_full_required_bypasses_cache_on_unsafe_delta(orchestration_env) -> None:
    """Section 13: unsafe delta decline (changed_window_qa_failed) sets fresh_full_required=True
    so full fallback performs fresh provider calls bypassing cache."""
    storage = orchestration_env["storage"]
    _save_delta_execution_fixture(
        storage,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
        translated_chapter_text="old whole unsafe",
        structured=True,
    )

    provider = DeterministicTranslationProvider(key="mock", model="mock-1.0", reorder=True)
    orchestrator = _real_pipeline_orchestrator(orchestration_env, provider)
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"
    # Unsafe delta fallback issued fresh full translation calls (not cached)
    assert len(provider.calls) >= 2


def test_pr41_context_overlap_stripping_and_qa_ratio() -> None:
    """Section 14: [CONTEXT OVERLAP]...[END CONTEXT OVERLAP] blocks are stripped from QA length ratio
    calculations so prior-chunk context does not cause translation_too_short, while translatable
    content outside overlap is still evaluated."""
    from novelai.translation.pipeline.context import TranslationChunk
    from novelai.translation.qa import evaluate_translation_quality

    source_text = (
        "[CONTEXT OVERLAP]\n"
        + ("X" * 1000)
        + "\n[END CONTEXT OVERLAP]\n[CHAPTER 1]\n[P p0001]\nActual source paragraph."
    )
    # Provider translates only the actual source paragraph (not the context overlap)
    output_text = "[CHAPTER 1]\n[P p0001]\nActual source paragraph translated."

    chunk = TranslationChunk(
        chunk_id="c1",
        novel_id="n1",
        chapter_ids=["1"],
        paragraph_ids=["p0001"],
        source_text=source_text,
        char_count=len(source_text),
        paragraph_refs=[("1", "p0001")],
    )

    res = evaluate_translation_quality(source_text=source_text, translated_text=output_text, chunk=chunk)
    assert res.passed, f"QA should pass when context overlap is stripped; errors: {res.errors}"
    assert "translation_too_short" not in res.errors

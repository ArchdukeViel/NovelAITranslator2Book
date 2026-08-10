from __future__ import annotations

import json
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.config.settings import GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODEL, settings
from novelai.core.chapter_state import ChapterState
from novelai.core.errors import ProviderConfigError, ProviderErrorCode
from novelai.db.base import Base
from novelai.db.models.novel import Novel
from novelai.inputs.base import DocumentAdapter
from novelai.inputs.models import ImportedDocument, ImportedUnit
from novelai.providers.base import TranslationProvider
from novelai.providers.model_fallbacks import model_candidates
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.orchestration import crawler as crawler_module
from novelai.services.orchestration.translation import _translation_lineage_kwargs
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache, TranslationCacheService
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
from novelai.storage.service import StorageService
from novelai.translation.pipeline.context import PipelineResult, PipelineState, paragraph_source_hash
from novelai.translation.pipeline.pipeline import TranslationPipeline
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.translation.pipeline.stages.cache_flush import CacheFlushStage
from novelai.translation.pipeline.stages.fetch import FetchStage
from novelai.translation.pipeline.stages.parse import ParseStage
from novelai.translation.pipeline.stages.post_process import PostProcessStage
from novelai.translation.pipeline.stages.segment import SmartSegmentStage
from novelai.translation.pipeline.stages.translate import TranslateStage
from novelai.translation.pipeline.stages.translation_qa import TranslationQAStage
from novelai.translation.service import TranslationService
from novelai.utils.chapter_selection import ResolvedChapterSelection
from tests.conftest import TESTS_TMP_ROOT, MockTranslationProvider


class StubSource(SourceAdapter):
    source_key = "stub"

    def __init__(self) -> None:
        self.requested_max_chapters: list[int | None] = []
        self.chapter_payloads: dict[str, dict[str, object]] = {}
        self.assets: dict[str, dict[str, object]] = {}

    def can_handle(self, identifier_or_url: str) -> bool:
        return False

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, object]:
        self.requested_max_chapters.append(max_chapter)
        return {
            "source_key": "syosetu_ncode",
            "source_url": f"https://ncode.syosetu.com/{url}/",
            "title": "Original Novel",
            "author": "Original Author",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{url}/1"},
                {"id": "2", "num": 2, "title": "Chapter Two", "url": f"https://example.com/{url}/2"},
            ],
        }

    async def fetch_chapter(self, url: str) -> str:
        return f"chapter from {url}"

    async def fetch_chapter_payload(self, url: str, *, on_retry=None) -> dict[str, object]:
        payload = self.chapter_payloads.get(url)
        if payload is not None:
            return payload
        return {"text": await self.fetch_chapter(url), "images": []}

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> dict[str, object]:
        asset = self.assets.get(url)
        if asset is not None:
            return asset
        return {
            "url": url,
            "content": b"asset-bytes",
            "content_type": "image/png",
        }


class UnusedTranslationService(TranslationService):
    pass


class StubDocumentAdapter(DocumentAdapter):
    @property
    def key(self) -> str:
        return "text"

    def probe(self, source: str | Path) -> bool:
        return True

    async def import_document(
        self,
        source: str | Path,
        *,
        max_units: int | None = None,
    ) -> ImportedDocument:
        units = (
            ImportedUnit(
                unit_id="1",
                import_order=1,
                title="Part 1",
                text="Hero Aria entered the city.",
                source_ref=str(source),
                unit_type="chapter",
                context_group_id="stub-doc",
            ),
            ImportedUnit(
                unit_id="2",
                import_order=2,
                title="Part 2",
                text="Hero Aria returned.",
                source_ref=str(source),
                unit_type="chapter",
                context_group_id="stub-doc",
            ),
        )
        return ImportedDocument(
            adapter_key=self.key,
            origin_type="file",
            origin_uri_or_path=str(source),
            document_type="text",
            title="Imported Story",
            source_language="Japanese",
            units=units,
        )


class StubTranslationService(TranslationService):
    def __init__(
        self,
        *,
        final_text: str = "translated",
        fail: bool = False,
        paragraph_prefix: str | None = None,
        reported_provider_key: str | None = None,
        reported_provider_model: str | None = None,
    ) -> None:
        self.final_text = final_text
        self.fail = fail
        self.paragraph_prefix = paragraph_prefix
        # Optional identity the stub reports on the RESULT, independent of the
        # requested provider (defaults to echoing the request, like the
        # production service). Passing a divergent value exercises the
        # orchestrator's invariant that stored lineage always records the
        # EFFECTIVE (requested) identity.
        self.reported_provider_key = reported_provider_key
        self.reported_provider_model = reported_provider_model
        self.calls: list[dict[str, Any]] = []

    async def translate_chapter(self, **kwargs: Any) -> PipelineResult:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("provider failure")
        provider_key = (
            self.reported_provider_key
            if self.reported_provider_key is not None
            else str(kwargs.get("provider_key") or "mock")
        )
        provider_model = (
            self.reported_provider_model
            if self.reported_provider_model is not None
            else str(kwargs.get("provider_model") or "mock-1.0")
        )
        if self.paragraph_prefix is not None:
            raw_text = str(kwargs.get("raw_text") or "")
            paragraphs = [part.strip() for part in raw_text.split("\n\n") if part.strip()]
            paragraph_map = [
                {
                    "chapter_id": str(kwargs.get("chapter_id") or "1"),
                    "paragraph_id": f"p{index:04d}",
                    "translated_text": f"{self.paragraph_prefix}{part}",
                }
                for index, part in enumerate(paragraphs, start=1)
            ]
            raw = json.dumps(
                {
                    "translated_text": "\n\n".join(item["translated_text"] for item in paragraph_map),
                    "paragraph_map": paragraph_map,
                }
            )
            return PipelineResult(
                final_text="\n\n".join(item["translated_text"] for item in paragraph_map),
                chapter_url=str(kwargs.get("chapter_url") or ""),
                provider_key=provider_key,
                provider_model=provider_model,
                translations=[raw],
                metadata={"raw_provider_translations": [raw]},
            )
        return PipelineResult(
            final_text=self.final_text,
            chapter_url=str(kwargs.get("chapter_url") or ""),
            provider_key=provider_key,
            provider_model=provider_model,
        )


class MarkerAwareStubTranslationService(TranslationService):
    """Realistic delta-window provider: plain ``[P ...]`` markers when
    ``json_output=False``, JSON ``paragraph_map`` when ``json_output=True``.

    Mirrors the production prompt contract (templates.py): paragraph ids are
    copied from the window's prompt (``paragraph_ids`` kwarg), every marker
    appears exactly once in source order, and a blank body keeps its marker.
    Malformed-output knobs exercise the strict marker parser's fail-closed
    behavior. The result echoes the REQUESTED provider identity like the
    production service.
    """

    def __init__(
        self,
        *,
        prefix: str = "tr:",
        drop_paragraph_ids: set[str] | None = None,
        duplicate_paragraph_id: str | None = None,
        extra_paragraph_id: str | None = None,
        reorder: bool = False,
        preamble: str | None = None,
        blank_paragraph_ids: set[str] | None = None,
        fail: bool = False,
    ) -> None:
        self.prefix = prefix
        self.drop_paragraph_ids = drop_paragraph_ids or set()
        self.duplicate_paragraph_id = duplicate_paragraph_id
        self.extra_paragraph_id = extra_paragraph_id
        self.reorder = reorder
        self.preamble = preamble
        self.blank_paragraph_ids = blank_paragraph_ids or set()
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def translate_chapter(self, **kwargs: Any) -> PipelineResult:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("provider failure")
        provider_key = str(kwargs.get("provider_key") or "mock")
        provider_model = str(kwargs.get("provider_model") or "mock-1.0")
        chapter_id = str(kwargs.get("chapter_id") or "1")
        json_output = bool(kwargs.get("json_output", False))
        raw_text = str(kwargs.get("raw_text") or "")
        paragraphs = [part.strip() for part in raw_text.split("\n\n") if part.strip()]
        paragraph_ids = [str(pid) for pid in (kwargs.get("paragraph_ids") or [])]
        if len(paragraph_ids) != len(paragraphs):
            paragraph_ids = [f"p{index:04d}" for index in range(1, len(paragraphs) + 1)]

        translated_by_id = {
            pid: ("" if pid in self.blank_paragraph_ids else f"{self.prefix}{part}")
            for pid, part in zip(paragraph_ids, paragraphs, strict=True)
        }
        emitted_ids: list[str] = []
        for pid in paragraph_ids:
            if pid in self.drop_paragraph_ids:
                continue
            emitted_ids.append(pid)
            if pid == self.duplicate_paragraph_id:
                emitted_ids.append(pid)
        if self.reorder:
            emitted_ids = list(reversed(emitted_ids))
        if self.extra_paragraph_id:
            emitted_ids.append(self.extra_paragraph_id)

        if json_output:
            paragraph_map = [
                {
                    "chapter_id": chapter_id,
                    "paragraph_id": pid,
                    "translated_text": translated_by_id.get(pid, f"{self.prefix}{pid}"),
                }
                for pid in emitted_ids
            ]
            raw = json.dumps(
                {
                    "translated_text": "\n\n".join(item["translated_text"] for item in paragraph_map),
                    "paragraph_map": paragraph_map,
                }
            )
            return PipelineResult(
                final_text="\n\n".join(item["translated_text"] for item in paragraph_map),
                chapter_url=str(kwargs.get("chapter_url") or ""),
                provider_key=provider_key,
                provider_model=provider_model,
                translations=[raw],
                metadata={"raw_provider_translations": [raw]},
            )

        lines: list[str] = []
        if self.preamble:
            lines.append(self.preamble)
        lines.append(f"[CHAPTER {chapter_id}]")
        lines.append("")
        for pid in emitted_ids:
            lines.append(f"[P {pid}]")
            body = translated_by_id.get(pid, f"{self.prefix}{pid}")
            if body:
                lines.append(body)
            lines.append("")
        raw_output = "\n".join(lines).strip()
        return PipelineResult(
            final_text=raw_output,
            chapter_url=str(kwargs.get("chapter_url") or ""),
            provider_key=provider_key,
            provider_model=provider_model,
            translations=[raw_output],
            metadata={"raw_provider_translations": [raw_output]},
        )


class RuntimeSimulationTranslationService(TranslationService):
    def __init__(self, storage: StorageService, *, fail_chapter_once: str | None = None) -> None:
        self.storage = storage
        self.fail_chapter_once = fail_chapter_once
        self.failed_chapters: set[str] = set()
        self.calls: list[dict[str, Any]] = []

    async def translate_chapter(self, **kwargs: Any) -> PipelineResult:
        self.calls.append(kwargs)
        novel_id = str(kwargs.get("novel_id") or "novel1")
        chapter_id = str(kwargs.get("chapter_id") or "1")
        job_id = kwargs.get("job_id") if isinstance(kwargs.get("job_id"), str) else None
        activity_id = kwargs.get("activity_id") if isinstance(kwargs.get("activity_id"), str) else None
        translation_run_id = job_id or activity_id or f"manual_sim_{len(self.calls):04d}"
        provider_key = str(kwargs.get("provider_key") or "mock")
        provider_model = str(kwargs.get("provider_model") or "mock-1.0")
        chunk_id = "c0001"
        is_failure = self.fail_chapter_once == chapter_id and chapter_id not in self.failed_chapters
        source_text = (
            "[P p0001]\nsmall retry paragraph"
            if not is_failure and chapter_id == self.fail_chapter_once
            else str(kwargs.get("raw_text") or f"[P p0001]\nchapter {chapter_id} full text")
        )
        status = "needs_retry" if is_failure else "translated"
        attempt_number = 2 if is_failure else 1

        self.storage.save_translation_chunks(
            novel_id,
            [
                {
                    "chunk_id": chunk_id,
                    "novel_id": novel_id,
                    "translation_run_id": translation_run_id,
                    "chapter_ids": [chapter_id],
                    "paragraph_ids": ["p0001"],
                    "source_text": source_text,
                    "status": status,
                    "attempt_count": attempt_number,
                    "provider_key": provider_key,
                    "provider_model": provider_model,
                }
            ],
        )
        self.storage.save_chunk_attempt_record(
            {
                "chunk_id": chunk_id,
                "novel_id": novel_id,
                "translation_run_id": translation_run_id,
                "chapter_ids": [chapter_id],
                "paragraph_ids": ["p0001"],
                "attempt_number": attempt_number,
                "provider_key": provider_key,
                "provider_model": provider_model,
                "status": "failed" if is_failure else "succeeded",
                "error_code": "simulated_full_chunk_failure" if is_failure else None,
            }
        )
        chunk_state = {
            "chunk_id": chunk_id,
            "novel_id": novel_id,
            "translation_run_id": translation_run_id,
            "chapter_ids": [chapter_id],
            "paragraph_ids": ["p0001"],
            "provider_key": provider_key,
            "provider_model": provider_model,
            "attempt_number": attempt_number,
            "status": status,
            "error_code": "simulated_full_chunk_failure" if is_failure else None,
        }
        self.storage.upsert_chunk_state(chunk_state)
        event = {
            "job_id": job_id,
            "activity_id": activity_id,
            "translation_run_id": translation_run_id,
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "chunk_id": chunk_id,
            "stage_name": "RuntimeSimulation",
            "status_before": "running",
            "status_after": "failed" if is_failure else "translated",
            "error_code": "simulated_full_chunk_failure" if is_failure else None,
        }
        if is_failure:
            self.failed_chapters.add(chapter_id)
            failed_context = PipelineState(
                chapter_url=str(kwargs.get("chapter_url") or ""),
                job_id=job_id,
                activity_id=activity_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                provider_key=provider_key,
                provider_model=provider_model,
                metadata={"translation_run_id": translation_run_id},
            )
            failed_context.chunk_states[chunk_id] = chunk_state
            failed_context.pipeline_events.append(event)
            error = RuntimeError("simulated full chunk failure")
            error.pipeline_context = failed_context  # type: ignore[attr-defined]
            error.pipeline_events = [event]  # type: ignore[attr-defined]
            error.details = {"chunk_id": chunk_id, "attempt_number": attempt_number}  # type: ignore[attr-defined]
            raise error

        translated = f"translated chapter {chapter_id}"
        self.storage.save_translation_output(
            {
                "output_id": f"{chunk_id}:attempt_{attempt_number:04d}",
                "chunk_id": chunk_id,
                "novel_id": novel_id,
                "translation_run_id": translation_run_id,
                "chapter_ids": [chapter_id],
                "paragraph_ids": ["p0001"],
                "translated_text": translated,
                "provider_key": provider_key,
                "provider_model": provider_model,
                "attempt_number": attempt_number,
                "qa_status": status,
            }
        )
        return PipelineResult(
            final_text=translated,
            chapter_url=str(kwargs.get("chapter_url") or ""),
            job_id=job_id,
            activity_id=activity_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            provider_key=provider_key,
            provider_model=provider_model,
            pipeline_events=[event],
            chunk_states={chunk_id: chunk_state},
            metadata={"translation_run_id": translation_run_id},
        )


class _BootstrapCandidate:
    def __init__(self, source: str, context_summary: str | None = None, notes: str | None = None) -> None:
        self.source = source
        self.context_summary = context_summary
        self.notes = notes


class RunIdCaptureStage(PipelineStage):
    def __init__(self) -> None:
        self.run_ids: list[str] = []

    async def run(self, context: PipelineState) -> PipelineState:
        run_id = context.metadata.get("translation_run_id")
        if isinstance(run_id, str):
            self.run_ids.append(run_id)
        context.final_text = "translated"
        return context


class GlossarySchemaCaptureProvider(MockTranslationProvider):
    def __init__(self) -> None:
        super().__init__(key="mock", model="mock-1.0")
        self.last_kwargs: dict[str, Any] = {}

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.last_kwargs = kwargs
        return {
            "text": json.dumps(
                {
                    "terms": [
                        {"source": "魔導具"},
                        {"source": "王都"},
                    ]
                },
                ensure_ascii=False,
            ),
            "metadata": {
                "usage": {
                    "total_tokens": 42,
                },
            },
        }


class PromptInjectionCaptureProvider(TranslationProvider):
    def __init__(self) -> None:
        self.user_prompts: list[str] = []

    @property
    def key(self) -> str:
        return "mock"

    def available_models(self) -> list[str]:
        return ["mock-1.0"]

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        request = kwargs.get("request")
        user_prompt = getattr(request, "user_prompt", "") if request is not None else ""
        self.user_prompts.append(str(user_prompt))
        return {
            "text": "[CHAPTER 1]\n[P p0001]\nTranslated Pocott.",
            "metadata": {"usage": {"total_tokens": 3}},
        }


class GeminiFallbackProvider(MockTranslationProvider):
    def __init__(self) -> None:
        super().__init__(key="gemini", model=GEMINI_DEFAULT_MODEL)
        self.models_seen: list[str | None] = []

    def available_models(self) -> list[str]:
        return [GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODEL]

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.models_seen.append(model)
        if model == GEMINI_DEFAULT_MODEL:
            raise RuntimeError("quota exceeded")
        source_text = prompt
        if "<source_text>" in prompt and "</source_text>" in prompt:
            source_text = prompt.split("<source_text>", 1)[1].split("</source_text>", 1)[0].strip()
        return {
            "text": f"[{model}] {source_text}",
            "metadata": {
                "usage": {
                    "total_tokens": 11,
                },
            },
        }


class PartialGeminiTitleProvider(MockTranslationProvider):
    def __init__(self) -> None:
        super().__init__(key="gemini", model=GEMINI_DEFAULT_MODEL)
        self.models_seen: list[str | None] = []

    def available_models(self) -> list[str]:
        return [GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODEL]

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.models_seen.append(model)
        source_text = prompt
        if "<source_text>" in prompt and "</source_text>" in prompt:
            source_text = prompt.split("<source_text>", 1)[1].split("</source_text>", 1)[0].strip()
        if model == GEMINI_DEFAULT_MODEL and source_text == "第10話　初スカート、お披露目":
            return {"text": "Episode", "metadata": {"usage": {"total_tokens": 3}}}
        if source_text == "第10話　初スカート、お披露目":
            return {"text": "Episode 10: First Skirt Reveal", "metadata": {"usage": {"total_tokens": 8}}}
        return {"text": f"[{model}] {source_text}", "metadata": {"usage": {"total_tokens": 11}}}


class PartialTitleSource(StubSource):
    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, object]:
        self.requested_max_chapters.append(max_chapter)
        return {
            "source_key": "novel18_syosetu",
            "source_url": f"https://novel18.syosetu.com/{url}/",
            "title": "TS刑事　如月真琴の憂鬱",
            "author": "Ayas_hi",
            "chapters": [
                {
                    "id": "10",
                    "num": 10,
                    "title": "第10話　初スカート、お披露目",
                    "url": f"https://example.com/{url}/10",
                },
            ],
        }


class SynopsisSource(StubSource):
    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, object]:
        metadata = await super().fetch_metadata(url, max_chapter=max_chapter)
        metadata["synopsis"] = "Original Synopsis"
        return metadata


class BatchMetadataProvider(MockTranslationProvider):
    def __init__(
        self,
        *,
        invalid_batch_json: bool = False,
        omit_ids: set[str] | None = None,
        duplicate_first_id: bool = False,
        fenced_batch_json: bool = False,
        commentary_batch_json: bool = False,
    ) -> None:
        super().__init__(key="mock", model="mock-1.0")
        self.invalid_batch_json = invalid_batch_json
        self.omit_ids = omit_ids or set()
        self.duplicate_first_id = duplicate_first_id
        self.fenced_batch_json = fenced_batch_json
        self.commentary_batch_json = commentary_batch_json
        self.prompts: list[str] = []

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.call_count += 1
        self.prompts.append(prompt)
        if self.invalid_batch_json and "<metadata_items>" in prompt:
            return {"text": "NOT JSON", "metadata": {"usage": {"total_tokens": 5}}}

        if "<metadata_items>" in prompt:
            payload = json.loads(prompt.split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0].strip())
            items = [
                {"id": item["id"], "translation": f"[TRANSLATED] {item['source_text']}"}
                for item in payload["items"]
                if item["id"] not in self.omit_ids
            ]
            if self.duplicate_first_id and items:
                duplicate = dict(items[0])
                duplicate["translation"] = f"{duplicate['translation']} duplicate"
                items.append(duplicate)
            text = json.dumps({"items": items})
            if self.fenced_batch_json:
                text = f"```json\n{text}\n```"
            if self.commentary_batch_json:
                text = f"Here is the JSON:\n{text}\nDone."
            return {"text": text, "metadata": {"usage": {"total_tokens": 7}}}

        return {"text": f"[TRANSLATED] {prompt}", "metadata": {"usage": {"total_tokens": 3}}}


class FailingMetadataProvider(MockTranslationProvider):
    def __init__(self) -> None:
        super().__init__(key="mock", model="mock-1.0")

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.call_count += 1
        raise RuntimeError("metadata provider failed " + ("x" * 800))


def _configure_catalog_projection_db(data_dir, monkeypatch):
    db_path = data_dir / "catalog_projection.sqlite"
    database_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal, engine


@pytest.fixture
def orchestration_env(monkeypatch):
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"orchestrator_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)

    storage = StorageService(data_dir)
    settings = PreferencesService(data_dir)
    settings.set_preferred_provider("mock")
    settings.set_preferred_model("mock-1.0")
    cache = TranslationCache(data_dir)
    usage = UsageService(data_dir)
    catalog_sessionmaker, catalog_engine = _configure_catalog_projection_db(data_dir, monkeypatch)

    try:
        yield {
            "data_dir": data_dir,
            "storage": storage,
            "settings": settings,
            "cache": cache,
            "usage": usage,
            "catalog_sessionmaker": catalog_sessionmaker,
        }
    finally:
        catalog_engine.dispose()
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_scrape_write_paths_refresh_catalog_projection(orchestration_env) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    source = StubSource()
    storage = orchestration_env["storage"]
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug="novel-1").one()
        assert novel.chapter_count == 2
        assert novel.translated_count == 0

    await orchestrator.scrape_chapters("syosetu_ncode", "novel-1", "all")
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug="novel-1").one()
        assert novel.chapter_count == 2
        assert novel.translated_count == 0


@pytest.mark.asyncio
async def test_scrape_metadata_bootstraps_glossary_candidates_nonfatally(orchestration_env) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    source = StubSource()
    storage = orchestration_env["storage"]
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    result = await orchestrator.scrape_metadata("syosetu_ncode", "bootstrap-novel", mode="update")

    assert result["bootstrap_candidate_count"] > 0
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug="bootstrap-novel").one()
        assert novel.glossary_status == "glossary_pending"
        entries = GlossaryRepository(session).list_glossary_entries_for_novel(novel.id)
        assert entries
        assert {entry.status for entry in entries} == {"candidate"}


@pytest.mark.asyncio
@hypothesis_settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None, deadline=None)
@given(st.integers(min_value=0, max_value=3))
async def test_scrape_metadata_bootstrap_exception_isolation(orchestration_env, candidate_count: int) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    source = StubSource()
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    storage.save_metadata(
        slug,
        {
            "title": "Bootstrap Exception",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{slug}/1"}],
        },
    )
    with SessionLocal() as session:
        novel = Novel(
            slug=slug,
            title="Bootstrap Exception",
            language="ja",
            publication_status="ongoing",
            glossary_status="glossary_skipped",
        )
        session.add(novel)
        session.commit()

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with patch.object(crawler_module, "extract_candidate_glossary_terms", side_effect=RuntimeError("boom")):
        result = await orchestrator.scrape_metadata("syosetu_ncode", slug, mode="update")

    assert result["bootstrap_candidate_count"] == 0
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug=slug).one()
        assert novel.glossary_status == "glossary_skipped"


@pytest.mark.asyncio
@hypothesis_settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None, deadline=None)
@given(st.sampled_from(["glossary_ready", "glossary_pending", "glossary_skipped"]))
async def test_bootstrap_invocation_gate(orchestration_env, glossary_status: str) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    storage.save_metadata(
        slug,
        {
            "title": "Bootstrap Gate",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{slug}/1"}],
        },
    )
    with SessionLocal() as session:
        novel = Novel(
            slug=slug,
            title="Bootstrap Gate",
            language="ja",
            publication_status="ongoing",
            glossary_status=glossary_status,
        )
        session.add(novel)
        session.commit()

    calls: list[list[str]] = []

    def _extract(texts, max_terms=50):
        calls.append(list(texts))
        return [_BootstrapCandidate("Pocott", "Pocott", "note")]

    source = StubSource()
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with patch.object(crawler_module, "extract_candidate_glossary_terms", side_effect=_extract):
        result = await crawler_module.bootstrap_glossary_if_needed(orchestrator, slug, {"title": "Bootstrap Gate"})

    if glossary_status == "glossary_ready":
        assert result == 0
        # extract runs before status check — calls populated regardless
    else:
        assert result == 1
        assert calls


@pytest.mark.asyncio
@hypothesis_settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None, deadline=None)
@given(st.integers(min_value=1, max_value=3))
async def test_bootstrap_produces_pending_status(orchestration_env, candidate_count: int) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    storage.save_metadata(
        slug,
        {
            "title": "Bootstrap Pending",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{slug}/1"}],
        },
    )
    with SessionLocal() as session:
        novel = Novel(
            slug=slug,
            title="Bootstrap Pending",
            language="ja",
            publication_status="ongoing",
            glossary_status="glossary_skipped",
        )
        session.add(novel)
        session.commit()

    candidates = [_BootstrapCandidate(f"Term {index}", f"Term {index}", None) for index in range(candidate_count)]

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    with patch.object(crawler_module, "extract_candidate_glossary_terms", return_value=candidates):
        added = await crawler_module.bootstrap_glossary_if_needed(orchestrator, slug, {"title": "Bootstrap Pending"})

    assert added == candidate_count
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug=slug).one()
        assert novel.glossary_status == "glossary_pending"
        entries = GlossaryRepository(session).list_glossary_entries_for_novel(novel.id)
        assert len(entries) == candidate_count


@pytest.mark.asyncio
@hypothesis_settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None, deadline=None)
@given(st.sampled_from(["glossary_pending", "glossary_ready", "glossary_skipped"]), st.booleans())
async def test_translate_guard_glossary_gate_properties(
    orchestration_env, glossary_status: str, skip_glossary_gate: bool
) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    slug = uuid4().hex
    storage.save_metadata(
        slug,
        {
            "title": "Guard Novel",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": f"https://example.com/{slug}/1"}],
        },
    )
    with SessionLocal() as session:
        novel = Novel(
            slug=slug, title="Guard Novel", language="ja", publication_status="ongoing", glossary_status=glossary_status
        )
        session.add(novel)
        session.flush()
        if glossary_status == "glossary_pending":
            GlossaryRepository(session).create_glossary_entry(
                novel_id=novel.id,
                canonical_term="Pocott",
                term_type="place",
                status="candidate",
            )
        session.commit()

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    issues = orchestrator._preflight_translation(
        novel_id=slug,
        source_key="stub",
        meta={"chapters": [{"id": "1", "title": "Chapter One", "url": f"https://example.com/{slug}/1"}]},
        selected=[
            ResolvedChapterSelection(
                chapter_id="1",
                source_episode_id="1",
                sequence_number=1,
                metadata={
                    "id": "1",
                    "title": "Chapter One",
                    "url": f"https://example.com/{slug}/1",
                },
            )
        ],
        force=False,
        source_language="Japanese",
        target_language="English",
        glossary=None,
        skip_glossary_gate=skip_glossary_gate,
    )

    gate_issues = [issue for issue in issues if issue.code == "glossary_gate_pending"]
    if glossary_status == "glossary_pending" and not skip_glossary_gate:
        assert len(gate_issues) == 1
        assert gate_issues[0].details is not None
        assert gate_issues[0].details["glossary_status"] == "glossary_pending"
        assert gate_issues[0].details["glossary_pending_count"] == 1
        assert gate_issues[0].details["glossary_review_url"] == f"/admin/novels/{slug}/glossary"
    else:
        assert gate_issues == []


@pytest.mark.asyncio
async def test_import_write_paths_refresh_catalog_projection(orchestration_env) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        input_adapter_factory=lambda key: StubDocumentAdapter(),
        provider_factory=lambda key: MockTranslationProvider(key="dummy", model="dummy"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.import_document("text", "imported-novel", "C:/story.txt")
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug="imported-novel").one()
        assert novel.chapter_count == 2
        assert novel.translated_count == 0


@pytest.mark.asyncio
async def test_translation_write_path_refreshes_catalog_projection(orchestration_env) -> None:
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "translated-novel",
        {
            "title": "Translated Novel",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"},
                {"id": "2", "num": 2, "title": "Chapter 2", "url": "https://example.com/2"},
            ],
        },
    )
    storage.save_chapter("translated-novel", "1", "raw text", title="Chapter 1")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(final_text="translated body"),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters(
        "stub",
        "translated-novel",
        "1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )
    with SessionLocal() as session:
        novel = session.query(Novel).filter_by(slug="translated-novel").one()
        assert novel.chapter_count == 2
        assert novel.translated_count == 1
        assert novel.latest_chapter_id == "1"
        assert novel.latest_chapter_number == 1
        assert novel.latest_chapter_title == "Chapter 1"
        assert novel.latest_chapter_updated_at is not None


@pytest.mark.asyncio
async def test_translate_chapters_passes_provider_lock_to_translation_service(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "locked-novel",
        {
            "title": "Locked Novel",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"},
            ],
        },
    )
    storage.save_chapter("locked-novel", "1", "raw text", title="Chapter 1")
    # Gemini requires a configured API key before contract resolution; the
    # resolver fails closed otherwise. Provide a runtime-only fake key so this
    # test can keep verifying identity forwarding to the translation service.
    orchestration_env["settings"].set_api_key("test-key-not-real", "gemini")
    translation = StubTranslationService(final_text="translated body")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters(
        "stub",
        "locked-novel",
        "1",
        provider_key="gemini",
        provider_model=GEMINI_DEFAULT_MODEL,
        source_language="Japanese",
        allow_cross_provider_fallback=False,
    )

    assert translation.calls[0]["provider_key"] == "gemini"
    assert translation.calls[0]["provider_model"] == GEMINI_DEFAULT_MODEL
    assert translation.calls[0]["allow_cross_provider_fallback"] is False


@pytest.mark.asyncio
async def test_translate_chapters_passes_platform_db_novel_id_to_translation_service(
    orchestration_env,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "glossary-owned",
        {
            "title": "Glossary Owned",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"}],
        },
    )
    storage.save_chapter("glossary-owned", "1", "Pocott arrives.", title="Chapter 1")
    with SessionLocal() as session:
        novel = Novel(
            slug="glossary-owned",
            title="Glossary Owned",
            language="ja",
            publication_status="ongoing",
            glossary_status="glossary_skipped",
        )
        session.add(novel)
        session.commit()
        platform_novel_id = novel.id
    translation = StubTranslationService(final_text="translated body")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "glossary-owned", "1", source_language="Japanese")

    assert translation.calls[0]["platform_novel_id"] == platform_novel_id


@pytest.mark.asyncio
async def test_translate_chapters_does_not_treat_source_id_as_platform_novel_id(
    orchestration_env,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "16817330655991571532",
        {
            "title": "Source ID Only",
            "source_key": "kakuyomu",
            "source_language": "Japanese",
            "source_novel_id": "16817330655991571532",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"}],
        },
    )
    storage.save_chapter("16817330655991571532", "1", "Pocott arrives.", title="Chapter 1")
    translation = StubTranslationService(final_text="translated body")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "16817330655991571532", "1", source_language="Japanese")

    assert translation.calls[0]["platform_novel_id"] is None


@pytest.mark.asyncio
async def test_translate_chapters_injects_approved_db_glossary_through_real_pipeline(
    orchestration_env,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "glossary-pipeline",
        {
            "title": "Glossary Pipeline",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"}],
        },
    )
    storage.save_chapter(
        "glossary-pipeline",
        "1",
        "Pocott and SMOKE_REVIEWING_CANDIDATE arrive.",
        title="Chapter 1",
    )
    with SessionLocal() as session:
        novel = Novel(
            slug="glossary-pipeline",
            title="Glossary Pipeline",
            language="ja",
            publication_status="ongoing",
            glossary_status="glossary_skipped",
            # start at 6 — creating an approved entry below increments it to 7
            glossary_revision=6,
        )
        session.add(novel)
        session.flush()
        repo = GlossaryRepository(session)
        approved = repo.create_glossary_entry(
            novel_id=novel.id,
            canonical_term="Pocott",
            term_type="place",
            approved_translation="Pocott",
            status="approved",
        )
        repo.add_glossary_alias(
            entry_id=approved.id,
            novel_id=novel.id,
            alias_text="Pokot",
            alias_type="banned",
        )
        repo.create_glossary_entry(
            novel_id=novel.id,
            canonical_term="SMOKE_REVIEWING_CANDIDATE",
            term_type="other",
            approved_translation="Do Not Inject",
            status="candidate",
        )
        session.commit()
    provider = PromptInjectionCaptureProvider()
    translate_stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=orchestration_env["cache"],
        settings_service=orchestration_env["settings"],
        usage_service=orchestration_env["usage"],
        storage=storage,
    )
    translation = TranslationService(
        TranslationPipeline(
            [
                FetchStage(),
                ParseStage(),
                SmartSegmentStage(),
                translate_stage,
                PostProcessStage(),
            ]
        )
    )
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters("stub", "glossary-pipeline", "1", source_language="Japanese")

    prompt = provider.user_prompts[0]
    assert prompt.count("GLOSSARY FOR THIS NOVEL") == 1
    assert "- Pocott => Pocott" in prompt
    assert 'Pocott: avoid "Pokot"' in prompt
    assert "SMOKE_REVIEWING_CANDIDATE =>" not in prompt
    assert "Do Not Inject" not in prompt
    outputs = storage.read_translation_output(
        "glossary-pipeline",
        chunk_id="c0001",
        chapter_ids=["1"],
    )
    output = outputs[-1]
    assert output["glossary_hash"]
    assert output["glossary_revision"] == 7
    assert output["glossary_injected_term_count"] == 1
    translated = storage.load_translated_chapter("glossary-pipeline", "1")
    assert translated is not None
    assert translated["glossary_revision"] == 7
    assert translated["glossary_injected_term_count"] == 1


@pytest.mark.asyncio
async def test_retranslate_chapter_preserves_platform_db_novel_id(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    SessionLocal = orchestration_env["catalog_sessionmaker"]
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "retry-glossary",
        {
            "title": "Retry Glossary",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"}],
        },
    )
    storage.save_chapter("retry-glossary", "1", "Pocott arrives.", title="Chapter 1")
    with SessionLocal() as session:
        novel = Novel(
            slug="retry-glossary",
            title="Retry Glossary",
            language="ja",
            publication_status="ongoing",
            glossary_status="glossary_skipped",
        )
        session.add(novel)
        session.commit()
        platform_novel_id = novel.id
    translation = StubTranslationService(final_text="translated body")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.retranslate_chapter("stub", "retry-glossary", "1", source_language="Japanese")

    assert translation.calls[0]["platform_novel_id"] == platform_novel_id


@pytest.mark.asyncio
async def test_runtime_orchestration_sim_scopes_full_failure_and_small_retry(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "runtime-scope-novel",
        {
            "title": "Runtime Scope Novel",
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter 1", "url": "https://example.com/1"},
                {"id": "2", "num": 2, "title": "Chapter 2", "url": "https://example.com/2"},
            ],
        },
    )
    storage.save_chapter("runtime-scope-novel", "1", "[P p0001]\nchapter one", title="Chapter 1")
    storage.save_chapter(
        "runtime-scope-novel",
        "2",
        "[P p0001]\nchapter two first paragraph\n\n[P p0002]\nchapter two second paragraph",
        title="Chapter 2",
    )
    translation = RuntimeSimulationTranslationService(storage, fail_chapter_once="2")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters(
        "stub",
        "runtime-scope-novel",
        "1",
        provider_key="mock",
        provider_model="mock-1.0",
        job_id="job_chapter_1",
        activity_id="activity_chapter_1",
        source_language="Japanese",
    )
    with pytest.raises(RuntimeError, match="simulated full chunk failure"):
        await orchestrator.translate_chapters(
            "stub",
            "runtime-scope-novel",
            "2",
            provider_key="mock",
            provider_model="mock-1.0",
            job_id="job_chapter_2_full",
            activity_id="activity_chapter_2_full",
            source_language="Japanese",
        )
    await orchestrator.translate_chapters(
        "stub",
        "runtime-scope-novel",
        "2",
        provider_key="mock",
        provider_model="mock-1.0",
        job_id="job_chapter_2_small_retry",
        activity_id="activity_chapter_2_small_retry",
        force=True,
        source_language="Japanese",
    )

    chapter_1_chunk = storage.read_translation_chunks(
        "runtime-scope-novel",
        translation_run_id="job_chapter_1",
        chapter_ids=["1"],
    )[0]
    chapter_2_full_chunk = storage.read_translation_chunks(
        "runtime-scope-novel",
        translation_run_id="job_chapter_2_full",
        chapter_ids=["2"],
    )[0]
    chapter_2_retry_chunk = storage.read_translation_chunks(
        "runtime-scope-novel",
        translation_run_id="job_chapter_2_small_retry",
        chapter_ids=["2"],
    )[0]
    assert {
        chapter_1_chunk["runtime_key"],
        chapter_2_full_chunk["runtime_key"],
        chapter_2_retry_chunk["runtime_key"],
    } == {
        "runtime-scope-novel:job_chapter_1:1:c0001",
        "runtime-scope-novel:job_chapter_2_full:2:c0001",
        "runtime-scope-novel:job_chapter_2_small_retry:2:c0001",
    }
    assert chapter_2_full_chunk["status"] == "needs_retry"
    assert chapter_2_retry_chunk["status"] == "translated"
    assert chapter_2_retry_chunk["attempt_count"] == 1

    full_attempt = storage.list_chunk_attempt_records(
        novel_id="runtime-scope-novel",
        chunk_id="c0001",
        translation_run_id="job_chapter_2_full",
        chapter_ids=["2"],
    )[0]
    retry_attempt = storage.list_chunk_attempt_records(
        novel_id="runtime-scope-novel",
        chunk_id="c0001",
        translation_run_id="job_chapter_2_small_retry",
        chapter_ids=["2"],
    )[0]
    assert full_attempt["attempt_number"] == 2
    assert full_attempt["status"] == "failed"
    assert retry_attempt["attempt_number"] == 1
    assert retry_attempt["status"] == "succeeded"

    chapter_1_output = storage.read_translation_output(
        "runtime-scope-novel",
        chunk_id="c0001",
        translation_run_id="job_chapter_1",
        chapter_ids=["1"],
    )[0]
    retry_output = storage.read_translation_output(
        "runtime-scope-novel",
        chunk_id="c0001",
        translation_run_id="job_chapter_2_small_retry",
        chapter_ids=["2"],
    )[0]
    assert chapter_1_output["translated_text"] == "translated chapter 1"
    assert retry_output["translated_text"] == "translated chapter 2"
    assert chapter_1_output["runtime_key"] != retry_output["runtime_key"]

    retry_states = storage.load_chunk_states(
        novel_id="runtime-scope-novel",
        chapter_id="2",
        translation_run_id="job_chapter_2_small_retry",
    )
    full_states = storage.load_chunk_states(
        novel_id="runtime-scope-novel",
        chapter_id="2",
        translation_run_id="job_chapter_2_full",
    )
    assert retry_states[0]["attempt_number"] == 1
    assert retry_states[0]["status"] == "translated"
    assert full_states[0]["attempt_number"] == 2
    assert full_states[0]["status"] == "needs_retry"

    assert storage.list_pipeline_events(job_id="job_chapter_1")
    assert storage.list_pipeline_events(job_id="job_chapter_2_full")
    assert storage.list_pipeline_events(job_id="job_chapter_2_small_retry")
    runtime_dir = storage._translation_runtime_dir()
    trace_dir = storage._trace_dir()
    assert (runtime_dir / "chunks.json").exists()
    assert (runtime_dir / "chunk_attempts.json").exists()
    assert (runtime_dir / "outputs.json").exists()
    assert (trace_dir / "chunk_states.json").exists()
    assert (trace_dir / "pipeline_events.json").exists()


@pytest.mark.asyncio
async def test_translation_service_generates_isolated_manual_run_ids() -> None:
    capture = RunIdCaptureStage()
    service = TranslationService(TranslationPipeline([capture]))

    first = await service.translate_chapter(source_adapter=None, chapter_url="manual-1")
    second = await service.translate_chapter(source_adapter=None, chapter_url="manual-2")
    stable = await service.translate_chapter(
        source_adapter=None,
        chapter_url="stable",
        job_id="job_stable",
        activity_id="activity_stable",
    )

    assert first.metadata["translation_run_id"].startswith("translation_run_")
    assert second.metadata["translation_run_id"].startswith("translation_run_")
    assert first.metadata["translation_run_id"] != second.metadata["translation_run_id"]
    assert stable.metadata["translation_run_id"] == "job_stable"
    assert capture.run_ids == [
        first.metadata["translation_run_id"],
        second.metadata["translation_run_id"],
        "job_stable",
    ]


def test_gemini_model_candidates_default_to_stable_flash_lite() -> None:
    candidates = model_candidates("gemini", None, [GEMINI_FALLBACK_MODEL])

    assert len(candidates) >= 1
    assert candidates[0] == GEMINI_DEFAULT_MODEL
    # When no requested_model is given, the first supported model is included
    # as an additional candidate after defaults and fallbacks.
    assert GEMINI_FALLBACK_MODEL in candidates
    assert not candidates[0].endswith("-preview")


def test_gemini_model_candidates_preserve_explicit_override() -> None:
    candidates = model_candidates("gemini", GEMINI_FALLBACK_MODEL, [GEMINI_DEFAULT_MODEL])

    assert candidates[:2] == [GEMINI_FALLBACK_MODEL, GEMINI_DEFAULT_MODEL]


@pytest.mark.asyncio
async def test_scrape_metadata_translates_title_author_and_chapter_titles(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    source = StubSource()
    storage = orchestration_env["storage"]

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")

    assert metadata["translated_title"] == "[TRANSLATED] Original Novel"
    assert metadata["translated_author"] == "[TRANSLATED] Original Author"
    assert metadata["metadata_translation_prompt_version"] == "metadata-literal-v3"
    assert metadata["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert metadata["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"
    stored = storage.load_metadata("novel-1")
    assert stored is not None
    index_entry = storage._load_index()["novel-1"]
    folder_name = index_entry["folder_name"]
    assert folder_name == stored["folder_name"]
    assert folder_name == "translated-original-novel"
    metadata_path = storage._folder_path(folder_name) / "metadata.json"
    assert metadata_path.exists()
    assert stored["translated_title"] == "[TRANSLATED] Original Novel"
    assert stored["translated_author"] == "[TRANSLATED] Original Author"
    assert stored["metadata_translation_status"] == "completed"
    assert stored["metadata_translation_prompt_version"] == "metadata-literal-v3"
    assert stored["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert stored["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"
    assert stored["authors"]["translated"] == "[TRANSLATED] Original Author"
    assert provider.call_count == 2
    assert orchestration_env["usage"].summary(all_days=True)["total_requests"] == 2


@pytest.mark.asyncio
async def test_scrape_metadata_batches_title_author_and_synopsis(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    source = SynopsisSource()
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")

    assert metadata["translated_title"] == "[TRANSLATED] Original Novel"
    assert metadata["translated_author"] == "[TRANSLATED] Original Author"
    assert metadata["translated_synopsis"] == "[TRANSLATED] Original Synopsis"
    stored = orchestration_env["storage"].load_metadata("novel-1")
    assert stored["translated_synopsis"] == "[TRANSLATED] Original Synopsis"
    assert stored["metadata_translation_status"] == "completed"
    first_batch = json.loads(provider.prompts[0].split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0])
    assert [item["id"] for item in first_batch["items"]] == ["novel_title", "author", "synopsis"]


@pytest.mark.asyncio
async def test_scrape_metadata_retranslates_source_identical_previous_metadata(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "translated_title": "Original Novel",
            "author": "Original Author",
            "translated_author": "Original Author",
            "chapters": [
                {
                    "id": "1",
                    "title": "Chapter One",
                    "translated_title": "Chapter One",
                },
                {
                    "id": "2",
                    "title": "Chapter Two",
                    "translated_title": "Chapter Two",
                },
            ],
        },
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")

    assert provider.call_count == 2
    assert metadata["translated_title"] == "[TRANSLATED] Original Novel"
    assert metadata["translated_author"] == "[TRANSLATED] Original Author"
    assert metadata["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert metadata["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"


@pytest.mark.asyncio
async def test_scrape_metadata_falls_back_between_gemini_models(orchestration_env) -> None:
    provider = GeminiFallbackProvider()
    source = StubSource()
    settings = orchestration_env["settings"]
    settings.set_preferred_provider("gemini")
    settings.set_preferred_model(GEMINI_DEFAULT_MODEL)
    settings.set_api_key("gemini-key", provider_key="gemini")
    orchestration_env["cache"].set(
        "metadata:chapter_title:English:第10話　初スカート、お披露目",
        "gemini",
        GEMINI_DEFAULT_MODEL,
        "Episode",
    )

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=settings,
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")

    assert provider.models_seen[:2] == [GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODEL]
    assert metadata["translated_title"] == f"[{GEMINI_FALLBACK_MODEL}] Original Novel"
    assert metadata["metadata_translation_status"] == "completed"


@pytest.mark.asyncio
async def test_scrape_metadata_retries_incomplete_chapter_title_translation(orchestration_env) -> None:
    provider = PartialGeminiTitleProvider()
    source = PartialTitleSource()
    settings = orchestration_env["settings"]
    settings.set_preferred_provider("gemini")
    settings.set_preferred_model(GEMINI_DEFAULT_MODEL)
    settings.set_api_key("gemini-key", provider_key="gemini")

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=settings,
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("novel18_syosetu", "n0813kx", mode="update")

    assert metadata["metadata_translation_status"] == "completed"
    assert metadata["chapters"][0]["translated_title"] == "Episode 10: First Skirt Reveal"
    assert GEMINI_DEFAULT_MODEL in provider.models_seen


@pytest.mark.asyncio
async def test_metadata_chapter_titles_batch_by_default_size(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    metadata = {
        "source_key": "syosetu_ncode",
        "chapters": [{"id": str(index), "num": index, "title": f"Chapter {index}"} for index in range(1, 31)],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    batch_prompts = [prompt for prompt in provider.prompts if "<metadata_items>" in prompt]
    assert len(batch_prompts) == 2
    first_batch = json.loads(batch_prompts[0].split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0])
    second_batch = json.loads(batch_prompts[1].split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0])
    assert len(first_batch["items"]) == 25
    assert len(second_batch["items"]) == 5
    assert translated["chapters"][29]["translated_title"] == "[TRANSLATED] Chapter 30"


@pytest.mark.asyncio
async def test_metadata_chapter_title_batch_deduplicates_exact_repeated_titles(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    metadata = {
        "source_key": "syosetu_ncode",
        "chapters": [
            {"id": "1", "num": 1, "title": "Interlude"},
            {"id": "2", "num": 2, "title": "Interlude"},
            {"id": "3", "num": 3, "title": "Finale"},
        ],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    batch = json.loads(provider.prompts[0].split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0])
    assert [item["source_text"] for item in batch["items"]] == ["Interlude", "Finale"]
    assert [chapter["translated_title"] for chapter in translated["chapters"]] == [
        "[TRANSLATED] Interlude",
        "[TRANSLATED] Interlude",
        "[TRANSLATED] Finale",
    ]


@pytest.mark.asyncio
async def test_metadata_batch_skips_reusable_and_cached_fields(orchestration_env) -> None:
    provider = BatchMetadataProvider()
    cache = orchestration_env["cache"]
    cache.set("metadata:chapter_title:English:Cached Chapter", "mock", "mock-1.0", "Cached Translation")
    metadata = {
        "source_key": "syosetu_ncode",
        "title": "Original Novel",
        "translated_title": "Translated Novel",
        "metadata_translation_prompt_version": "metadata-literal-v3",
        "chapters": [
            {"id": "1", "num": 1, "title": "Cached Chapter"},
            {"id": "2", "num": 2, "title": "Needs Batch"},
        ],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=cache,
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata, existing_metadata=metadata)

    assert provider.call_count == 1
    batch = json.loads(provider.prompts[0].split("<metadata_items>", 1)[1].split("</metadata_items>", 1)[0])
    assert [item["source_text"] for item in batch["items"]] == ["Needs Batch"]
    assert translated["translated_title"] == "Translated Novel"
    assert translated["chapters"][0]["translated_title"] == "Cached Translation"
    assert translated["chapters"][1]["translated_title"] == "[TRANSLATED] Needs Batch"


@pytest.mark.asyncio
async def test_metadata_invalid_batch_json_falls_back_to_individual_translation(orchestration_env) -> None:
    provider = BatchMetadataProvider(invalid_batch_json=True)
    metadata = {
        "source_key": "syosetu_ncode",
        "title": "Original Novel",
        "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    assert translated["translated_title"] == "[TRANSLATED] Original Novel"
    assert translated["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert provider.call_count == 8


@pytest.mark.asyncio
async def test_metadata_batch_fenced_json_is_extracted(orchestration_env) -> None:
    provider = BatchMetadataProvider(fenced_batch_json=True)
    metadata = {
        "source_key": "syosetu_ncode",
        "title": "Original Novel",
        "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    assert translated["translated_title"] == "[TRANSLATED] Original Novel"
    assert translated["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_metadata_batch_commentary_with_single_json_object_is_extracted(orchestration_env) -> None:
    provider = BatchMetadataProvider(commentary_batch_json=True)
    metadata = {
        "source_key": "syosetu_ncode",
        "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    assert translated["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_metadata_duplicate_batch_item_id_falls_back_safely(orchestration_env) -> None:
    provider = BatchMetadataProvider(duplicate_first_id=True)
    metadata = {
        "source_key": "syosetu_ncode",
        "chapters": [
            {"id": "1", "num": 1, "title": "Chapter One"},
            {"id": "2", "num": 2, "title": "Chapter Two"},
        ],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    assert translated["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert translated["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"
    assert provider.call_count == 5


@pytest.mark.asyncio
async def test_metadata_missing_batch_item_id_falls_back_safely(orchestration_env) -> None:
    provider = BatchMetadataProvider(omit_ids={"chapter:2"})
    metadata = {
        "source_key": "syosetu_ncode",
        "chapters": [
            {"id": "1", "num": 1, "title": "Chapter One"},
            {"id": "2", "num": 2, "title": "Chapter Two"},
        ],
    }
    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    translated = await orchestrator._translate_metadata_fields(metadata)

    assert translated["chapters"][0]["translated_title"] == "[TRANSLATED] Chapter One"
    assert translated["chapters"][1]["translated_title"] == "[TRANSLATED] Chapter Two"
    assert provider.call_count == 5


@pytest.mark.asyncio
async def test_scrape_metadata_passes_max_chapter_to_source(orchestration_env) -> None:
    provider = MockTranslationProvider(key="mock", model="mock-1.0")
    source = StubSource()

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update", max_chapter=46)

    assert source.requested_max_chapters == [46]


@pytest.mark.asyncio
async def test_scrape_metadata_missing_gemini_key_never_calls_dummy_provider(orchestration_env) -> None:
    provider = MockTranslationProvider(key="dummy", model="dummy")
    source = StubSource()
    settings = orchestration_env["settings"]
    settings.set_preferred_provider("gemini")
    settings.set_preferred_model("gemini-2.0-flash")
    settings.clear_api_key("gemini")

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=settings,
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")

    assert provider.call_count == 0
    assert metadata["metadata_translation_status"] == "unavailable"
    assert metadata["metadata_translation_prompt_version"] == "metadata-literal-v3"
    assert "metadata_translation_error" not in metadata
    assert "translated_title" not in metadata


@pytest.mark.asyncio
async def test_scrape_metadata_failed_translation_preserves_source_fields_without_fake_translations(
    orchestration_env,
) -> None:
    provider = FailingMetadataProvider()
    source = SynopsisSource()

    orchestrator = NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    metadata = await orchestrator.scrape_metadata("syosetu_ncode", "novel-1", mode="update")
    stored = orchestration_env["storage"].load_metadata("novel-1")

    assert metadata["title"] == "Original Novel"
    assert metadata["author"] == "Original Author"
    assert metadata["synopsis"] == "Original Synopsis"
    assert metadata["chapters"][0]["title"] == "Chapter One"
    assert metadata["metadata_translation_status"] == "failed"
    assert metadata["metadata_translation_prompt_version"] == "metadata-literal-v3"
    assert len(metadata["metadata_translation_error"]) <= 500
    assert "translated_title" not in metadata
    assert "translated_author" not in metadata
    assert "translated_synopsis" not in metadata
    assert "translated_title" not in metadata["chapters"][0]
    assert stored["metadata_translation_status"] == "failed"
    assert stored["metadata_translation_error"] == metadata["metadata_translation_error"]
    assert stored["chapters"][1]["title"] == "Chapter Two"


def test_estimate_translation_requests_counts_metadata_and_body_chunks(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "syosetu_ncode",
            "title": "Original Novel",
            "author": "Original Author",
            "synopsis": "Original Synopsis",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One"},
                {"id": "2", "num": 2, "title": "Chapter Two"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "a" * 3000)
    storage.save_chapter("novel-1", "2", "\n\n".join(["b" * 3000, "c" * 3000]))
    provider = MockTranslationProvider(key="mock", model="mock-1.0")
    translation = StubTranslationService()
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: provider,
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-1",
        chapters="all",
    )

    assert estimate["metadata_requests"]["title"] == 1
    assert estimate["metadata_requests"]["author"] == 1
    assert estimate["metadata_requests"]["synopsis"] == 1
    assert estimate["metadata_requests"]["novel_fields"] == 1
    assert estimate["metadata_requests"]["chapter_titles"] == 1
    assert estimate["metadata_requests"]["unique_chapter_titles"] == 2
    assert estimate["metadata_requests"]["chapter_title_batch_size"] == 25
    assert estimate["metadata_requests"]["metadata_batching"] is True
    assert estimate["metadata_requests"]["total"] == 2
    assert estimate["body_requests"]["estimated_chunks"] == 2
    assert estimate["body_requests"]["chapters_with_text"] == 2
    assert estimate["body_requests"]["chapters_missing_text"] == []
    assert estimate["body_requests"]["per_chapter"] == [
        {"chapter_id": "1", "source_chars": 3000, "paragraphs": 1, "chunks": 1},
        {"chapter_id": "2", "source_chars": 6002, "paragraphs": 2, "chunks": 1},
    ]
    assert estimate["total_estimated_requests"] == 4
    assert estimate["assumptions"]["provider_calls"] is False
    assert estimate["assumptions"]["metadata_batching"] is True
    assert estimate["assumptions"]["adaptive_chunking"] is True
    assert estimate["assumptions"]["adaptive_soft_target_chars"] == 5800
    assert estimate["assumptions"]["adaptive_hard_max_chars"] == 7000
    assert estimate["assumptions"]["conditional_overlap"] is True
    assert estimate["assumptions"]["default_overlap_paragraphs"] == 0
    assert estimate["assumptions"]["unsafe_boundary_overlap_paragraphs"] == 1
    assert estimate["assumptions"]["boundary_context_chars"] == 160
    assert estimate["assumptions"]["paragraph_hash_lineage"] is True
    assert estimate["assumptions"]["delta_retranslation_enabled"] is True
    assert estimate["assumptions"]["delta_require_structured_paragraph_map"] is True
    assert estimate["assumptions"]["delta_force_full_on_unsafe"] is True
    assert provider.call_count == 0
    assert translation.calls == []


def test_estimate_translation_requests_uses_adaptive_body_chunk_count(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "syosetu_ncode",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "\n\n".join(["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000]))
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-1",
        chapters="all",
    )

    assert estimate["body_requests"]["estimated_chunks"] == 2
    assert estimate["body_requests"]["per_chapter"] == [
        {"chapter_id": "1", "source_chars": 12006, "paragraphs": 4, "chunks": 2}
    ]
    assert estimate["assumptions"]["adaptive_chunking"] is True


def _save_delta_fixture(
    storage: StorageService,
    *,
    old_paragraphs: list[str],
    new_paragraphs: list[str],
    novel_id: str = "novel-delta",
) -> None:
    storage.save_metadata(
        novel_id,
        {
            "source_key": "syosetu_ncode",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
        },
    )
    storage.save_chapter(novel_id, "1", "\n\n".join(new_paragraphs))
    old_lineage = [
        {
            "chapter_id": "1",
            "paragraph_id": f"p{index:04d}",
            "paragraph_index": index,
            "source_hash": paragraph_source_hash(text),
            "char_count": len(text),
        }
        for index, text in enumerate(old_paragraphs, start=1)
    ]
    storage.save_translation_chunks(
        novel_id,
        [
            {
                "chunk_id": "c0001",
                "chapter_ids": ["1"],
                "paragraph_ids": [item["paragraph_id"] for item in old_lineage],
                "paragraph_hashes": [item["source_hash"] for item in old_lineage],
                "paragraph_lineage": old_lineage,
                "source_text": "\n\n".join(old_paragraphs),
                "status": "translated",
            }
        ],
    )


def _delta_estimate(orchestration_env, *, old_paragraphs: list[str], new_paragraphs: list[str]) -> dict[str, Any]:
    storage = orchestration_env["storage"]
    _save_delta_fixture(storage, old_paragraphs=old_paragraphs, new_paragraphs=new_paragraphs)
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )
    return orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-delta",
        chapters="all",
    )


def test_estimate_translation_requests_delta_identical_has_no_windows(orchestration_env) -> None:
    estimate = _delta_estimate(orchestration_env, old_paragraphs=["A.", "B.", "C."], new_paragraphs=["A.", "B.", "C."])

    assert estimate["body_requests"]["estimated_chunks"] == 1
    assert estimate["delta"]["available"] is True
    assert estimate["delta"]["delta_body_requests"] == 0
    assert estimate["delta"]["unchanged_paragraphs"] == 3
    assert estimate["delta"]["changed_windows"] == []
    assert estimate["total_estimated_requests"] == estimate["metadata_requests"]["total"] + 1


def test_estimate_translation_requests_delta_changed_paragraph_has_padded_window(orchestration_env) -> None:
    estimate = _delta_estimate(
        orchestration_env, old_paragraphs=["A.", "B.", "C."], new_paragraphs=["A.", "Bee.", "C."]
    )

    assert estimate["delta"]["changed_paragraphs"] == 1
    assert estimate["delta"]["delta_body_requests"] == 1
    assert estimate["delta"]["changed_windows"] == [
        {
            "chapter_id": "1",
            "start_paragraph_index": 1,
            "end_paragraph_index": 3,
            "paragraph_hashes": [
                paragraph_source_hash("A."),
                paragraph_source_hash("Bee."),
                paragraph_source_hash("C."),
            ],
            "estimated_chunks": 1,
        }
    ]


def test_estimate_translation_requests_delta_inserted_paragraph_has_window(orchestration_env) -> None:
    estimate = _delta_estimate(orchestration_env, old_paragraphs=["A.", "C."], new_paragraphs=["A.", "B.", "C."])

    assert estimate["delta"]["inserted_paragraphs"] == 1
    assert estimate["delta"]["changed_windows"][0]["start_paragraph_index"] == 1
    assert estimate["delta"]["changed_windows"][0]["end_paragraph_index"] == 3


def test_estimate_translation_requests_delta_deleted_paragraph_has_conservative_window(orchestration_env) -> None:
    estimate = _delta_estimate(orchestration_env, old_paragraphs=["A.", "B.", "C."], new_paragraphs=["A.", "C."])

    assert estimate["delta"]["deleted_paragraphs"] == 1
    assert estimate["delta"]["delta_body_requests"] == 1
    assert estimate["delta"]["changed_windows"][0]["chapter_id"] == "1"


def test_estimate_translation_requests_delta_repeated_hashes_are_ambiguous(orchestration_env) -> None:
    estimate = _delta_estimate(
        orchestration_env, old_paragraphs=["A.", "X.", "X.", "C."], new_paragraphs=["A.", "X.", "X.", "C."]
    )

    assert estimate["delta"]["ambiguous_paragraphs"] == 2
    assert estimate["delta"]["unchanged_paragraphs"] == 2
    assert estimate["delta"]["delta_body_requests"] == 1


def test_estimate_translation_requests_delta_moved_paragraph_is_ambiguous(orchestration_env) -> None:
    estimate = _delta_estimate(orchestration_env, old_paragraphs=["A.", "B.", "C."], new_paragraphs=["B.", "A.", "C."])

    assert estimate["delta"]["ambiguous_paragraphs"] >= 1
    assert estimate["delta"]["unchanged_paragraphs"] < 3
    assert estimate["delta"]["delta_body_requests"] == 1


def test_estimate_translation_requests_delta_overlapping_windows_merge(orchestration_env) -> None:
    estimate = _delta_estimate(
        orchestration_env,
        old_paragraphs=["A.", "B.", "C.", "D.", "E."],
        new_paragraphs=["A.", "Bee.", "C.", "Dee.", "E."],
    )

    assert estimate["delta"]["changed_paragraphs"] == 2
    assert len(estimate["delta"]["changed_windows"]) == 1
    assert estimate["delta"]["changed_windows"][0]["start_paragraph_index"] == 1
    assert estimate["delta"]["changed_windows"][0]["end_paragraph_index"] == 5


def test_estimate_translation_requests_delta_missing_old_lineage_unavailable(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "syosetu_ncode",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
        },
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nB.")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-delta",
        chapters="all",
    )

    assert estimate["delta"]["available"] is False
    assert estimate["delta"]["delta_body_requests"] == estimate["body_requests"]["estimated_chunks"]


def test_estimate_translation_requests_delta_older_records_without_hashes_unavailable(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "syosetu_ncode",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
        },
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nB.")
    storage.save_translation_chunks(
        "novel-delta",
        [{"chunk_id": "legacy_c0001", "chapter_ids": ["1"], "paragraph_ids": ["p0001"], "source_text": "A."}],
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

    estimate = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-delta",
        chapters="all",
    )

    assert estimate["delta"]["available"] is False
    assert "falling back to full body estimate" in " ".join(estimate["delta"]["notes"])


def test_estimate_translation_requests_delta_uses_active_segmentation_for_window_chunks(orchestration_env) -> None:
    estimate = _delta_estimate(
        orchestration_env,
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "b" * 3000, "c" * 3000, "d" * 3000, "C."],
    )

    assert estimate["body_requests"]["estimated_chunks"] == 2
    assert estimate["delta"]["delta_body_requests"] == 2


def _save_delta_execution_fixture(
    storage: StorageService,
    *,
    old_paragraphs: list[str],
    new_paragraphs: list[str],
    old_translations: list[str] | None = None,
    structured: bool = True,
    translated_chapter_text: str | None = None,
    translated_chapter_lineage_overrides: dict[str, Any] | None = None,
) -> None:
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-delta/1"}],
        },
    )
    storage.save_chapter("novel-delta", "1", "\n\n".join(new_paragraphs))
    old_lineage = [
        {
            "chapter_id": "1",
            "paragraph_id": f"p{index:04d}",
            "paragraph_index": index,
            "source_hash": paragraph_source_hash(text),
            "char_count": len(text),
        }
        for index, text in enumerate(old_paragraphs, start=1)
    ]
    storage.save_translation_chunks(
        "novel-delta",
        [
            {
                "chunk_id": "c0001",
                "chapter_ids": ["1"],
                "paragraph_ids": [item["paragraph_id"] for item in old_lineage],
                "paragraph_hashes": [item["source_hash"] for item in old_lineage],
                "paragraph_lineage": old_lineage,
                "source_text": "\n\n".join(old_paragraphs),
                "status": "translated",
            }
        ],
    )
    if structured:
        translations = old_translations or [f"old:{text}" for text in old_paragraphs]
        storage.save_translation_output(
            {
                "output_id": "old_c0001",
                "chunk_id": "c0001",
                "novel_id": "novel-delta",
                "chapter_ids": ["1"],
                "paragraph_ids": [item["paragraph_id"] for item in old_lineage],
                "paragraph_hashes": [item["source_hash"] for item in old_lineage],
                "paragraph_lineage": old_lineage,
                "translated_text": "\n\n".join(translations),
                "structured_paragraph_map": [
                    {
                        "chapter_id": "1",
                        "paragraph_id": item["paragraph_id"],
                        "translated_text": translations[index],
                    }
                    for index, item in enumerate(old_lineage)
                ],
            }
        )
    if translated_chapter_text is not None:
        raw_text = "\n\n".join(new_paragraphs)
        # Compute the real contract values the orchestrator will use so the
        # seeded lineage matches the effective contract and delta reuse /
        # resume-skip paths behave as if a prior production run stored it.
        from novelai.glossary import canonical_glossary_hash as _seed_canon_gh
        from novelai.services.orchestration.translation import _qa_policy_fingerprint as _seed_qa_fp
        from novelai.services.orchestration.translation import _resolve_effective_prompt_version as _seed_prompt_ver

        seed_prompt_version = _seed_prompt_ver(storage, storage.load_metadata("novel-delta") or {})
        seed_qa_fingerprint = _seed_qa_fp(prompt_template_version=seed_prompt_version)
        seed_glossary_hash = _seed_canon_gh(None)
        lineage_kwargs = _translation_lineage_kwargs(
            storage,
            "novel-delta",
            "1",
            raw_text=raw_text,
            translated=translated_chapter_text,
            translation_run_id="prior-run",
            raw_generation_id="",
            source_language="Japanese",
            target_language="English",
            style_preset=None,
            consistency_mode=False,
            json_output=False,
            qa_policy_fingerprint=seed_qa_fingerprint,
            auto_activate=True,
            honorific_policy=None,
            source_episode_id="1",
        )
        # Persist the canonical prompt version and glossary hash the
        # orchestrator's effective contract will compute, so reuse decisions
        # behave as a production prior run wrote this lineage.
        lineage_kwargs["prompt_template_version"] = seed_prompt_version
        lineage_kwargs["glossary_hash"] = seed_glossary_hash
        if translated_chapter_lineage_overrides:
            lineage_kwargs.update(translated_chapter_lineage_overrides)
        # Allow overrides to specify provider_key/provider_model via lineage_kwargs
        # by popping them out before the explicit kwargs collide.
        override_provider_key = lineage_kwargs.pop("provider_key", "mock")
        override_provider_model = lineage_kwargs.pop("provider_model", "mock-1.0")
        storage.save_translated_chapter(
            "novel-delta",
            "1",
            translated_chapter_text,
            provider_key=override_provider_key,
            provider_model=override_provider_model,
            **lineage_kwargs,
        )


async def _run_delta_translate(orchestration_env, translation: Any) -> tuple[StorageService, Any]:
    storage = orchestration_env["storage"]
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )
    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
    )
    return storage, translation


@pytest.mark.asyncio
async def test_delta_disabled_preserves_full_translation_behavior(orchestration_env, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRANSLATION_DELTA_RETRANSLATION_ENABLED", False)
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, StubTranslationService(final_text="full translation")
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "full translation"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "delta_disabled"


@pytest.mark.asyncio
async def test_delta_unchanged_chapter_reuses_whole_old_output(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old whole chapter",
    )

    storage = orchestration_env["storage"]
    versions_before = storage.list_translated_chapter_versions("novel-delta", "1")
    assert len(versions_before) == 1
    version_id_before = versions_before[0]["version_id"]

    translation = StubTranslationService(final_text="full translation")
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
    # Section 6: whole-chapter reuse is a TRUE no-op — no new version is
    # persisted and the stored version identity is preserved untouched.
    versions_after = storage.list_translated_chapter_versions("novel-delta", "1")
    assert [version["version_id"] for version in versions_after] == [version_id_before]
    assert saved["version_id"] == version_id_before
    assert saved["translation_run_id"] == "prior-run"
    # The reuse is recorded in the run manifest with its own status.
    assert summary["reused"] == 1
    assert summary["chapter_progress"]["1"]["status"] == "reused"
    manifest = storage.load_translation_run_manifest("novel-delta", summary["translation_run_id"])
    assert manifest is not None
    assert manifest.reused_chapter_ids == ["1"]
    assert manifest.reused_count == 1
    assert manifest.completed_count == 0
    assert manifest.chapter_ids == []


@pytest.mark.asyncio
async def test_delta_changed_paragraph_translates_window_and_reassembles(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, StubTranslationService(paragraph_prefix="new:")
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new:A.\n\nnew:Bee.\n\nnew:C."
    assert len(translation.calls) == 1
    # Section 5: the changed window executes the EFFECTIVE output policy —
    # no json_output supplied resolves to False, never a hard-coded True.
    assert translation.calls[0]["json_output"] is False
    assert saved["confidence_details"]["delta"]["mode"] == "delta"
    assert saved["confidence_details"]["delta"]["newly_translated_paragraph_ids"] == ["p0001", "p0002", "p0003"]


@pytest.mark.asyncio
async def test_delta_inserted_paragraph_reassembles_correctly(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "C."],
        new_paragraphs=["A.", "B.", "C."],
        old_translations=["old:A.", "old:C."],
    )

    storage, _ = await _run_delta_translate(orchestration_env, StubTranslationService(paragraph_prefix="new:"))

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "new:A.\n\nnew:B.\n\nnew:C."


@pytest.mark.asyncio
async def test_delta_deleted_paragraph_reassembles_without_stale_translation(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
    )

    storage, _ = await _run_delta_translate(orchestration_env, StubTranslationService(paragraph_prefix="new:"))

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    text = saved["text"]
    assert "old:B." not in text
    assert text == "new:A.\n\nnew:C."


@pytest.mark.asyncio
async def test_delta_ambiguous_region_falls_back_to_full_translation(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "X.", "X.", "C."],
        new_paragraphs=["A.", "X.", "X.", "C."],
        old_translations=["old:A.", "old:X1", "old:X2", "old:C."],
    )

    storage, translation = await _run_delta_translate(
        orchestration_env, StubTranslationService(final_text="full fallback")
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "full fallback"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "ambiguous_or_moved_region"


@pytest.mark.asyncio
async def test_delta_missing_lineage_falls_back_to_full_translation(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-delta",
        {
            "source_key": "stub",
            "source_language": "Japanese",
            "chapters": [{"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-delta/1"}],
        },
    )
    storage.save_chapter("novel-delta", "1", "A.\n\nB.")

    storage, _ = await _run_delta_translate(orchestration_env, StubTranslationService(final_text="full fallback"))

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "full fallback"
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "missing_lineage"


@pytest.mark.asyncio
async def test_delta_missing_structured_map_falls_back_for_changed_chapter(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        structured=False,
    )

    storage, _ = await _run_delta_translate(orchestration_env, StubTranslationService(final_text="full fallback"))

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "full fallback"
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "missing_structured_paragraph_map"


@pytest.mark.asyncio
async def test_delta_window_missing_structured_output_falls_back(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B.", "C."],
        new_paragraphs=["A.", "Bee.", "C."],
        old_translations=["old:A.", "old:B.", "old:C."],
    )

    storage, _ = await _run_delta_translate(orchestration_env, StubTranslationService(final_text="plain window"))

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "plain window"
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "changed_window_qa_failed"


@pytest.mark.asyncio
async def test_force_retranslate_bypasses_delta_reuse(orchestration_env) -> None:
    _save_delta_execution_fixture(
        orchestration_env["storage"],
        old_paragraphs=["A.", "B."],
        new_paragraphs=["A.", "B."],
        translated_chapter_text="old whole chapter",
    )
    storage = orchestration_env["storage"]
    translation = StubTranslationService(final_text="forced full")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.translate_chapters(
        source_key="stub",
        novel_id="novel-delta",
        chapters="1",
        provider_key="mock",
        provider_model="mock-1.0",
        source_language="Japanese",
        force=True,
    )

    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved["text"] == "forced full"
    assert len(translation.calls) == 1
    assert saved["confidence_details"]["delta"]["fallback_reason"] == "force_full_translation"


def test_estimate_translation_requests_counts_batched_unique_chapter_titles(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "syosetu_ncode",
            "chapters": [
                {"id": str(index), "num": index, "title": "Repeated" if index <= 10 else f"Chapter {index}"}
                for index in range(1, 31)
            ],
        },
    )
    for index in range(1, 31):
        storage.save_chapter("novel-1", str(index), "text")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-1",
        chapters="all",
    )

    assert estimate["metadata_requests"]["unique_chapter_titles"] == 21
    assert estimate["metadata_requests"]["chapter_titles"] == 1
    assert estimate["metadata_requests"]["total"] == 1
    assert estimate["body_requests"]["estimated_chunks"] == 30


def test_estimate_translation_requests_reports_missing_raw_chapter_text(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "kakuyomu",
            "title": "Original Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One"},
                {"id": "2", "num": 2, "title": "Chapter Two"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "available text")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    estimate = orchestrator.estimate_translation_requests(
        source_key="kakuyomu",
        novel_id="novel-1",
        chapters="all",
    )

    assert estimate["body_requests"]["estimated_chunks"] == 1
    assert estimate["body_requests"]["chapters_with_text"] == 1
    assert estimate["body_requests"]["chapters_missing_text"] == ["2"]
    assert estimate["body_requests"]["per_chapter"][0]["chapter_id"] == "1"


def test_estimate_translation_requests_can_exclude_or_include_translated_chapters(orchestration_env) -> None:
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "syosetu_ncode",
            "title": "Original Novel",
            "metadata_translation_prompt_version": "metadata-literal-v2",
            "translated_title": "Translated Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "translated_title": "Translated One"},
                {"id": "2", "num": 2, "title": "Chapter Two", "translated_title": "Translated Two"},
            ],
        },
    )
    storage.save_chapter("novel-1", "1", "already translated text")
    storage.save_chapter("novel-1", "2", "pending text")
    storage.save_translated_chapter("novel-1", "1", "Translated body", provider_key="mock", provider_model="mock-1.0")
    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=StubTranslationService(),
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    excluded = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-1",
        chapters="all",
    )
    included = orchestrator.estimate_translation_requests(
        source_key="syosetu_ncode",
        novel_id="novel-1",
        chapters="all",
        include_already_translated=True,
    )

    assert excluded["chapters_selected"] == 2
    assert excluded["chapters_included"] == 1
    assert excluded["body_requests"]["chapters_skipped_translated"] == ["1"]
    assert excluded["body_requests"]["per_chapter"] == [
        {"chapter_id": "2", "source_chars": len("pending text"), "paragraphs": 1, "chunks": 1}
    ]
    assert included["chapters_included"] == 2
    assert included["body_requests"]["chapters_skipped_translated"] == []
    assert [item["chapter_id"] for item in included["body_requests"]["per_chapter"]] == ["1", "2"]


@pytest.mark.asyncio
async def test_scrape_chapters_downloads_and_stores_image_assets(orchestration_env) -> None:
    source = StubSource()
    chapter_url = "https://example.com/novel-1/1"
    source.chapter_payloads[chapter_url] = {
        "text": "Before\n\n[Image: Scene illustration]\n\nAfter",
        "images": [
            {
                "index": 0,
                "placeholder": "[Image: Scene illustration]",
                "original_url": "https://assets.example.com/scene.jpg",
                "alt": "Scene illustration",
            }
        ],
    }
    source.assets["https://assets.example.com/scene.jpg"] = {
        "url": "https://assets.example.com/scene.jpg",
        "content": b"scene-bytes",
        "content_type": "image/jpeg",
    }

    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": chapter_url},
            ],
        },
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.scrape_chapters("stub", "novel-1", "1", mode="update")

    chapter = storage.load_chapter("novel-1", "1")
    assert chapter is not None
    assert chapter["text"] == "Before\n\n[Image: Scene illustration]\n\nAfter"
    assert chapter["images"][0]["local_path"] == "assets/images/1/0000.jpg"
    assert "download_error" not in chapter["images"][0]

    assert storage.resolve_asset_path("novel-1", chapter["images"][0]["local_path"]) is not None


@pytest.mark.asyncio
async def test_scrape_chapters_records_download_error_for_html_asset_response(orchestration_env) -> None:
    source = StubSource()
    chapter_url = "https://example.com/novel-1/1"
    source.chapter_payloads[chapter_url] = {
        "text": "[Image: Blocked image]",
        "images": [
            {
                "index": 0,
                "placeholder": "[Image: Blocked image]",
                "original_url": "https://assets.example.com/blocked.jpg",
                "alt": "Blocked image",
            }
        ],
    }
    source.assets["https://assets.example.com/blocked.jpg"] = {
        "url": "https://assets.example.com/blocked.jpg",
        "content": b"<html>blocked</html>",
        "content_type": "text/html; charset=utf-8",
    }

    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": chapter_url},
            ],
        },
    )

    orchestrator = NovelOrchestrationService(
        storage=storage,
        translation=UnusedTranslationService(),
        source_factory=lambda key: source,
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )

    await orchestrator.scrape_chapters("stub", "novel-1", "1", mode="update")

    chapter = storage.load_chapter("novel-1", "1")
    assert chapter is not None
    assert chapter["images"][0]["download_error"] == "Asset response was HTML instead of image content."
    assert chapter["images"][0].get("local_path") is None


@pytest.mark.asyncio
async def test_translate_chapters_preflight_blocks_missing_source_language(orchestration_env) -> None:
    source = StubSource()
    storage = orchestration_env["storage"]
    storage.save_metadata(
        "novel-1",
        {
            "title": "Original Novel",
            "chapters": [
                {"id": "1", "num": 1, "title": "Chapter One", "url": "https://example.com/novel-1/1"},
            ],
        },
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

    with pytest.raises(RuntimeError, match="missing_source_language"):
        await orchestrator.translate_chapters("stub", "novel-1", "1")


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
            {"source": "勇者", "target": "hero", "status": "pending", "locked": True},
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


def _s6_orchestrator(orchestration_env, translation: Any) -> NovelOrchestrationService:
    return NovelOrchestrationService(
        storage=orchestration_env["storage"],
        translation=translation,
        source_factory=lambda key: StubSource(),
        provider_factory=lambda key: MockTranslationProvider(key="mock", model="mock-1.0"),
        settings_service=orchestration_env["settings"],
        translation_cache=orchestration_env["cache"],
        usage_service=orchestration_env["usage"],
    )


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
    honorific_policy: str | None = None,
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
    assert saved["honorific_policy"] is None
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


def _parse_marker_source(source_text: str) -> tuple[str | None, list[str], dict[str, str]]:
    """Parse ``[CHAPTER <id>]`` / ``[P <id>]`` blocks out of a prompt source."""
    chapter_id: str | None = None
    ids: list[str] = []
    bodies: dict[str, str] = {}
    current_id: str | None = None
    current_body: list[str] = []
    for line in (source_text or "").splitlines():
        paragraph_match = re.match(r"^\[P\s+([^\]]+)\]\s*$", line)
        if paragraph_match:
            if current_id is not None:
                bodies[current_id] = "\n".join(current_body).strip()
            matched_paragraph_id = paragraph_match.group(1)
            if matched_paragraph_id is None:
                continue
            current_id = matched_paragraph_id.strip()
            current_body = []
            if current_id is not None:
                ids.append(current_id)
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
        bodies[current_id] = "\n".join(current_body).strip()
    return chapter_id, ids, bodies


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
        chapter_id, marker_ids, bodies = _parse_marker_source(source_text)

        emitted_ids: list[str] = []
        for pid in marker_ids:
            if pid in self.drop_paragraph_ids:
                continue
            emitted_ids.append(pid)
            if pid == self.duplicate_paragraph_id:
                emitted_ids.append(pid)
        if self.reorder:
            emitted_ids = list(reversed(emitted_ids))
        extra_id = self.extra_paragraph_id
        if extra_id:
            emitted_ids.append(extra_id)

        body_for = lambda pid: f"{self.prefix}{bodies.get(pid, pid)}"  # noqa: E731 - intentional local helper
        if json_output:
            paragraph_map = [
                {
                    "chapter_id": chapter_id or "1",
                    "paragraph_id": pid,
                    "translated_text": body_for(pid),
                }
                for pid in emitted_ids
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
        for pid in emitted_ids:
            lines.append(f"[P {pid}]")
            lines.append(body_for(pid))
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
async def test_pr41_real_pipeline_oversized_paragraph_fails_closed(orchestration_env, monkeypatch) -> None:
    """Section 6 real pipeline fail-closed: an oversized paragraph in the
    changed window is split by SmartSegmentStage while preserving the source
    paragraph_id on every piece — the override no longer matches 1:1, the
    segmenter's own ids win, and the strict validation fails closed instead of
    persisting a wrong mapping. (Splitting the delta window into valid
    sub-paragraphs is recorded as non-blocking optimization debt.)"""
    monkeypatch.setattr(settings, "TRANSLATION_MAX_ATTEMPTS_PER_CHUNK", 1)
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
    with pytest.raises(RuntimeError):
        await orchestrator.translate_chapters(
            source_key="stub",
            novel_id="novel-delta",
            chapters="1",
            provider_key="mock",
            provider_model="mock-1.0",
            source_language="Japanese",
        )

    # Fail closed: the seeded version stays; no wrong mapping was persisted.
    saved = storage.load_translated_chapter("novel-delta", "1")
    assert saved is not None
    assert saved["text"] == "old whole orp"
    assert len(storage.list_translated_chapter_versions("novel-delta", "1")) == 1


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

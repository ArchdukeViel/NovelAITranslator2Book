"""Tests for pipeline stages."""

import hashlib
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given, settings as hypothesis_settings, strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.config.settings import settings
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.db.base import Base
from novelai.db.models.novel import Novel
from novelai.prompts.models import TranslationRequest
from novelai.providers.base import TranslationProvider
from novelai.services.glossary_prompt_injection import GlossaryPromptInjectionService
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.storage.service import StorageService
from novelai.translation.pipeline.context import PipelineState, TranslationChunk, paragraph_source_hash
from novelai.translation.pipeline.pipeline import TranslationPipeline
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.translation.pipeline.stages.fetch import FetchStage
from novelai.translation.pipeline.stages.parse import ParseStage
from novelai.translation.pipeline.stages.segment import SegmentStage, SmartSegmentStage
from novelai.translation.pipeline.stages.translate import TranslateStage
from novelai.translation.scheduler import SchedulerPausedError
from tests.conftest import MockSourceAdapter


class _FallbackContractProvider(TranslationProvider):
    def __init__(self, key: str, *, error_code: ProviderErrorCode | None = None) -> None:
        self._key = key
        self.error_code = error_code
        self.models_seen: list[str | None] = []

    @property
    def key(self) -> str:
        return self._key

    def available_models(self) -> list[str]:
        if self.key == "gemini":
            return ["gemini-3.1-flash-lite", "gemma-4-31b-it", "gemini-2.5-flash-lite"]
        return ["google/gemma-4-31b-it"]

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        self.models_seen.append(model)
        if self.error_code is not None:
            raise ProviderError(
                self.error_code,
                provider_key=self.key,
                provider_model=model or "unknown",
                message=self.error_code.value,
            )
        return {"text": "Translated paragraph.", "metadata": {"usage": {"total_tokens": 3}}}


class _PromptCaptureProvider(TranslationProvider):
    def __init__(self) -> None:
        self.requests: list[TranslationRequest | None] = []
        self.prompts: list[str] = []

    @property
    def key(self) -> str:
        return "dummy"

    def available_models(self) -> list[str]:
        return ["dummy"]

    async def translate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        self.prompts.append(prompt)
        request = kwargs.get("request")
        self.requests.append(request if isinstance(request, TranslationRequest) else None)
        return {"text": "Translated paragraph.", "metadata": {"usage": {"total_tokens": 3}}}


def _fallback_stage_env(tmp_path):
    prefs = PreferencesService(tmp_path / "prefs")
    prefs.set_provider_key("gemini")
    prefs.set_provider_model(settings.PROVIDER_GEMINI_DEFAULT_MODEL)
    prefs.set_api_key("gemini-key", provider_key="gemini")
    return {
        "prefs": prefs,
        "cache": TranslationCache(tmp_path / "cache"),
        "usage": UsageService(tmp_path / "usage"),
        "storage": StorageService(tmp_path / "storage"),
    }


def _fallback_context() -> PipelineState:
    return PipelineState(
        chapter_url="test",
        novel_id="novel1",
        chapter_id="chapter_001",
        provider_key="gemini",
        provider_model=settings.PROVIDER_GEMINI_DEFAULT_MODEL,
        translation_chunks=[
            TranslationChunk(
                chunk_id="c0001",
                novel_id="novel1",
                chapter_ids=["chapter_001"],
                paragraph_ids=["p0001"],
                source_text="源テキスト",
                char_count=4,
            )
        ],
        metadata={"source_language": "Japanese", "target_language": "English"},
    )


def _glossary_test_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    novel = Novel(slug="glossary-pipeline", title="Glossary Pipeline", language="ja", status="ongoing")
    session.add(novel)
    session.flush()
    repo = GlossaryRepository(session)
    service = GlossaryPromptInjectionService(repo)
    return engine, session, novel, repo, service


def _create_pipeline_glossary_entry(
    repo: GlossaryRepository,
    novel_id: int,
    term: str,
    translation: str | None,
    *,
    status: str = "approved",
):
    return repo.create_glossary_entry(
        novel_id=novel_id,
        canonical_term=term,
        term_type="other",
        approved_translation=translation,
        status=status,
    )


def _glossary_pipeline_context(platform_novel_id: int, source_text: str = "seireikai and maso") -> PipelineState:
    return PipelineState(
        chapter_url="test",
        novel_id="storage-novel-id",
        chapter_id="chapter_001",
        provider_key="dummy",
        provider_model="dummy",
        translation_chunks=[
            TranslationChunk(
                chunk_id="c0001",
                novel_id="storage-novel-id",
                chapter_ids=["chapter_001"],
                paragraph_ids=["p0001"],
                source_text=source_text,
                char_count=len(source_text),
            )
        ],
        metadata={
            "source_language": "Japanese",
            "target_language": "English",
            "platform_novel_id": platform_novel_id,
        },
    )


@pytest.mark.asyncio
async def test_translate_stage_injects_approved_db_glossary_block_once(tmp_path):
    engine, session, novel, repo, service = _glossary_test_service()
    try:
        approved = _create_pipeline_glossary_entry(repo, novel.id, "seireikai", "Spirit Realm")
        _create_pipeline_glossary_entry(repo, novel.id, "candidate-term", "Candidate Translation", status="candidate")
        _create_pipeline_glossary_entry(repo, novel.id, "recommended-term", "Recommended Translation", status="recommended")
        _create_pipeline_glossary_entry(repo, novel.id, "rejected-term", "Rejected Translation", status="rejected")
        _create_pipeline_glossary_entry(repo, novel.id, "deprecated-term", "Deprecated Translation", status="deprecated")
        _create_pipeline_glossary_entry(repo, novel.id, "blank-translation", None)
        repo.add_glossary_alias(
            entry_id=approved.id,
            novel_id=novel.id,
            alias_text="Spirit World",
            alias_type="banned",
        )
        repo.add_glossary_alias(
            entry_id=approved.id,
            novel_id=novel.id,
            alias_text="spirit-world-source",
            alias_type="source_variant",
        )
        session.commit()
        env = _fallback_stage_env(tmp_path)
        provider = _PromptCaptureProvider()
        stage = TranslateStage(
            provider_factory=lambda _key: provider,
            cache=env["cache"],
            settings_service=env["prefs"],
            usage_service=env["usage"],
            storage=env["storage"],
            glossary_prompt_service=service,
        )

        result = await stage.run(_glossary_pipeline_context(novel.id, "spirit-world-source appears."))

        assert result.translations == ["Translated paragraph."]
        assert len(provider.requests) == 1
        request = provider.requests[0]
        assert request is not None
        assert request.user_prompt.count("GLOSSARY FOR THIS NOVEL") == 1
        assert "- seireikai => Spirit Realm" in request.user_prompt
        assert 'seireikai: avoid "Spirit World"' in request.user_prompt
        assert "candidate-term" not in request.user_prompt
        assert "recommended-term" not in request.user_prompt
        assert "rejected-term" not in request.user_prompt
        assert "deprecated-term" not in request.user_prompt
        assert "blank-translation" not in request.user_prompt
        assert "spirit-world-source =>" not in request.user_prompt
        records = result.metadata["glossary_prompt_blocks"]
        assert records == [
            {
                "chunk_id": "c0001",
                "terms_injected": 1,
                "skipped_count": 1,
                "truncated": False,
                "conflict_warning_count": 0,
                "empty": False,
                "glossary_hash": records[0]["glossary_hash"],
            }
        ]
        output = env["storage"].read_translation_output(
            "storage-novel-id",
            chunk_id="c0001",
            translation_run_id="run_manual",
            chapter_ids=["chapter_001"],
        )[-1]
        assert output["translated_text"] == "Translated paragraph."
        assert output["glossary_hash"] == records[0]["glossary_hash"]
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_translate_stage_uses_safe_empty_behavior_without_approved_glossary(tmp_path):
    engine, session, novel, repo, service = _glossary_test_service()
    try:
        _create_pipeline_glossary_entry(repo, novel.id, "candidate-term", "Candidate Translation", status="candidate")
        session.commit()
        env = _fallback_stage_env(tmp_path)
        provider = _PromptCaptureProvider()
        stage = TranslateStage(
            provider_factory=lambda _key: provider,
            cache=env["cache"],
            settings_service=env["prefs"],
            usage_service=env["usage"],
            storage=env["storage"],
            glossary_prompt_service=service,
        )

        result = await stage.run(_glossary_pipeline_context(novel.id))

        request = provider.requests[0]
        assert request is not None
        assert "GLOSSARY FOR THIS NOVEL" not in request.user_prompt
        assert result.metadata["glossary_prompt_blocks"][0]["empty"] is True
        assert result.translations == ["Translated paragraph."]
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_translate_stage_preserves_budget_warnings_without_breaking_call(tmp_path):
    engine, session, novel, repo, service = _glossary_test_service()
    try:
        _create_pipeline_glossary_entry(repo, novel.id, "Alpha", "A")
        _create_pipeline_glossary_entry(repo, novel.id, "Beta", "B")
        session.commit()
        env = _fallback_stage_env(tmp_path)
        provider = _PromptCaptureProvider()
        stage = TranslateStage(
            provider_factory=lambda _key: provider,
            cache=env["cache"],
            settings_service=env["prefs"],
            usage_service=env["usage"],
            storage=env["storage"],
            glossary_prompt_service=service,
        )
        context = _glossary_pipeline_context(novel.id, "Alpha Beta")
        context.metadata["glossary_prompt_max_terms"] = 1

        result = await stage.run(context)

        assert result.translations == ["Translated paragraph."]
        assert result.metadata["glossary_prompt_blocks"][0]["terms_injected"] == 1
        assert result.metadata["glossary_prompt_blocks"][0]["skipped_count"] == 1
        assert result.metadata["glossary_prompt_blocks"][0]["truncated"] is True
        assert "glossary_prompt_truncated" in result.metadata["glossary_prompt_warnings"]
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_translate_stage_glossary_hash_changes_only_for_approved_prompt_rules():
    engine, session, novel, repo, service = _glossary_test_service()
    try:
        _create_pipeline_glossary_entry(repo, novel.id, "seireikai", "Spirit Realm")
        session.commit()
        stage = TranslateStage(provider_factory=lambda _key: _PromptCaptureProvider(), glossary_prompt_service=service)
        context = _glossary_pipeline_context(novel.id, "seireikai candidate-term")

        first = stage._build_prompt_glossary_block(context, "seireikai candidate-term")
        first_hash = stage._glossary_hash(context, first.rendered_text if first is not None else "")
        second = stage._build_prompt_glossary_block(context, "seireikai candidate-term")
        second_hash = stage._glossary_hash(context, second.rendered_text if second is not None else "")
        candidate = _create_pipeline_glossary_entry(
            repo,
            novel.id,
            "candidate-term",
            "Candidate Translation",
            status="candidate",
        )
        session.commit()
        candidate_only = stage._build_prompt_glossary_block(context, "seireikai candidate-term")
        candidate_only_hash = stage._glossary_hash(
            context,
            candidate_only.rendered_text if candidate_only is not None else "",
        )
        repo.change_glossary_entry_status(candidate.id, novel_id=novel.id, status="approved")
        session.commit()
        approved_changed = stage._build_prompt_glossary_block(context, "seireikai candidate-term")
        approved_changed_hash = stage._glossary_hash(
            context,
            approved_changed.rendered_text if approved_changed is not None else "",
        )

        assert first_hash == second_hash
        assert candidate_only_hash == first_hash
        assert approved_changed_hash != first_hash
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.mark.asyncio
@hypothesis_settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None, deadline=None)
@given(st.integers(min_value=0, max_value=10), st.integers(min_value=0, max_value=4))
async def test_translate_stage_audit_metadata_matches_db_state(tmp_path, revision: int, term_count: int) -> None:
    engine, session, novel, repo, service = _glossary_test_service()
    try:
        novel.glossary_revision = revision
        source_terms = [f"Term {index}" for index in range(term_count)]
        for term in source_terms:
            _create_pipeline_glossary_entry(repo, novel.id, term, term)
        session.commit()

        env = _fallback_stage_env(tmp_path / uuid4().hex)
        stage = TranslateStage(
            provider_factory=lambda _key: _PromptCaptureProvider(),
            cache=env["cache"],
            settings_service=env["prefs"],
            usage_service=env["usage"],
            storage=env["storage"],
            glossary_prompt_service=service,
        )
        context = _glossary_pipeline_context(novel.id, " ".join(source_terms) or "fallback text")
        context.metadata["glossary_revision"] = revision

        result = await stage.run(context)

        output = env["storage"].read_translation_output(
            "storage-novel-id",
            chunk_id="c0001",
            translation_run_id="run_manual",
            chapter_ids=["chapter_001"],
        )[-1]
        prompt_block = result.metadata["glossary_prompt_blocks"][0]
        assert output["glossary_revision"] == revision
        assert output["glossary_injected_term_count"] == prompt_block["terms_injected"]
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_translate_stage_scopes_existing_output_by_run_and_chapter(tmp_path):
    env = _fallback_stage_env(tmp_path)
    storage = env["storage"]
    stage = TranslateStage(
        provider_factory=lambda _key: _FallbackContractProvider("dummy"),
        cache=env["cache"],
        settings_service=env["prefs"],
        usage_service=env["usage"],
        storage=storage,
    )
    source_text = "[P p0001]\nこんにちは。"
    source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    empty_glossary_hash = hashlib.sha256(b"").hexdigest()
    storage.save_translation_output(
        {
            "output_id": "c0001:attempt_0001",
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "translation_run_id": "run_chapter_1",
            "chapter_ids": ["chapter_001"],
            "translated_text": "Chapter 1 translation.",
            "source_text_hash": source_hash,
            "prompt_version": "translation_request_v1",
            "glossary_hash": empty_glossary_hash,
            "json_output": False,
            "consistency_mode": False,
        }
    )
    context = PipelineState(
        chapter_url="test",
        novel_id="novel1",
        chapter_id="chapter_002",
        metadata={"translation_run_id": "run_chapter_2"},
    )
    context.chunk_states["c0001"] = {
        "chunk_id": "c0001",
        "novel_id": "novel1",
        "translation_run_id": "run_chapter_2",
        "chapter_ids": ["chapter_002"],
        "status": "translated",
    }

    assert stage._load_existing_chunk_output(
        context,
        chunk_id="c0001",
        chunk_text=source_text,
        chapter_ids=["chapter_002"],
    ) is None

    storage.save_translation_output(
        {
            "output_id": "c0001:attempt_0001",
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "translation_run_id": "run_chapter_2",
            "chapter_ids": ["chapter_002"],
            "translated_text": "Chapter 2 translation.",
            "source_text_hash": source_hash,
            "prompt_version": "translation_request_v1",
            "glossary_hash": empty_glossary_hash,
            "json_output": False,
            "consistency_mode": False,
        }
    )

    assert stage._load_existing_chunk_output(
        context,
        chunk_id="c0001",
        chunk_text=source_text,
        chapter_ids=["chapter_002"],
    ) == "Chapter 2 translation."


def test_translate_stage_does_not_load_full_chunk_state_for_small_chunk_retry(tmp_path):
    env = _fallback_stage_env(tmp_path)
    storage = env["storage"]
    stage = TranslateStage(
        provider_factory=lambda _key: _FallbackContractProvider("dummy"),
        cache=env["cache"],
        settings_service=env["prefs"],
        usage_service=env["usage"],
        storage=storage,
    )
    storage.upsert_chunk_state(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "translation_run_id": "run_full_chunk",
            "chapter_ids": ["chapter_001"],
            "status": "needs_retry",
            "attempt_number": 3,
        }
    )
    context = PipelineState(
        chapter_url="test",
        novel_id="novel1",
        chapter_id="chapter_001",
        metadata={"translation_run_id": "run_small_chunk"},
    )

    stage._load_persisted_chunk_states(context)

    assert context.chunk_states == {}


class _FailingStage(PipelineStage):
    async def run(self, context: PipelineState) -> PipelineState:
        raise RuntimeError("stage boom")


@pytest.fixture
def mock_source():
    """Provide mock source adapter."""
    source = MockSourceAdapter()
    source.add_chapter(
        "http://example.com/ch1",
        "Chapter 1 content\n\n段落2の内容です。\n\nMore content here.",
    )
    return source


@pytest.fixture
def pipeline_context():
    """Provide pipeline context."""
    return PipelineState(chapter_url="http://example.com/ch1")


@pytest.mark.asyncio
async def test_fetch_stage(mock_source, pipeline_context):
    """Test FetchStage."""
    fetch = FetchStage()
    pipeline_context.metadata["_source_adapter"] = mock_source

    result = await fetch.run(pipeline_context)

    assert result.raw_text is not None
    assert len(result.raw_text) > 0
    assert "Chapter 1" in result.raw_text
    assert mock_source.call_count == 1


@pytest.mark.asyncio
async def test_parse_stage(pipeline_context):
    """Test ParseStage."""
    parse = ParseStage()
    pipeline_context.raw_text = "Hello <ruby>world</ruby>!\n\n  Multiple   spaces  \n\nOK"

    result = await parse.run(pipeline_context)

    assert result.normalized_text is not None
    assert "<ruby>" not in result.normalized_text  # Ruby text removed
    assert "Multiple" in result.normalized_text  # Whitespace normalized


@pytest.mark.asyncio
async def test_segment_stage():
    """Test SegmentStage."""
    segment = SegmentStage()
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"

    result = await segment.run(context)

    assert result.chunks is not None
    assert len(result.paragraphs) == 3
    assert [paragraph.paragraph_id for paragraph in result.paragraphs] == ["p0001", "p0002", "p0003"]
    assert [paragraph.chapter_id for paragraph in result.paragraphs] == ["chapter_001"] * 3
    assert len(result.translation_chunks) == 1
    assert result.translation_chunks[0].chunk_id == "c0001"
    assert result.translation_chunks[0].novel_id == "novel1"
    assert result.translation_chunks[0].chapter_ids == ["chapter_001"]
    assert result.translation_chunks[0].paragraph_ids == ["p0001", "p0002", "p0003"]
    assert result.chunks == [result.translation_chunks[0].source_text]
    assert "[CHAPTER chapter_001]" in result.chunks[0]
    assert "[P p0001]" in result.chunks[0]
    assert "Paragraph 1" in result.chunks[0]


@pytest.mark.asyncio
async def test_segment_stage_empty():
    """Test SegmentStage with empty text."""
    segment = SegmentStage()
    context = PipelineState(chapter_url="test")
    context.normalized_text = ""

    result = await segment.run(context)

    assert result.chunks is not None
    assert len(result.chunks) == 0
    assert result.paragraphs == []
    assert result.translation_chunks == []


@pytest.mark.asyncio
async def test_pipeline_records_stage_transition_events():
    segment = SegmentStage()
    pipeline = TranslationPipeline([segment])
    context = PipelineState(
        chapter_url="test",
        job_id="job_1",
        activity_id="activity_1",
        novel_id="novel1",
        chapter_id="chapter_001",
        source_key="kakuyomu",
    )
    context.normalized_text = "Paragraph 1"

    result = await pipeline.run(context)

    assert [event["status_after"] for event in result.pipeline_events] == ["running", "segmented"]
    assert result.pipeline_events[0]["job_id"] == "job_1"
    assert result.pipeline_events[0]["activity_id"] == "activity_1"
    assert result.pipeline_events[0]["source_key"] == "kakuyomu"
    assert result.pipeline_events[1]["stage_name"] == "SegmentStage"
    assert result.pipeline_events[1]["timestamp"]


@pytest.mark.asyncio
async def test_pipeline_records_failed_stage_event():
    pipeline = TranslationPipeline([_FailingStage()])
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")

    with pytest.raises(RuntimeError, match="stage boom"):
        await pipeline.run(context)

    assert context.errors[0]["stage_name"] == "_FailingStage"
    assert context.pipeline_events[-1]["status_after"] == "failed"
    assert context.pipeline_events[-1]["error_code"] == "RuntimeError"


@pytest.mark.asyncio
async def test_smart_segment_stage_is_deterministic():
    """Same normalized input should produce the same paragraph and chunk IDs."""
    text = "Alpha\n\nBeta\n\nGamma"

    first = PipelineState(chapter_url="https://example.com/novel1/1", novel_id="novel1", chapter_id="1")
    first.normalized_text = text
    second = PipelineState(chapter_url="https://example.com/novel1/1", novel_id="novel1", chapter_id="1")
    second.normalized_text = text

    segment = SmartSegmentStage(target_chars=4500, hard_max_chars=7000)
    first_result = await segment.run(first)
    second_result = await segment.run(second)

    assert [paragraph.to_dict() for paragraph in first_result.paragraphs] == [
        paragraph.to_dict() for paragraph in second_result.paragraphs
    ]
    assert [chunk.to_dict() for chunk in first_result.translation_chunks] == [
        chunk.to_dict() for chunk in second_result.translation_chunks
    ]
    assert [paragraph.source_hash for paragraph in first_result.paragraphs] == [
        paragraph.source_hash for paragraph in second_result.paragraphs
    ]


def test_paragraph_source_hash_is_stable_and_line_ending_normalized():
    assert paragraph_source_hash("Alpha\r\nBeta") == paragraph_source_hash("Alpha\nBeta")
    assert paragraph_source_hash("Alpha\nBeta") != paragraph_source_hash("Alpha\nGamma")


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_translate_stage_default_fallback_order_is_gemini_only(tmp_path):
    env = _fallback_stage_env(tmp_path)
    gemini_provider = _FallbackContractProvider("gemini")
    stage = TranslateStage(
        provider_factory=lambda key: gemini_provider,
        cache=env["cache"],
        settings_service=env["prefs"],
        usage_service=env["usage"],
        storage=env["storage"],
    )

    scheduler = stage._build_scheduler(_fallback_context(), provider_key="gemini", model=settings.PROVIDER_GEMINI_DEFAULT_MODEL)
    model_states = scheduler.to_model_state_list()

    assert len(model_states) >= 1
    assert model_states[0]["provider_key"] == "gemini"

@pytest.mark.asyncio
async def test_translate_stage_provider_lock_filters_cross_provider_fallback(tmp_path):
    env = _fallback_stage_env(tmp_path)
    provider = _FallbackContractProvider("gemini")
    stage = TranslateStage(
        provider_factory=lambda key: provider,
        cache=env["cache"],
        settings_service=env["prefs"],
        usage_service=env["usage"],
        storage=env["storage"],
    )
    context = _fallback_context()
    context.metadata["allow_cross_provider_fallback"] = False
    context.metadata["scheduler_models"] = [
        {"provider_key": "gemini", "provider_model": settings.PROVIDER_GEMINI_DEFAULT_MODEL, "priority_order": 0},
    ]

    scheduler = stage._build_scheduler(context, provider_key="gemini", model=settings.PROVIDER_GEMINI_DEFAULT_MODEL)
    model_states = scheduler.to_model_state_list()

    assert [(item["provider_key"], item["provider_model"]) for item in model_states] == [
        ("gemini", "gemini-3.1-flash-lite"),
    ]

@pytest.mark.asyncio
async def test_translate_stage_gemini_quota_falls_back_to_fallback_model(tmp_path):
    env = _fallback_stage_env(tmp_path)
    gemini_provider = _FallbackContractProvider("gemini", error_code=ProviderErrorCode.QUOTA_EXHAUSTED)
    stage = TranslateStage(
        provider_factory=lambda key: gemini_provider,
        cache=env["cache"],
        settings_service=env["prefs"],
        usage_service=env["usage"],
        storage=env["storage"],
    )

    result = await stage.run(_fallback_context())

    assert gemini_provider.models_seen == ["gemini-3.1-flash-lite"]
    assert result.translations == ["Translated paragraph."]

@pytest.mark.asyncio
async def test_translate_stage_provider_locked_gemini_failure_stops_without_cross_provider_fallback(tmp_path):
    env = _fallback_stage_env(tmp_path)
    gemini_provider = _FallbackContractProvider("gemini", error_code=ProviderErrorCode.QUOTA_EXHAUSTED)
    stage = TranslateStage(
        provider_factory=lambda key: gemini_provider,
        cache=env["cache"],
        settings_service=env["prefs"],
        usage_service=env["usage"],
        storage=env["storage"],
    )
    context = _fallback_context()
    context.metadata["allow_cross_provider_fallback"] = False

    with pytest.raises(SchedulerPausedError) as exc_info:
        await stage.run(context)

    assert gemini_provider.models_seen == ["gemini-3.1-flash-lite"]
    assert {item["provider_key"] for item in exc_info.value.model_states} == {"gemini"}

@pytest.mark.asyncio
async def test_translate_stage_uses_saved_admin_fallback_policy_order(tmp_path):
    env = _fallback_stage_env(tmp_path)
    prefs = env["prefs"]
    prefs.set_provider_management(
        {
            "credentials": {
                "gemini": {"is_active": True},
            },
            "fallback_policy": {
                "allow_cross_provider_fallback": False,
                "candidates": [
                    {
                        "priority_order": 0,
                        "provider": "gemini",
                        "model": "gemini-3.1-flash-lite",
                        "credential_id": "gemini",
                        "enabled": True,
                    },
                ],
            },
        }
    )
    stage = TranslateStage(
        provider_factory=lambda key: _FallbackContractProvider(key),
        cache=env["cache"],
        settings_service=prefs,
        usage_service=env["usage"],
        storage=env["storage"],
    )

    scheduler = stage._build_scheduler(_fallback_context(), provider_key="gemini", model=settings.PROVIDER_GEMINI_DEFAULT_MODEL)
    model_states = scheduler.to_model_state_list()

    assert [(item["provider_key"], item["provider_model"]) for item in model_states] == [
        ("gemini", "gemini-3.1-flash-lite"),
    ]

@pytest.mark.asyncio
async def test_translate_stage_saved_policy_skips_disabled_credentials(tmp_path):
    env = _fallback_stage_env(tmp_path)
    prefs = env["prefs"]
    prefs.set_provider_management(
        {
            "credentials": {
                "gemini": {"is_active": False},
            },
            "fallback_policy": {
                "allow_cross_provider_fallback": False,
                "candidates": [
                    {
                        "priority_order": 0,
                        "provider": "gemini",
                        "model": "gemini-3.1-flash-lite",
                        "credential_id": "gemini",
                        "enabled": True,
                    },
                ],
            },
        }
    )
    stage = TranslateStage(
        provider_factory=lambda key: _FallbackContractProvider(key),
        cache=env["cache"],
        settings_service=prefs,
        usage_service=env["usage"],
        storage=env["storage"],
    )

    scheduler = stage._build_scheduler(_fallback_context(), provider_key="gemini", model=settings.PROVIDER_GEMINI_DEFAULT_MODEL)

    assert scheduler.to_model_state_list() == []

@pytest.mark.asyncio
async def test_translate_stage_saved_policy_skips_invalid_credentials(tmp_path):
    env = _fallback_stage_env(tmp_path)
    prefs = env["prefs"]
    prefs.set_provider_management(
        {
            "credentials": {
                "gemini": {"is_active": True, "validation_status": "failed"},
            },
            "fallback_policy": {
                "allow_cross_provider_fallback": False,
                "candidates": [
                    {
                        "priority_order": 0,
                        "provider": "gemini",
                        "model": "gemini-3.1-flash-lite",
                        "credential_id": "gemini",
                        "enabled": True,
                    },
                ],
            },
        }
    )
    stage = TranslateStage(
        provider_factory=lambda key: _FallbackContractProvider(key),
        cache=env["cache"],
        settings_service=prefs,
        usage_service=env["usage"],
        storage=env["storage"],
    )

    scheduler = stage._build_scheduler(_fallback_context(), provider_key="gemini", model=settings.PROVIDER_GEMINI_DEFAULT_MODEL)

    assert scheduler.to_model_state_list() == []

@pytest.mark.asyncio
async def test_translate_stage_gemini_unknown_error_does_not_fallback(tmp_path):
    env = _fallback_stage_env(tmp_path)
    gemini_provider = _FallbackContractProvider("gemini", error_code=ProviderErrorCode.UNKNOWN)
    stage = TranslateStage(
        provider_factory=lambda key: gemini_provider,
        cache=env["cache"],
        settings_service=env["prefs"],
        usage_service=env["usage"],
        storage=env["storage"],
    )

    with pytest.raises(ProviderError):
        await stage.run(_fallback_context())

    assert gemini_provider.models_seen == ["gemini-3.1-flash-lite"]


@pytest.mark.asyncio
async def test_smart_segment_stage_packs_normal_chapter_by_budget():
    """Paragraphs should be packed into budget-aware chunks instead of one call per paragraph."""
    segment = SmartSegmentStage(
        target_chars=25,
        hard_max_chars=40,
        overlap_paragraphs=1,
        conditional_overlap_enabled=False,
    )
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "aaaaaaaaaa\n\nbbbbbbbbbb\n\ncccccccccc\n\ndddddddddd"

    result = await segment.run(context)

    assert len(result.paragraphs) == 4
    assert len(result.translation_chunks) == 2
    assert [chunk.chunk_id for chunk in result.translation_chunks] == ["c0001", "c0002"]
    assert result.translation_chunks[0].paragraph_ids == ["p0001", "p0002"]
    assert result.translation_chunks[1].paragraph_ids == ["p0003", "p0004"]
    assert result.translation_chunks[1].paragraph_hashes == [
        result.paragraphs[2].source_hash,
        result.paragraphs[3].source_hash,
    ]
    assert result.translation_chunks[1].previous_context == "bbbbbbbbbb"


@pytest.mark.asyncio
async def test_smart_segment_stage_keeps_short_chapter_as_single_chunk():
    segment = SmartSegmentStage(target_chars=100, hard_max_chars=150)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "Short chapter."

    result = await segment.run(context)

    assert len(result.translation_chunks) == 1
    chunk = result.translation_chunks[0]
    assert chunk.chapter_ids == ["chapter_001"]
    assert chunk.paragraph_ids == ["p0001"]
    assert chunk.char_count == len("Short chapter.")


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_keeps_chapter_below_hard_max_as_single_chunk():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "a" * 6000

    result = await segment.run(context)

    assert len(result.translation_chunks) == 1
    assert result.translation_chunks[0].char_count == 6000
    assert result.metadata["segmentation"]["adaptive_chunking_enabled"] is True


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_reduces_mid_length_extra_chunks():
    text = "\n\n".join(["a" * 3000, "b" * 3000, "c" * 3000])
    adaptive = SmartSegmentStage(adaptive_chunking_enabled=True)
    baseline = SmartSegmentStage(adaptive_chunking_enabled=False)

    adaptive_context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    baseline_context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    adaptive_context.normalized_text = text
    baseline_context.normalized_text = text

    adaptive_result = await adaptive.run(adaptive_context)
    baseline_result = await baseline.run(baseline_context)

    assert len(baseline_result.translation_chunks) == 3
    assert len(adaptive_result.translation_chunks) == 2
    assert [chunk.char_count for chunk in adaptive_result.translation_chunks] == [6000, 3000]


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_balances_twelve_thousand_chars_into_two_chunks():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "\n\n".join(["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000])

    result = await segment.run(context)

    assert len(result.translation_chunks) == 2
    assert [chunk.char_count for chunk in result.translation_chunks] == [6000, 6000]
    assert all(chunk.char_count <= 7000 for chunk in result.translation_chunks)


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_preserves_refs_and_previous_context():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True, boundary_context_chars=160)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    paragraphs = ["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000]
    context.normalized_text = "\n\n".join(paragraphs)

    result = await segment.run(context)

    assert [chunk.paragraph_ids for chunk in result.translation_chunks] == [
        ["p0001", "p0002"],
        ["p0003", "p0004"],
    ]
    assert result.translation_chunks[1].paragraph_refs == [
        ("chapter_001", "p0003"),
        ("chapter_001", "p0004"),
    ]
    assert result.translation_chunks[1].previous_context == paragraphs[1][-160:]


@pytest.mark.asyncio
async def test_smart_segment_stage_conditional_overlap_uses_zero_overlap_for_safe_boundary():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "\n\n".join(
        [
            ("a" * 2999) + ".",
            ("b" * 2999) + ".",
            ("c" * 2999) + ".",
            ("d" * 2999) + ".",
        ]
    )

    result = await segment.run(context)

    assert len(result.translation_chunks) == 2
    assert "[CONTEXT OVERLAP]" not in result.translation_chunks[1].source_text
    assert result.translation_chunks[1].paragraph_ids == ["p0003", "p0004"]


@pytest.mark.asyncio
async def test_smart_segment_stage_conditional_overlap_uses_overlap_for_unsafe_quote_boundary():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    unsafe_previous = "「" + ("b" * 2999)
    context.normalized_text = "\n\n".join(
        [
            ("a" * 2999) + ".",
            unsafe_previous,
            ("c" * 2999) + ".",
            ("d" * 2999) + ".",
        ]
    )

    result = await segment.run(context)

    second_chunk = result.translation_chunks[1]
    assert second_chunk.paragraph_ids == ["p0003", "p0004"]
    assert second_chunk.paragraph_refs == [("chapter_001", "p0003"), ("chapter_001", "p0004")]
    assert second_chunk.paragraph_hashes == [result.paragraphs[2].source_hash, result.paragraphs[3].source_hash]
    assert all(item["paragraph_id"] != "p0002" for item in second_chunk.paragraph_lineage)
    assert second_chunk.source_text.startswith("[CONTEXT OVERLAP]\n" + unsafe_previous)


@pytest.mark.asyncio
async def test_smart_segment_stage_conditional_overlap_uses_zero_overlap_after_scene_separator():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "\n\n".join(
        [
            "a" * 3000,
            "***",
            ("b" * 2999) + ".",
            ("c" * 2999) + ".",
        ]
    )

    result = await segment.run(context)

    assert len(result.translation_chunks) == 2
    assert result.translation_chunks[0].paragraph_ids == ["p0001", "p0002"]
    assert result.translation_chunks[1].paragraph_ids == ["p0003", "p0004"]
    assert "[CONTEXT OVERLAP]" not in result.translation_chunks[1].source_text


@pytest.mark.asyncio
async def test_smart_segment_stage_previous_context_is_capped_without_source_duplication():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True, boundary_context_chars=25)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    previous_tail = "b" * 30 + "."
    context.normalized_text = "\n\n".join(
        [
            "a" * 3000,
            previous_tail,
            ("c" * 2999) + ".",
            ("d" * 2999) + ".",
        ]
    )

    result = await segment.run(context)

    second_chunk = result.translation_chunks[1]
    assert second_chunk.previous_context == previous_tail[-25:]
    assert previous_tail not in second_chunk.source_text
    assert "[CONTEXT OVERLAP]" not in second_chunk.source_text


@pytest.mark.asyncio
async def test_smart_segment_stage_conditional_overlap_disabled_preserves_legacy_context():
    segment = SmartSegmentStage(
        adaptive_chunking_enabled=True,
        conditional_overlap_enabled=False,
        overlap_paragraphs=1,
    )
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    paragraphs = ["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000]
    context.normalized_text = "\n\n".join(paragraphs)

    result = await segment.run(context)

    assert result.translation_chunks[1].previous_context == paragraphs[1]
    assert "[CONTEXT OVERLAP]" not in result.translation_chunks[1].source_text


@pytest.mark.asyncio
async def test_smart_segment_stage_bundles_multiple_short_neighboring_chapters():
    segment = SmartSegmentStage(target_chars=100, hard_max_chars=150, max_chapters_per_bundle=3)
    context = PipelineState(chapter_url="bundle", novel_id="novel1")
    context.metadata["_normalized_chapters"] = [
        {"novel_id": "novel1", "chapter_id": "chapter_001", "text": "One."},
        {"novel_id": "novel1", "chapter_id": "chapter_002", "text": "Two."},
        {"novel_id": "novel1", "chapter_id": "chapter_003", "text": "Three."},
    ]

    result = await segment.run(context)

    assert len(result.translation_chunks) == 1
    chunk = result.translation_chunks[0]
    assert chunk.chapter_ids == ["chapter_001", "chapter_002", "chapter_003"]
    assert chunk.paragraph_ids == ["p0001", "p0001", "p0001"]
    assert chunk.paragraph_refs == [
        ("chapter_001", "p0001"),
        ("chapter_002", "p0001"),
        ("chapter_003", "p0001"),
    ]
    assert "[CHAPTER chapter_001]" in chunk.source_text
    assert "[CHAPTER chapter_002]" in chunk.source_text
    assert "[CHAPTER chapter_003]" in chunk.source_text


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_bundles_multiple_short_neighboring_chapters():
    segment = SmartSegmentStage(adaptive_chunking_enabled=True, max_chapters_per_bundle=3)
    context = PipelineState(chapter_url="bundle", novel_id="novel1")
    context.metadata["_normalized_chapters"] = [
        {"novel_id": "novel1", "chapter_id": "chapter_001", "text": "One."},
        {"novel_id": "novel1", "chapter_id": "chapter_002", "text": "Two."},
        {"novel_id": "novel1", "chapter_id": "chapter_003", "text": "Three."},
    ]

    result = await segment.run(context)

    assert len(result.translation_chunks) == 1
    assert result.translation_chunks[0].chapter_ids == ["chapter_001", "chapter_002", "chapter_003"]


@pytest.mark.asyncio
async def test_smart_segment_stage_splits_long_chapter_without_paragraph_loss():
    segment = SmartSegmentStage(target_chars=30, hard_max_chars=45)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "\n\n".join([f"paragraph-{index:02d}" for index in range(1, 8)])

    result = await segment.run(context)

    assert len(result.translation_chunks) > 1
    refs = [ref for chunk in result.translation_chunks for ref in chunk.paragraph_refs]
    expected = [("chapter_001", f"p{index:04d}") for index in range(1, 8)]
    assert refs == expected
    hashes = [source_hash for chunk in result.translation_chunks for source_hash in chunk.paragraph_hashes]
    assert hashes == [paragraph.source_hash for paragraph in result.paragraphs]
    assert all(chunk.char_count <= 45 for chunk in result.translation_chunks)


@pytest.mark.asyncio
async def test_smart_segment_stage_adaptive_disabled_preserves_baseline_chunk_count():
    segment = SmartSegmentStage(adaptive_chunking_enabled=False)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "\n\n".join(["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000])

    result = await segment.run(context)

    assert len(result.translation_chunks) == 4
    assert result.metadata["segmentation"]["adaptive_chunking_enabled"] is False


@pytest.mark.asyncio
async def test_smart_segment_stage_isolates_oversized_paragraph_with_warning():
    segment = SmartSegmentStage(target_chars=10, hard_max_chars=12)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "short\n\nthis paragraph is too long\n\nend"

    result = await segment.run(context)

    oversized_chunks = [
        chunk
        for chunk in result.translation_chunks
        if chunk.paragraph_ids == ["p0002"]
    ]
    assert len(oversized_chunks) == 1
    warnings = result.metadata["segmentation"]["warnings"]
    assert any("Oversized paragraph chapter_001/p0002" in warning for warning in warnings)


@pytest.mark.asyncio
async def test_smart_segment_stage_preserves_image_placeholders_and_scene_breaks_in_order():
    segment = SmartSegmentStage(target_chars=100, hard_max_chars=150)
    context = PipelineState(chapter_url="test", novel_id="novel1", chapter_id="chapter_001")
    context.normalized_text = "[Image: cover]\n\n***\n\nThe story continues."

    result = await segment.run(context)

    assert [paragraph.text for paragraph in result.paragraphs] == [
        "[Image: cover]",
        "***",
        "The story continues.",
    ]
    source_text = result.translation_chunks[0].source_text
    assert source_text.index("[Image: cover]") < source_text.index("***") < source_text.index("The story continues.")


@pytest.mark.asyncio
async def test_translation_chunk_serialization_preserves_split_metadata():
    segment = SmartSegmentStage(target_chars=100, hard_max_chars=150)
    context = PipelineState(chapter_url="bundle", novel_id="novel1")
    context.metadata["_normalized_chapters"] = [
        {"novel_id": "novel1", "chapter_id": "chapter_001", "text": "One.\n\nTwo."},
        {"novel_id": "novel1", "chapter_id": "chapter_002", "text": "Three."},
    ]

    result = await segment.run(context)
    payload = result.translation_chunks[0].to_dict()
    restored = TranslationChunk.from_dict(payload)

    assert restored.chunk_id == "c0001"
    assert restored.chapter_ids == ["chapter_001", "chapter_002"]
    assert restored.paragraph_hashes == result.translation_chunks[0].paragraph_hashes
    assert restored.paragraph_lineage == result.translation_chunks[0].paragraph_lineage
    assert restored.paragraph_refs == [
        ("chapter_001", "p0001"),
        ("chapter_001", "p0002"),
        ("chapter_002", "p0001"),
    ]


def test_translation_chunk_serialization_accepts_missing_paragraph_hashes():
    restored = TranslationChunk.from_dict(
        {
            "chunk_id": "c0001",
            "novel_id": "novel1",
            "chapter_ids": ["chapter_001"],
            "paragraph_ids": ["p0001"],
            "source_text": "Legacy text",
            "char_count": 11,
            "paragraph_refs": [{"chapter_id": "chapter_001", "paragraph_id": "p0001"}],
        }
    )

    assert restored.paragraph_hashes == []
    assert restored.paragraph_lineage == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

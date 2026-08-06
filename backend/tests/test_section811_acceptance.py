"""PR-41 Section 8 + 11 acceptance contract tests.

Section 8: cache acceptance is locked to the exact QA-accepted attempt; provider
or model switching produces different cache keys. Section 11: redirect
sanitization across multi-hop chains never reintroduces credentials, and the
HTTP origin includes effective port.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
from pathlib import Path

from novelai.infrastructure.http.fetch_service import (
    _origin,
    _strip_origin_sensitive_headers,
)
from novelai.services.translation_cache import (
    CacheEntry,
    TranslationCacheService,
    make_cache_key,
)
from novelai.translation.pipeline.context import PipelineState
from novelai.translation.pipeline.stages.cache_flush import CacheFlushStage
from novelai.translation.pipeline.stages.translate_cache_lookup import (
    RETRY_MARKED_STATUSES,
)


def test_http_origin_distinguishes_effective_port() -> None:
    """Section 11: ``http://example.com:8080`` is cross-origin to the default port."""
    base = _origin("http://example.com")
    alt = _origin("http://example.com:8080")
    https_default = _origin("https://example.com")
    https_alt = _origin("https://example.com:8443")
    assert base != alt
    assert https_default != https_alt
    # Same scheme + hostname + same effective port collapses.
    assert _origin("http://example.com") == _origin("http://example.com:80")
    assert _origin("https://example.com") == _origin("https://example.com:443")


def test_origin_sensitive_headers_strip_authorization_and_cookie() -> None:
    headers = {
        "Authorization": "Bearer x",
        "Proxy-Authorization": "Bearer y",
        "Cookie": "session=abc",
        "Host": "example.com",
        "If-None-Match": "etag",
        "If-Modified-Since": "x",
        "User-Agent": "ua",
        "Accept": "*/*",
    }
    cleaned = _strip_origin_sensitive_headers(headers)
    assert "authorization" not in {key.lower() for key in cleaned}
    assert "cookie" not in {key.lower() for key in cleaned}
    assert "host" not in {key.lower() for key in cleaned}
    assert "if-none-match" not in {key.lower() for key in cleaned}
    assert cleaned["User-Agent"] == "ua"
    assert cleaned["Accept"] == "*/*"


def test_cache_key_distinguishes_provider_and_model() -> None:
    """Section 8: provider/model/prompt/glossary produce different cache keys."""
    key_default = make_cache_key(
        "hello",
        "ja",
        "en",
        "ghash",
        provider_key="openai",
        provider_model="gpt-4",
        prompt_version="v2",
    )
    key_different_provider = make_cache_key(
        "hello",
        "ja",
        "en",
        "ghash",
        provider_key="anthropic",
        provider_model="gpt-4",
        prompt_version="v2",
    )
    key_different_model = make_cache_key(
        "hello",
        "ja",
        "en",
        "ghash",
        provider_key="openai",
        provider_model="gpt-4o",
        prompt_version="v2",
    )
    key_different_prompt = make_cache_key(
        "hello",
        "ja",
        "en",
        "ghash",
        provider_key="openai",
        provider_model="gpt-4",
        prompt_version="v3",
    )
    key_different_glossary = make_cache_key(
        "hello",
        "ja",
        "en",
        "ghash2",
        provider_key="openai",
        provider_model="gpt-4",
        prompt_version="v2",
    )
    assert (
        len({key_default, key_different_provider, key_different_model, key_different_prompt, key_different_glossary})
        == 5
    )


def test_retry_marked_statuses_cover_all_rejection_outcomes() -> None:
    """Section 8: needs_retry/needs_review/qa_failed are the rejection set."""
    assert "needs_retry" in RETRY_MARKED_STATUSES
    assert "needs_review" in RETRY_MARKED_STATUSES
    assert "qa_failed" in RETRY_MARKED_STATUSES


def test_cache_flush_dedupes_pending_keys_and_skips_rejected_chunks() -> None:
    """Section 8: dedup per-key keeps only the final attempt; rejected chunks drop."""
    now = _dt.datetime.now(_dt.UTC).isoformat()
    ctx = PipelineState(
        chapter_url="u",
        novel_id="n1",
        chapter_id="c1",
        provider_key="mock",
        provider_model="mock-model",
    )
    ctx.metadata["_pending_cache_entries"] = []
    ctx.chunk_states["c1"] = {"status": "needs_retry"}
    ctx.metadata["progress"] = {}
    rejected_entry = CacheEntry(
        key="k",
        source_text="hello",
        translated_text="rejected attempt",
        source_language="ja",
        target_language="en",
        glossary_hash="",
        provider_key="mock",
        provider_model="mock-model",
        created_at=now,
        novel_id="n1",
        chunk_id="c1",
        attempt_number=1,
        translation_run_id="r",
        output_hash="abc",
    )
    ctx.metadata["_pending_cache_entries"].append(("k", rejected_entry))

    asyncio.run(CacheFlushStage().run(ctx))
    progress = ctx.metadata["progress"]
    assert progress["cache_flush_dropped"] == 1
    assert progress["cache_flush_written"] == 0


def test_cache_flush_writes_only_accepted_attempt(tmp_path) -> None:
    """Section 8: identical cache key only keeps the last accepted attempt."""
    svc = TranslationCacheService(cache_dir=Path(tmp_path / "cache"))
    import pathlib

    svc.cache_dir = pathlib.Path(svc.cache_dir).resolve()
    key = make_cache_key(
        "src",
        "ja",
        "en",
        "gh",
        provider_key="mock",
        provider_model="m",
        prompt_version="v2",
    )
    ctx = PipelineState(
        chapter_url="u",
        novel_id="n1",
        chapter_id="c1",
        provider_key="mock",
        provider_model="m",
    )
    ctx.chunk_states["c1"] = {"status": "translated"}
    ctx.metadata["progress"] = {}

    def _entry(translated_text: str, attempt: int) -> CacheEntry:
        return CacheEntry(
            key=key,
            source_text="src",
            translated_text=translated_text,
            source_language="ja",
            target_language="en",
            glossary_hash="gh",
            provider_key="mock",
            provider_model="m",
            created_at=_dt.datetime.now(_dt.UTC).isoformat(),
            novel_id="n1",
            chunk_id="c1",
            attempt_number=attempt,
            translation_run_id="r",
            output_hash=f"hash-{attempt}",
        )

    ctx.metadata["_pending_cache_entries"] = [
        (key, _entry("attempt-one", 1)),
        (key, _entry("attempt-two", 2)),
    ]
    asyncio.run(CacheFlushStage(cache_service=svc).run(ctx))
    assert ctx.metadata["progress"]["cache_flush_written"] == 1
    cached = svc.get(key)
    assert cached is not None
    assert cached.translated_text == "attempt-two"
    assert cached.attempt_number == 2

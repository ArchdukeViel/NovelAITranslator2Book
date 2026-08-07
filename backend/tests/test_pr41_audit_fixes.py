"""PR-41 audit-fix regression tests.

Covers the unambiguous gaps found in the PR-41 audit:

- S3: crawler defers live ``metadata.json`` / ``source_state.json``
  projections until after the active pointer swap, so a partial or
  cancelled run never exposes half-committed state.
- S4: generation pre-activation validation is not tautological (real
  source-state presence check, manifest hash integrity, manifest
  membership reconciled against physical bundles).
- S5: force-mode checkpoint reset keys by stable chapter id, not by
  positional sequence number.
- S6: ``is_translation_valid`` reads the overlay key spellings
  (``source_hash`` / ``prompt_template_version``).
- S7: cache flush stamps acceptance provenance (``accepted_at`` /
  ``qa_status``) on flushed entries.
- S9: throttle keys include the effective port; credentials stripped on
  a cross-origin hop are never restored on a later same-origin hop.
- S10/S11: ``resolve_asset_path`` has no legacy fallback under an active
  generation; OCR/media state lives in a novel-root overlay; raw writes
  into committed generations are refused (chapters, checkpoints,
  imports, rollback bundle-pop).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from novelai.infrastructure.http.cache import InMemoryFetchCache
from novelai.infrastructure.http.client import create_async_client
from novelai.infrastructure.http.fetch_service import FetchService
from novelai.infrastructure.http.throttle import DomainThrottle
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import CacheEntry
from novelai.services.usage_service import UsageService
from novelai.sources import SourceAdapter
from novelai.storage.service import StorageService
from novelai.translation.pipeline.context import PipelineState
from novelai.translation.pipeline.stages.cache_flush import CacheFlushStage
from novelai.translation.run_manifest import is_translation_valid

_TMP = Path(__file__).resolve().parent / ".tmp" / "audit_fixes"


def _fresh_storage() -> StorageService:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return StorageService(d)


def _commit_minimal_generation(
    storage: StorageService,
    novel_id: str,
    generation_id: str,
    chapter_ids: list[str] | None = None,
) -> None:
    """Stage + commit a minimal raw generation with the given chapter ids."""
    chapter_ids = chapter_ids or ["1"]
    storage.create_generation_stage(
        novel_id,
        generation_id,
        source_key="test_source",
        source_work_id=novel_id,
        mode="full",
        expected_chapters=len(chapter_ids),
    )
    storage.stage_generation_metadata(
        novel_id,
        generation_id,
        {"title": "Audit Fixes", "source_novel_id": novel_id},
    )
    storage.stage_generation_source_state(novel_id, generation_id, {"chapters": []})
    storage.stage_generation_chapter_index(
        novel_id,
        generation_id,
        [
            {"id": cid, "chapter_id": cid, "title": f"Chapter {cid}", "url": f"http://example.test/{cid}"}
            for cid in chapter_ids
        ],
    )
    for cid in chapter_ids:
        storage.stage_generation_chapter(
            novel_id,
            generation_id,
            cid,
            {"id": cid, "raw": {"text": f"Raw {cid}", "paragraphs": [f"Raw {cid}"]}},
        )
    storage.commit_generation(novel_id, generation_id)


def _generation_dir(storage: StorageService, novel_id: str, generation_id: str) -> Path:
    return storage.base_dir / "novels" / novel_id / "generations" / generation_id


def _bundle_hash(storage: StorageService, novel_id: str, generation_id: str, chapter_id: str) -> str:
    chapter_dir = _generation_dir(storage, novel_id, generation_id) / "chapters"
    for path in chapter_dir.glob("*.json"):
        if storage.logical_id_from_stem(path.stem) == chapter_id:
            return hashlib.sha256(path.read_bytes()).hexdigest()
    raise AssertionError(f"no bundle for chapter {chapter_id!r} in {chapter_dir}")


# ---------------------------------------------------------------------------
# S3 harness (mirrors test_crawl_fetch_observability.py)
# ---------------------------------------------------------------------------


class FakeSource(SourceAdapter):
    def __init__(
        self, *, source_key: str = "test_source", chapter_payloads: dict[str, dict[str, Any]] | None = None
    ) -> None:
        self.source_key = source_key
        self._chapter_payloads = chapter_payloads or {}

    def can_handle(self, identifier_or_url: str) -> bool:
        return False

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        return {
            "novel_id": url,
            "title": f"Test Novel {url}",
            "author": "Test Author",
            "source_key": self.source_key,
            "source_url": f"https://example.test/{url}",
            "chapters": [
                {"id": str(i), "num": i, "title": f"Chapter {i}", "url": f"http://example.test/{url}/{i}"}
                for i in range(1, 4)
            ],
        }

    async def fetch_chapter(self, url: str) -> str:
        return self._chapter_payloads.get(url, {}).get("text", f"Content for {url}")

    async def fetch_chapter_payload(self, url: str, *, on_retry: Any = None) -> Mapping[str, Any]:
        payload = self._chapter_payloads.get(url, {})
        return {"text": payload.get("text", f"Content for {url}"), "images": payload.get("images", [])}

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> Mapping[str, Any]:
        return {"url": url, "content": b"", "content_type": "image/png"}


class _NoopTranslationService:
    async def translate_chapters(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"status": "noop"}


def _make_orchestrator(storage: StorageService, source: SourceAdapter) -> Any:
    from novelai.services.novel_orchestration_service import NovelOrchestrationService
    from novelai.services.translation_cache import TranslationCache

    return NovelOrchestrationService(
        storage=storage,
        translation=_NoopTranslationService(),  # type: ignore[arg-type]
        source_factory=lambda _key: source,
        settings_service=PreferencesService(),
        translation_cache=TranslationCache(storage.base_dir),
        usage_service=UsageService(storage.base_dir),
    )


@pytest.fixture(autouse=True)
def _stub_catalog_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    from novelai.services import catalog_service
    from novelai.services.orchestration import crawler as crawler_module

    def _noop(novel_id: str, storage: Any, *, context: str, **kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(catalog_service, "safely_refresh_catalog_projection_after_storage_write", _noop)
    monkeypatch.setattr(crawler_module, "safely_refresh_catalog_projection_after_storage_write", _noop)


def _seed_metadata(storage: StorageService, novel_id: str) -> dict[str, Any]:
    meta = {
        "novel_id": novel_id,
        "title": f"Seeded Original {novel_id}",
        "author": "Seed Author",
        "source_key": "test_source",
        "chapters": [
            {"id": str(i), "num": i, "title": f"Chapter {i}", "url": f"http://example.test/{novel_id}/{i}"}
            for i in range(1, 4)
        ],
    }
    storage.save_metadata(novel_id, meta)
    return meta


# ---------------------------------------------------------------------------
# S3 — crawler defers live projections until after commit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancelled_full_crawl_never_writes_live_projections() -> None:
    storage = _fresh_storage()
    _seed_metadata(storage, "novel-s3-fail")
    orchestrator = _make_orchestrator(storage, FakeSource())

    with pytest.raises(asyncio.CancelledError):
        await orchestrator.scrape_chapters(
            "test_source",
            "novel-s3-fail",
            "all",
            mode="full",
            cancellation_check=lambda: True,
        )

    # The seeded live metadata must be untouched (pre-fix the full-mode
    # crawl overwrote it before any chapter was fetched).
    meta = storage.load_metadata("novel-s3-fail")
    assert meta is not None
    assert meta["title"] == "Seeded Original novel-s3-fail"
    # No live source state, no active pointer, no leftover stage.
    assert storage.load_source_state("novel-s3-fail") is None
    assert storage.get_active_generation("novel-s3-fail") is None
    generations_dir = storage.base_dir / "novels" / "novel-s3-fail" / "generations"
    assert not generations_dir.exists() or not list(generations_dir.iterdir())


@pytest.mark.asyncio
async def test_full_crawl_writes_live_projections_only_after_commit() -> None:
    storage = _fresh_storage()
    _seed_metadata(storage, "novel-s3-ok")
    orchestrator = _make_orchestrator(storage, FakeSource())

    result = await orchestrator.scrape_chapters("test_source", "novel-s3-ok", "all", mode="full")

    assert result["succeeded"] == 3
    active = storage.get_active_generation("novel-s3-ok")
    assert active is not None
    # Live projections exist now (post-commit best-effort refresh).
    meta = storage.load_metadata("novel-s3-ok")
    assert meta is not None
    assert meta["title"] == "Test Novel novel-s3-ok"
    assert storage.load_source_state("novel-s3-ok") is not None


# ---------------------------------------------------------------------------
# S4 — generation validation is not tautological
# ---------------------------------------------------------------------------


def test_commit_requires_staged_source_state() -> None:
    storage = _fresh_storage()
    storage.create_generation_stage(
        "n4", "gen-1", source_key="test_source", source_work_id="n4", mode="full", expected_chapters=1
    )
    storage.stage_generation_metadata("n4", "gen-1", {"title": "T", "source_novel_id": "n4"})
    storage.stage_generation_chapter_index("n4", "gen-1", [{"id": "1", "chapter_id": "1", "title": "C", "url": "u"}])
    storage.stage_generation_chapter("n4", "gen-1", "1", {"id": "1", "raw": {"text": "Hello"}})

    with pytest.raises(RuntimeError, match="source_state_present"):
        storage.commit_generation("n4", "gen-1")


def test_commit_rejects_tampered_staged_metadata() -> None:
    storage = _fresh_storage()
    _commit_minimal_generation(storage, "n4-tamper", "gen-1")

    metadata_path = _generation_dir(storage, "n4-tamper", "gen-1") / "metadata.json"
    metadata_path.write_text(json.dumps({"title": "Tampered", "source_novel_id": "n4-tamper"}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="manifest_metadata_hash_matches_stage"):
        storage.commit_generation("n4-tamper", "gen-1")


def test_manifest_membership_without_physical_bundle_fails_validation() -> None:
    storage = _fresh_storage()
    _commit_minimal_generation(storage, "n4-member", "gen-1", chapter_ids=["1"])

    manifest_path = _generation_dir(storage, "n4-member", "gen-1") / "generation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["chapter_ids"] = ["1", "ghost"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = storage.validate_generation_activation("n4-member", "gen-1")
    assert not result.is_valid
    assert any(check.name == "manifest_chapter_ids_match_available" and not check.passed for check in result.checks)


def test_integer_index_ids_reconcile_with_string_logical_ids() -> None:
    """Adapters emit int ``id`` in the index snapshot; bundles use str ids.

    Regression for the e2e crawl failure: the index preserves the raw
    adapter spelling (``json.dumps`` keeps ints) while bundles and the
    manifest use stringified logical ids, so validation must normalize
    before the subset/reconciliation checks.
    """
    storage = _fresh_storage()
    storage.create_generation_stage(
        "n4-int", "gen-1", source_key="test_source", source_work_id="n4-int", mode="full", expected_chapters=2
    )
    storage.stage_generation_metadata("n4-int", "gen-1", {"title": "Int", "source_novel_id": "n4-int"})
    storage.stage_generation_source_state("n4-int", "gen-1", {"chapters": []})
    # Raw adapter spelling: integer ids survive JSON round-trip.
    storage.stage_generation_chapter_index(
        "n4-int",
        "gen-1",
        [
            {"id": 1, "num": 1, "title": "C1", "url": "http://example.test/1"},
            {"id": 2, "num": 2, "title": "C2", "url": "http://example.test/2"},
        ],
    )
    for cid in ("1", "2"):
        storage.stage_generation_chapter(
            "n4-int",
            "gen-1",
            cid,
            {"id": cid, "raw": {"text": f"Raw {cid}", "paragraphs": [f"Raw {cid}"]}},
        )

    result = storage.validate_generation_activation("n4-int", "gen-1")
    assert result.is_valid, [c.name for c in result.checks if not c.passed]


def test_integer_index_id_without_bundle_still_fails_validation() -> None:
    """Normalization must not weaken the membership check: an int index id
    with no physical bundle (and not recorded unavailable) still fails."""
    storage = _fresh_storage()
    storage.create_generation_stage(
        "n4-int-ghost",
        "gen-1",
        source_key="test_source",
        source_work_id="n4-int-ghost",
        mode="full",
        expected_chapters=2,
    )
    storage.stage_generation_metadata("n4-int-ghost", "gen-1", {"title": "Ghost", "source_novel_id": "n4-int-ghost"})
    storage.stage_generation_source_state("n4-int-ghost", "gen-1", {"chapters": []})
    storage.stage_generation_chapter_index(
        "n4-int-ghost",
        "gen-1",
        [
            {"id": 1, "num": 1, "title": "C1", "url": "http://example.test/1"},
            {"id": 99, "num": 2, "title": "Ghost", "url": "http://example.test/99"},
        ],
    )
    storage.stage_generation_chapter(
        "n4-int-ghost",
        "gen-1",
        "1",
        {"id": "1", "raw": {"text": "Raw 1", "paragraphs": ["Raw 1"]}},
    )

    result = storage.validate_generation_activation("n4-int-ghost", "gen-1")
    assert not result.is_valid
    assert any(check.name == "every_index_entry_resolved" and not check.passed for check in result.checks)


# ---------------------------------------------------------------------------
# S5 — force-mode checkpoint reset keys by stable chapter id
# ---------------------------------------------------------------------------


def test_force_reset_deletes_checkpoints_keyed_by_stable_chapter_id() -> None:
    from novelai.services.orchestration.translation_resume import _init_checkpoint_manager

    storage = _fresh_storage()
    stable_id = "kakuyomu:episode-12345"
    _commit_minimal_generation(storage, "n5", "gen-1", chapter_ids=["1", "2"])

    # Create a checkpoint the way the translation flow does: keyed by the
    # stable chapter id, not the positional sequence number.
    storage.create_checkpoint("n5", stable_id, "before_translate")

    class _Shim:
        def __init__(self, inner: StorageService) -> None:
            self.storage = inner

    cp_mgr = _init_checkpoint_manager(
        _Shim(storage),
        novel_id="n5",
        selected_chapter_ids=[stable_id],
        force=True,
    )
    # The checkpoint file for the stable id must be gone.
    assert cp_mgr.load(stable_id) is None
    assert cp_mgr.load("1") is None  # positional number never existed


# ---------------------------------------------------------------------------
# S6 — is_translation_valid reads overlay key spellings
# ---------------------------------------------------------------------------


def test_is_translation_valid_reads_overlay_keys() -> None:
    record = {
        "source_hash": "abc123",
        "prompt_template_version": "prompt-v9",
        "glossary_hash": "gloss-1",
        "provider_key": "p",
        "provider_model": "m",
    }
    assert is_translation_valid(
        source_text_hash="abc123",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        record=record,
    )

    # Legacy key spellings still work.
    legacy = {
        "source_text_hash": "abc123",
        "prompt_version": "prompt-v9",
        "provider_key": "p",
        "provider_model": "m",
    }
    assert is_translation_valid(
        source_text_hash="abc123",
        active_glossary_hash=None,
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        record=legacy,
    )

    # Mismatched source hash invalidates.
    assert not is_translation_valid(
        source_text_hash="different",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        record=record,
    )


# ---------------------------------------------------------------------------
# S8 — complete raw-to-version translation lineage
# ---------------------------------------------------------------------------


def _lineage_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "source_hash": "src-hash",
        "source_content_hash": "src-hash",
        "source_structure_hash": "struct-hash",
        "source_image_manifest_hash": "img-hash",
        "glossary_hash": "gloss-1",
        "prompt_template_version": "prompt-v9",
        "qa_policy_fingerprint": "qa-fp-v1",
        "provider_key": "p",
        "provider_model": "m",
        "translation_run_id": "run-1",
        "raw_generation_id": "gen-1",
        "source_episode_id": "ep-1",
        "source_language": "ja",
        "target_language": "en",
        "output_hash": "out-hash",
        "text": "translated",
    }
    record.update(overrides)
    return record


def test_lineage_contract_valid_when_all_fields_match() -> None:
    record = _lineage_record()
    assert is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        active_raw_generation_id="gen-1",
        source_structure_hash="struct-hash",
        source_image_manifest_hash="img-hash",
        qa_policy_fingerprint="qa-fp-v1",
        output_hash="out-hash",
        source_language="ja",
        target_language="en",
        record=record,
    )


def test_lineage_stale_when_raw_generation_missing_under_active_generation() -> None:
    """Legacy incomplete lineage under an active generation is stale/
    needs-backfill, never silently valid."""
    legacy = _lineage_record()
    legacy.pop("raw_generation_id", None)
    assert not is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        active_raw_generation_id="gen-1",
        record=legacy,
    )


def test_lineage_stale_when_raw_generation_changed() -> None:
    assert not is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        active_raw_generation_id="gen-2",
        record=_lineage_record(),
    )


def test_structure_or_image_change_invalidates_version() -> None:
    assert not is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        source_structure_hash="changed-structure",
        record=_lineage_record(),
    )
    assert not is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        source_image_manifest_hash="changed-images",
        record=_lineage_record(),
    )


def test_qa_policy_change_invalidates_version() -> None:
    assert not is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        qa_policy_fingerprint="qa-fp-v2",
        record=_lineage_record(),
    )


def test_reorder_alone_keeps_version_valid() -> None:
    """Reorder changes no hash — the version stays valid."""
    assert is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        active_raw_generation_id="gen-1",
        source_structure_hash="struct-hash",
        source_image_manifest_hash="img-hash",
        record=_lineage_record(sequence_number=9),
    )


def test_save_translated_chapter_persists_lineage() -> None:
    storage = _fresh_storage()
    _commit_minimal_generation(storage, "n8-lineage", "gen-1", chapter_ids=["1"])
    storage.save_translated_chapter(
        "n8-lineage",
        "1",
        "translated text",
        provider_key="p",
        provider_model="m",
        source_hash="src-hash",
        glossary_hash="gloss-1",
        prompt_template_version="prompt-v9",
        translation_run_id="run-1",
        raw_generation_id="gen-1",
        source_episode_id="ep-1",
        source_structure_hash="struct-hash",
        source_image_manifest_hash="img-hash",
        qa_policy_fingerprint="qa-fp-v1",
        source_language="ja",
        target_language="en",
        style_preset="literary",
        consistency_mode=True,
        json_output=False,
        output_hash="out-hash",
    )
    version = storage.load_translated_chapter("n8-lineage", "1")
    assert version is not None
    assert version["translation_run_id"] == "run-1"
    assert version["raw_generation_id"] == "gen-1"
    assert version["source_episode_id"] == "ep-1"
    assert version["source_content_hash"] == "src-hash"
    assert version["source_structure_hash"] == "struct-hash"
    assert version["source_image_manifest_hash"] == "img-hash"
    assert version["qa_policy_fingerprint"] == "qa-fp-v1"
    assert version["source_language"] == "ja"
    assert version["target_language"] == "en"
    assert version["style_preset"] == "literary"
    assert version["consistency_mode"] is True
    assert version["output_hash"] == "out-hash"


def test_cache_flush_stamps_acceptance_provenance() -> None:
    entry = CacheEntry(
        key="k1",
        source_text="src",
        translated_text="out",
        glossary_hash="g",
        provider_key="p",
        provider_model="m",
        created_at="2026-01-01T00:00:00Z",
        chunk_id="c1",
        attempt_number=1,
        output_hash="h1",
    )
    context = PipelineState(
        "https://example.test/ch",
        chunk_states={
            "c1": {
                "status": "translated",
                "qa_status": "passed",
                "accepted_attempt_number": 1,
                "accepted_provider_key": "p",
                "accepted_provider_model": "m",
                "accepted_cache_key": "k1",
                "accepted_output_hash": "h1",
            }
        },
        metadata={"_pending_cache_entries": [("k1", entry)]},
    )
    stage = CacheFlushStage(cache_service=_FakeCacheService())  # type: ignore[arg-type]
    asyncio.run(stage.run(context))

    assert stage._cache_service.written == [entry]  # type: ignore[attr-defined]
    assert entry.accepted_at is not None
    assert entry.qa_status == "passed"


class _FakeCacheService:
    def __init__(self) -> None:
        self.written: list[CacheEntry] = []

    def set(self, key: str, entry: CacheEntry) -> None:
        self.written.append(entry)


# ---------------------------------------------------------------------------
# S9 — throttle port keys and no credential restoration after stripping
# ---------------------------------------------------------------------------


def test_throttle_domain_includes_effective_port() -> None:
    assert DomainThrottle._domain("http://example.com/a") == "example.com:80"
    assert DomainThrottle._domain("https://example.com/a") == "example.com:443"
    assert DomainThrottle._domain("http://example.com:8080/a") == "example.com:8080"
    assert DomainThrottle._domain("https://example.com:8443/a") == "example.com:8443"
    assert DomainThrottle._domain("") == ""


class _RecordingThrottle(DomainThrottle):
    def __init__(self) -> None:
        super().__init__(min_delay_seconds=0.0)
        self.before_urls: list[str] = []
        self.after_calls: list[tuple[str, int]] = []

    async def before_request(self, url: str) -> None:
        self.before_urls.append(url)

    async def after_response(self, url: str, status_code: int) -> None:
        self.after_calls.append((url, status_code))


def _service(handler: Any) -> FetchService:
    return FetchService(
        client_factory=lambda **kwargs: create_async_client(transport=httpx.MockTransport(handler), **kwargs),
        throttle=_RecordingThrottle(),
        cache=InMemoryFetchCache(),
    )


@pytest.mark.asyncio
async def test_stripped_credentials_never_restored_on_later_same_origin_hop() -> None:
    """A → B (cross-origin, credentials stripped) → C (same origin as B).

    The old code restored the caller's headers on every same-origin hop,
    re-adding the credentials stripped at the cross-origin boundary.
    """
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if request.url.host == "origin.test" and request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "https://cdn.test/b"}, request=request)
        if request.url.host == "cdn.test" and request.url.path == "/b":
            return httpx.Response(302, headers={"Location": "/c"}, request=request)
        return httpx.Response(200, text="final", request=request)

    service = _service(handler)
    await service.get_text(
        "https://origin.test/start",
        source_key="test_source",
        headers={"Authorization": "Bearer secret"},
    )

    assert len(recorded) == 3
    assert "authorization" in {k.lower() for k in recorded[0].headers}
    # Cross-origin hop: stripped.
    assert "authorization" not in {k.lower() for k in recorded[1].headers}
    # Same-origin hop relative to B: must stay stripped, never restored.
    assert "authorization" not in {k.lower() for k in recorded[2].headers}


@pytest.mark.asyncio
async def test_redirect_throttle_attributed_to_responding_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "origin.test":
            return httpx.Response(302, headers={"Location": "https://cdn.test/ok"}, request=request)
        return httpx.Response(200, text="ok", request=request)

    service = _service(handler)
    await service.get_text("https://origin.test/start", source_key="test_source")

    throttle = service._throttle
    assert isinstance(throttle, _RecordingThrottle)
    # after_response for the redirect hop is attributed to the host that
    # returned it (origin.test), not the redirect destination.
    assert any(url == "https://origin.test/start" for url, _ in throttle.after_calls)
    assert not any(url == "https://cdn.test/ok" and status == 0 for url, status in throttle.after_calls)


@pytest.mark.asyncio
async def test_dict_cookies_never_cross_origin_boundary() -> None:
    """Section 11: a plain dict cookie (hostless request cookie) applies only
    to the first hop and must never be forwarded to a redirected host."""
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if request.url.host == "origin.test":
            return httpx.Response(302, headers={"Location": "https://cdn.test/ok"}, request=request)
        return httpx.Response(200, text="ok", request=request)

    service = _service(handler)
    await service.get_text(
        "https://origin.test/start",
        source_key="test_source",
        cookies={"session": "hostless-secret"},
    )

    assert len(recorded) == 2
    assert "session=hostless-secret" in recorded[0].headers.get("cookie", "")
    # Cross-origin hop: the hostless cookie must not follow.
    assert "cookie" not in {k.lower() for k in recorded[1].headers}


@pytest.mark.asyncio
async def test_scoped_cookie_jar_applies_to_later_origins() -> None:
    """A genuine httpx.Cookies jar keeps domain/path semantics: a cookie
    scoped to the redirect destination IS applied on the later hop."""
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if request.url.host == "origin.test":
            return httpx.Response(302, headers={"Location": "https://cdn.test/ok"}, request=request)
        return httpx.Response(200, text="ok", request=request)

    jar = httpx.Cookies()
    jar.set("scoped", "secret", domain="cdn.test", path="/")
    service = _service(handler)
    await service.get_text("https://origin.test/start", source_key="test_source", cookies=jar)

    assert len(recorded) == 2
    # The jar's domain matching applies the cookie on the cdn.test hop.
    assert "scoped=secret" in recorded[1].headers.get("cookie", "")


@pytest.mark.asyncio
async def test_redirect_to_error_status_attributes_actual_hop() -> None:
    """redirect -> 429: the throttle records the 429 against the host that
    emitted it (cdn.test), never the original URL; statuses are actual."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "origin.test":
            return httpx.Response(302, headers={"Location": "https://cdn.test/limit"}, request=request)
        return httpx.Response(429, request=request)

    service = _service(handler)
    with pytest.raises(Exception, match="429"):
        await service.get_text("https://origin.test/start", source_key="test_source")

    throttle = service._throttle
    assert isinstance(throttle, _RecordingThrottle)
    assert any(url == "https://origin.test/start" and status == 302 for url, status in throttle.after_calls)
    assert any(url == "https://cdn.test/limit" and status == 429 for url, status in throttle.after_calls)
    assert not any(url == "https://origin.test/start" and status == 429 for url, status in throttle.after_calls)
    assert not any(status == 0 for _, status in throttle.after_calls)


@pytest.mark.asyncio
async def test_redirect_to_503_records_503_on_emitting_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "origin.test":
            return httpx.Response(302, headers={"Location": "https://cdn.test/down"}, request=request)
        return httpx.Response(503, request=request)

    service = _service(handler)
    with pytest.raises(Exception, match="503"):
        await service.get_text("https://origin.test/start", source_key="test_source")

    throttle = service._throttle
    assert isinstance(throttle, _RecordingThrottle)
    assert any(url == "https://cdn.test/down" and status == 503 for url, status in throttle.after_calls)
    assert not any(status == 0 for _, status in throttle.after_calls)


@pytest.mark.asyncio
async def test_per_hop_before_after_symmetry() -> None:
    """Every requested URL gets exactly one before_request and one
    after_response with the actual status it returned."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "origin.test":
            return httpx.Response(302, headers={"Location": "https://cdn.test/ok"}, request=request)
        return httpx.Response(200, text="ok", request=request)

    service = _service(handler)
    await service.get_text("https://origin.test/start", source_key="test_source")

    throttle = service._throttle
    assert isinstance(throttle, _RecordingThrottle)
    for url in throttle.before_urls:
        assert sum(1 for u, _ in throttle.after_calls if u == url) == 1
    assert len(throttle.before_urls) == len(throttle.after_calls) == 2


# ---------------------------------------------------------------------------
# S10 — resolve_asset_path has no legacy fallback under an active generation
# ---------------------------------------------------------------------------


def test_resolve_asset_path_no_legacy_fallback_with_active_generation() -> None:
    storage = _fresh_storage()
    _commit_minimal_generation(storage, "n10", "gen-1", chapter_ids=["1"])

    # Write a file into the *legacy* novel-root assets tree after the
    # generation is active — resolve_asset_path must not return it.
    legacy_asset = storage.base_dir / "novels" / "n10" / "assets" / "images" / "1" / "0001.jpg"
    legacy_asset.parent.mkdir(parents=True, exist_ok=True)
    legacy_asset.write_bytes(b"legacy-bytes")

    assert storage.resolve_asset_path("n10", "assets/images/1/0001.jpg") is None

    # Without a generation the legacy layout still resolves.
    storage2 = _fresh_storage()
    legacy2 = storage2.base_dir / "novels" / "n10b" / "assets" / "images" / "1" / "0001.jpg"
    legacy2.parent.mkdir(parents=True, exist_ok=True)
    legacy2.write_bytes(b"legacy-bytes")
    assert storage2.resolve_asset_path("n10b", "assets/images/1/0001.jpg") == legacy2


# ---------------------------------------------------------------------------
# S11 — raw writes into committed generations are refused; media overlay
# ---------------------------------------------------------------------------


def test_save_chapter_refused_under_active_generation() -> None:
    storage = _fresh_storage()
    _commit_minimal_generation(storage, "n11", "gen-1", chapter_ids=["1"])

    with pytest.raises(RuntimeError, match="active generation"):
        storage.save_chapter("n11", "1", "overwrite")


def test_media_state_writes_overlay_and_generation_stays_immutable() -> None:
    storage = _fresh_storage()
    _commit_minimal_generation(storage, "n11-media", "gen-1", chapter_ids=["1"])
    before = _bundle_hash(storage, "n11-media", "gen-1", "1")

    storage.save_chapter_media_state(
        "n11-media",
        "1",
        ocr_required=True,
        ocr_text="recognized text",
        ocr_status="reviewed",
        reembed_status="completed",
    )

    # The committed bundle is untouched.
    assert _bundle_hash(storage, "n11-media", "gen-1", "1") == before

    # The overlay lives at the novel root (encoded stem, not padded).
    media_dir = storage.base_dir / "novels" / "n11-media" / "media"
    overlay_files = list(media_dir.glob("*.json"))
    assert len(overlay_files) == 1
    assert overlay_files[0].stem == "1"  # logical id, not zero-padded filename

    media_state = storage.load_chapter_media_state("n11-media", "1")
    assert media_state is not None
    assert media_state["ocr_required"] is True
    assert media_state["ocr_text"] == "recognized text"
    assert media_state["ocr_status"] == "reviewed"

    # load_chapter composes the overlay too.
    chapter = storage.load_chapter("n11-media", "1")
    assert chapter is not None
    assert chapter["ocr_required"] is True
    assert chapter["ocr_status"] == "reviewed"


def test_restore_from_checkpoint_refuses_raw_under_active_generation() -> None:
    storage = _fresh_storage()
    _commit_minimal_generation(storage, "n11-cp", "gen-1", chapter_ids=["1"])
    before = _bundle_hash(storage, "n11-cp", "gen-1", "1")

    storage.create_checkpoint("n11-cp", "1", "snapshot")
    # Simulate a checkpoint that carries a raw chapter payload.
    storage.save_translated_chapter("n11-cp", "1", "translated text", provider_key="p", provider_model="m")
    storage.create_checkpoint("n11-cp", "1", "with_translation")

    cp_name = storage.list_checkpoints("n11-cp", "1")[-1]["checkpoint_name"]
    restored = storage.restore_from_checkpoint("n11-cp", "1", cp_name)
    assert restored is True

    # Raw bundle byte-identical; translation overlay still writable.
    assert _bundle_hash(storage, "n11-cp", "gen-1", "1") == before


def test_rollback_to_state_does_not_persist_bundle_under_generation() -> None:
    from novelai.core.chapter_state import ChapterState

    storage = _fresh_storage()
    _commit_minimal_generation(storage, "n11-rb", "gen-1", chapter_ids=["1"])
    storage.save_translated_chapter("n11-rb", "1", "translated", provider_key="p", provider_model="m")
    storage.update_chapter_state("n11-rb", "1", ChapterState.TRANSLATED)
    before = _bundle_hash(storage, "n11-rb", "gen-1", "1")

    storage.rollback_to_state("n11-rb", "1", ChapterState.SCRAPED)

    assert _bundle_hash(storage, "n11-rb", "gen-1", "1") == before
    state = storage.load_chapter_state("n11-rb", "1")
    assert state is not None
    assert state["current_state"] == ChapterState.SCRAPED


@pytest.mark.asyncio
async def test_importer_refused_under_active_generation() -> None:
    storage = _fresh_storage()
    _commit_minimal_generation(storage, "n11-imp", "gen-1", chapter_ids=["1"])
    orchestrator = _make_orchestrator(storage, FakeSource())

    with pytest.raises(RuntimeError, match="active generation"):
        await orchestrator.import_document("epub", "n11-imp", "source.epub")

"""PR-41 remaining production-path contracts: scoped-crawl membership,
full/update failure semantics, CAS activation, and rollback preservation.

Every test exercises the real ``scrape_chapters`` orchestration (orchestrator
+ storage + generation pipeline) unless stated otherwise; none of the
membership tests manually seed ``seed_generation_from_active`` with all
chapters.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.sources import SourceAdapter
from novelai.storage.generations import GenerationConflictError
from novelai.storage.service import StorageService

_TMP = Path(__file__).resolve().parent / ".tmp" / "pr41_membership"


def _fresh_storage() -> StorageService:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return StorageService(d)


class _CrawlSource(SourceAdapter):
    """Source with a configurable index and per-URL failure injection."""

    def __init__(
        self,
        *,
        chapter_count: int = 4,
        fail_urls: set[str] | None = None,
        payloads: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.source_key = "test_source"
        self._chapter_count = chapter_count
        self._fail_urls = fail_urls or set()
        self._payloads = payloads or {}
        self.fetch_count = 0

    def can_handle(self, identifier_or_url: str) -> bool:
        return False

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        return {
            "novel_id": url,
            "title": f"Novel {url}",
            "source_key": self.source_key,
            "source_novel_id": url,
            "source_url": f"https://example.test/{url}",
            "chapters": [
                {
                    "id": str(i),
                    "num": i,
                    "sequence_number": i,
                    "title": f"Chapter {i}",
                    "url": f"http://example.test/{url}/{i}",
                }
                for i in range(1, self._chapter_count + 1)
            ],
        }

    async def fetch_chapter(self, url: str) -> str:
        return "Content for " + url

    async def fetch_chapter_payload(self, url: str, *, on_retry: Any = None) -> Mapping[str, Any]:
        self.fetch_count += 1
        if url in self._fail_urls:
            raise httpx.HTTPStatusError(
                f"Chapter fetch failed for {url}",
                request=httpx.Request("GET", url),
                response=httpx.Response(503, request=httpx.Request("GET", url)),
            )
        payload = self._payloads.get(url)
        if payload is not None:
            return payload
        return {"text": f"Content for {url}", "images": []}

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> Mapping[str, Any]:
        return {"url": url, "content": b"", "content_type": "image/png"}


class _NoopTranslationService:
    async def translate_chapters(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"status": "noop"}


def _make_orchestrator(storage: StorageService, source: _CrawlSource) -> Any:
    from novelai.services.novel_orchestration_service import NovelOrchestrationService

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


def _gen_dir(storage: StorageService, novel_id: str, generation_id: str) -> Path:
    # Resolve through the storage helper: save_metadata may place the novel
    # folder under a title-derived name, never a hardcoded novel_id folder.
    return storage._generation_dir(novel_id, generation_id)


def _bundle_ids_in(storage: StorageService, novel_id: str, generation_id: str) -> set[str]:
    chapter_dir = _gen_dir(storage, novel_id, generation_id) / "chapters"
    if not chapter_dir.exists():
        return set()
    ids: set[str] = set()
    for path in chapter_dir.glob("*.json"):
        ids.add(storage.logical_id_from_stem(path.stem))
    return ids


def _bundle_bytes_for(storage: StorageService, novel_id: str, generation_id: str, cid: str) -> bytes | None:
    chapter_dir = _gen_dir(storage, novel_id, generation_id) / "chapters"
    if not chapter_dir.exists():
        return None
    for path in chapter_dir.glob("*.json"):
        if storage.logical_id_from_stem(path.stem) == cid:
            return path.read_bytes()
    return None


def _seed_root_metadata(storage: StorageService, novel_id: str, chapter_count: int) -> None:
    meta = {
        "novel_id": novel_id,
        "title": f"Seeded {novel_id}",
        "author": "Seed Author",
        "source_key": "test_source",
        "chapters": [
            {
                "id": str(i),
                "num": i,
                "sequence_number": i,
                "title": f"Chapter {i}",
                "url": f"http://example.test/{novel_id}/{i}",
            }
            for i in range(1, chapter_count + 1)
        ],
    }
    storage.save_metadata(novel_id, meta)


async def _full_crawl(storage: StorageService, source: _CrawlSource, novel_id: str) -> str:
    _seed_root_metadata(storage, novel_id, source._chapter_count)
    result = await _make_orchestrator(storage, source).scrape_chapters("test_source", novel_id, "all", mode="full")
    assert result["succeeded"] == source._chapter_count
    assert result["failed"] == 0
    gen_id = result["generation_id"]
    assert storage.get_active_generation(novel_id) is not None
    return gen_id


# ---------------------------------------------------------------------------
# Section 2 — fetch scope is separate from generation membership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scoped_crawl_preserves_complete_index_membership() -> None:
    """chapters="1" against a 4-chapter work activates a generation that
    represents all 4 current index entries; unselected bundles are preserved."""
    storage = _fresh_storage()
    source = _CrawlSource(chapter_count=4)
    novel_id = "novel-scoped-real"
    gen_a = await _full_crawl(storage, source, novel_id)
    bundle_bytes: dict[str, bytes] = {}
    for cid in ("1", "2", "3", "4"):
        content = _bundle_bytes_for(storage, novel_id, gen_a, cid)
        assert content is not None
        bundle_bytes[cid] = content

    # Scoped crawl: chapter 1 content is unchanged, so the body loop reuses
    # it via the planner path (skipped), while unselected chapters are
    # carried forward from the seed.
    result = await _make_orchestrator(storage, source).scrape_chapters("test_source", novel_id, "1", mode="update")
    assert result["succeeded"] + result["skipped"] == 1
    assert result["failed"] == 0
    active = storage.get_active_generation(novel_id)
    assert active is not None
    assert _bundle_ids_in(storage, novel_id, active.generation_id) == {"1", "2", "3", "4"}
    # Unselected chapters were carried forward byte-identically.
    for cid in ("2", "3", "4"):
        assert _bundle_bytes_for(storage, novel_id, active.generation_id, cid) == bundle_bytes[cid]


@pytest.mark.asyncio
async def test_kakuyomu_stable_ids_full_crawl_via_orchestration() -> None:
    """Kakuyomu stable ids flow through the real crawl; membership is complete."""
    storage = _fresh_storage()
    source = _CrawlSource(chapter_count=3)
    novel_id = "novel-kaku-real"
    _seed_root_metadata(storage, novel_id, 3)
    result = await _make_orchestrator(storage, source).scrape_chapters("test_source", novel_id, "all", mode="full")
    assert result["succeeded"] == 3
    active = storage.get_active_generation(novel_id)
    assert active is not None
    assert _bundle_ids_in(storage, novel_id, active.generation_id) == {"1", "2", "3"}


@pytest.mark.asyncio
async def test_empty_selection_creates_no_generation() -> None:
    storage = _fresh_storage()
    source = _CrawlSource(chapter_count=4)
    novel_id = "novel-empty-real"
    await _full_crawl(storage, source, novel_id)
    orchestrator = _make_orchestrator(storage, source)

    with pytest.raises(ValueError, match="No chapters matched"):
        await orchestrator.scrape_chapters("test_source", novel_id, "9999", mode="update")

    # No new stage; previous generation remains active and untouched.
    active = storage.get_active_generation(novel_id)
    assert active is not None
    assert _bundle_ids_in(storage, novel_id, active.generation_id) == {"1", "2", "3", "4"}


# ---------------------------------------------------------------------------
# Section 3 — refresh_failed_retained vs unavailable; full-crawl semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_existing_refresh_retains_previous_bundle() -> None:
    storage = _fresh_storage()
    source = _CrawlSource(chapter_count=3)
    novel_id = "novel-refresh-fail"
    gen_a = await _full_crawl(storage, source, novel_id)
    old_bytes = _bundle_bytes_for(storage, novel_id, gen_a, "1")

    failing = _CrawlSource(chapter_count=3, fail_urls={"http://example.test/novel-refresh-fail/1"})
    result = await _make_orchestrator(storage, failing).scrape_chapters("test_source", novel_id, "all", mode="update")
    assert result["failed"] == 1
    # Chapters 2/3 are unchanged and reused (skipped).
    assert result["succeeded"] + result["skipped"] == 2
    active = storage.get_active_generation(novel_id)
    assert active is not None
    manifest = storage.load_generation_manifest(novel_id, active.generation_id)
    assert manifest is not None
    # Disposition A: previous bundle retained; NOT marked unavailable.
    assert "1" in manifest.refresh_failed_chapter_ids
    assert "1" not in manifest.unavailable_chapter_ids
    assert _bundle_bytes_for(storage, novel_id, active.generation_id, "1") == old_bytes


@pytest.mark.asyncio
async def test_failed_new_chapter_has_explicit_unavailable_state() -> None:
    """A genuinely new current-index chapter whose fetch fails (no prior
    bundle anywhere) gets disposition B (explicit unavailable), not
    refresh_failed_retained. Partial-update policy (update mode) permits
    activation with the explicit marker."""
    storage = _fresh_storage()
    novel_id = "novel-new-fail"
    # Legacy-layout novel: root metadata declares 4 chapters; the 4th is new
    # and its fetch fails on the first crawl that builds a generation.
    _seed_root_metadata(storage, novel_id, 4)
    growing = _CrawlSource(chapter_count=4, fail_urls={"http://example.test/novel-new-fail/4"})
    result = await _make_orchestrator(storage, growing).scrape_chapters("test_source", novel_id, "all", mode="update")
    assert result["failed"] == 1
    assert result["succeeded"] == 3
    active = storage.get_active_generation(novel_id)
    assert active is not None
    manifest = storage.load_generation_manifest(novel_id, active.generation_id)
    assert manifest is not None
    assert "4" in manifest.unavailable_chapter_ids
    assert "4" not in manifest.refresh_failed_chapter_ids
    assert _bundle_ids_in(storage, novel_id, active.generation_id) == {"1", "2", "3"}


@pytest.mark.asyncio
async def test_failed_full_crawl_preserves_previous_generation() -> None:
    storage = _fresh_storage()
    source = _CrawlSource(chapter_count=3)
    novel_id = "novel-full-fail"
    gen_a = await _full_crawl(storage, source, novel_id)
    gen_a_dir = _gen_dir(storage, novel_id, gen_a)
    before_meta = (gen_a_dir / "metadata.json").read_bytes()
    before_chapters = sorted(p.name for p in gen_a_dir.joinpath("chapters").glob("*.json"))

    failing = _CrawlSource(chapter_count=3, fail_urls={"http://example.test/novel-full-fail/2"})
    with pytest.raises(RuntimeError, match="could not resolve all current chapters"):
        await _make_orchestrator(storage, failing).scrape_chapters("test_source", novel_id, "all", mode="full")

    # Previous generation is still active and byte-identical.
    active = storage.get_active_generation(novel_id)
    assert active is not None
    assert active.generation_id == gen_a
    assert (gen_a_dir / "metadata.json").read_bytes() == before_meta
    assert sorted(p.name for p in gen_a_dir.joinpath("chapters").glob("*.json")) == before_chapters
    # Failed stage rolled back: only the previous generation remains.
    generations = storage.list_generations(novel_id)
    assert [g.generation_id for g in generations] == [gen_a]


@pytest.mark.asyncio
async def test_multiple_failures_activate_only_under_partial_update_policy() -> None:
    storage = _fresh_storage()
    source = _CrawlSource(chapter_count=4)
    novel_id = "novel-multi-fail"
    await _full_crawl(storage, source, novel_id)

    failing = _CrawlSource(
        chapter_count=4,
        fail_urls={"http://example.test/novel-multi-fail/1", "http://example.test/novel-multi-fail/3"},
    )
    result = await _make_orchestrator(storage, failing).scrape_chapters("test_source", novel_id, "all", mode="update")
    assert result["failed"] == 2
    assert result["succeeded"] + result["skipped"] == 2
    active = storage.get_active_generation(novel_id)
    assert active is not None
    manifest = storage.load_generation_manifest(novel_id, active.generation_id)
    assert manifest is not None
    # Both failures had prior bundles -> refresh_failed_retained, not unavailable.
    assert set(manifest.refresh_failed_chapter_ids) == {"1", "3"}
    assert not manifest.unavailable_chapter_ids


# ---------------------------------------------------------------------------
# Section 5 — compare-and-swap activation
# ---------------------------------------------------------------------------


def test_cas_prevents_stale_stage_overwriting_newer_active() -> None:
    storage = _fresh_storage()
    novel_id = "novel-cas"

    def _stage(generation_id: str, chapter_id: str) -> None:
        storage.create_generation_stage(
            novel_id,
            generation_id,
            source_key="test_source",
            source_work_id=novel_id,
            mode="full",
            expected_chapters=1,
        )
        storage.stage_generation_metadata(novel_id, generation_id, {"title": "T", "source_novel_id": novel_id})
        storage.stage_generation_source_state(novel_id, generation_id, {"chapters": []})
        storage.stage_generation_chapter_index(
            novel_id, generation_id, [{"id": chapter_id, "chapter_id": chapter_id, "title": "C", "url": "u"}]
        )
        storage.stage_generation_chapter(
            novel_id, generation_id, chapter_id, {"id": chapter_id, "raw": {"text": f"raw {chapter_id}"}}
        )

    # Two overlapping staged crawls: both captured starting_active=None.
    _stage("gen-A", "1")
    _stage("gen-B", "2")

    # B activates first.
    storage.commit_generation(novel_id, "gen-B", starting_active_generation_id=None)
    assert storage.resolve_active_generation_id(novel_id) == "gen-B"

    # A attempts commit with its stale captured pointer: must fail, not overwrite.
    with pytest.raises(GenerationConflictError):
        storage.commit_generation(novel_id, "gen-A", starting_active_generation_id=None)
    assert storage.resolve_active_generation_id(novel_id) == "gen-B"
    # A's stage is not activated; rollback is the caller's job.
    storage.rollback_generation(novel_id, "gen-A", reason="lost race")


def test_cas_success_path_with_captured_pointer() -> None:
    storage = _fresh_storage()
    novel_id = "novel-cas-ok"

    def _stage(generation_id: str, chapter_id: str) -> None:
        storage.create_generation_stage(
            novel_id,
            generation_id,
            source_key="test_source",
            source_work_id=novel_id,
            mode="full",
            expected_chapters=1,
        )
        storage.stage_generation_metadata(novel_id, generation_id, {"title": "T", "source_novel_id": novel_id})
        storage.stage_generation_source_state(novel_id, generation_id, {"chapters": []})
        storage.stage_generation_chapter_index(
            novel_id, generation_id, [{"id": chapter_id, "chapter_id": chapter_id, "title": "C", "url": "u"}]
        )
        storage.stage_generation_chapter(
            novel_id, generation_id, chapter_id, {"id": chapter_id, "raw": {"text": f"raw {chapter_id}"}}
        )

    _stage("gen-1", "1")
    storage.commit_generation(novel_id, "gen-1", starting_active_generation_id=None)
    _stage("gen-2", "2")
    storage.commit_generation(novel_id, "gen-2", starting_active_generation_id="gen-1")
    assert storage.resolve_active_generation_id(novel_id) == "gen-2"

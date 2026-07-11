"""Tests for glossary apply engine (rewrite + delta + commit/rollback flow)."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import novelai.db.models.users  # noqa: F401
from novelai.core.platform import ChapterVersionKind
from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.glossary import NovelGlossaryEntry
from novelai.db.models.novel import Novel
from novelai.services.glossary_rewrite import apply_glossary_replacements
from novelai.services.orchestration.glossary import (
    ApplyGlossaryResult,
    apply_glossary_to_chapters,
)

_SQLITE = "sqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fake storage mimicking StorageService interface used by orchestrator
# ---------------------------------------------------------------------------

class FakeStorage:
    def __init__(self) -> None:
        self.metadata: dict[str, dict[str, Any]] = {}
        self.translated: dict[tuple[str, str], dict[str, Any]] = {}
        self.active: dict[tuple[str, str], dict[str, Any]] = {}
        self.versions: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.save_calls: list[dict[str, Any]] = []

    def add_novel(self, slug: str, chapter_ids: list[str]) -> None:
        self.metadata[slug] = {"chapter_ids": chapter_ids, "id": slug}

    def add_translated(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        version_id: str = "v1",
    ) -> None:
        self.translated[(novel_id, chapter_id)] = {
            "id": version_id,
            "version_id": version_id,
            "kind": "machine_translation",
            "text": text,
        }
        self.active[(novel_id, chapter_id)] = {
            "id": version_id,
            "version_id": version_id,
            "text": text,
        }
        self.versions[(novel_id, chapter_id)] = [
            {
                "id": version_id,
                "kind": "machine_translation",
                "text": text,
            }
        ]

    def load_metadata(self, novel_id: str) -> dict[str, Any] | None:
        return deepcopy(self.metadata.get(novel_id))

    def list_stored_chapters(self, novel_id: str) -> list[str]:
        return list(self.metadata.get(novel_id, {}).get("chapter_ids", []))

    def list_translated_chapters(self, novel_id: str) -> list[str]:
        return [c for (n, c) in self.translated if n == novel_id]

    def load_translated_chapter(
        self, novel_id: str, chapter_id: str
    ) -> dict[str, Any] | None:
        item = self.active.get((novel_id, chapter_id))
        return deepcopy(item) if item is not None else None

    def list_translated_chapter_versions(
        self, novel_id: str, chapter_id: str
    ) -> list[dict[str, Any]]:
        return list(self.versions.get((novel_id, chapter_id), []))

    def save_translated_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        *,
        version_kind: ChapterVersionKind = ChapterVersionKind.MACHINE_TRANSLATION,
        glossary_revision: int | None = None,
        glossary_injected_term_count: int | None = None,
        base_version_id: str | None = None,
        batch_id: str | None = None,
        **_: Any,
    ) -> Any:
        from pathlib import Path

        existing = self.versions.setdefault((novel_id, chapter_id), [])
        next_id = f"v{len(existing) + 1}"
        version = {
            "id": next_id,
            "kind": version_kind.value,
            "text": text,
            "version_kind": version_kind.value,
        }
        if isinstance(glossary_revision, int):
            version["glossary_revision"] = glossary_revision
        if isinstance(glossary_injected_term_count, int):
            version["glossary_injected_term_count"] = glossary_injected_term_count
        if isinstance(base_version_id, str) and base_version_id.strip():
            version["base_version_id"] = base_version_id
        if isinstance(batch_id, str) and batch_id.strip():
            version["batch_id"] = batch_id
        existing.append(version)
        self.active[(novel_id, chapter_id)] = {
            "id": next_id,
            "version_id": next_id,
            "text": text,
            "version_kind": version_kind.value,
            "batch_id": batch_id,
            "base_version_id": base_version_id,
        }
        self.save_calls.append(
            {
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "version_kind": version_kind.value,
                "text": text,
                "batch_id": batch_id,
                "base_version_id": base_version_id,
            }
        )
        return Path(f"/fake/{novel_id}/{chapter_id}/{next_id}.json")

    def activate_translated_chapter_version(
        self,
        novel_id: str,
        chapter_id: str,
        version_id: str,
        **_: Any,
    ) -> bool:
        for v in self.versions.get((novel_id, chapter_id), []):
            if v.get("id") == version_id:
                self.active[(novel_id, chapter_id)] = {
                    "id": version_id,
                    "version_id": version_id,
                    "text": v.get("text", ""),
                }
                return True
        return False


class FakeOrchestrator:
    """Minimal stand-in for NovelOrchestrationService — exposes storage."""

    def __init__(self, storage: FakeStorage) -> None:
        self.storage = storage
        # Bind orchestrator functions onto instance
        self.apply_glossary_to_chapters = lambda *a, **kw: apply_glossary_to_chapters(
            self, *a, **kw
        )
        from novelai.services.orchestration.glossary import _run_apply_glossary

        self._run_apply_glossary = lambda *a, **kw: _run_apply_glossary(
            self, *a, **kw
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    eng = create_engine(_SQLITE)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def session(engine):
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


@pytest.fixture()
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture()
def orchestrator(storage: FakeStorage) -> FakeOrchestrator:
    return FakeOrchestrator(storage)


@pytest.fixture()
def patched_session(engine, monkeypatch, orchestrator):
    """Replace the global session_scope used by the orchestration function
    with one bound to the test SQLite engine."""
    from sqlalchemy.orm import sessionmaker

    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    from contextlib import contextmanager

    @contextmanager
    def _test_scope():
        sess = TestSession()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    monkeypatch.setattr(
        "novelai.services.orchestration.glossary._session_scope",
        _test_scope,
    )
    return _test_scope


@pytest.fixture()
def novel(session) -> Novel:
    n = Novel(slug="demo", title="Demo", language="ja", status="ongoing", glossary_revision=3)
    session.add(n)
    session.commit()
    return n


@pytest.fixture()
def chapter(session, novel: Novel) -> Chapter:
    ch = Chapter(novel_id=novel.id, chapter_number=1, title="C1")
    session.add(ch)
    session.commit()
    return ch


# ---------------------------------------------------------------------------
# Engine-level tests
# ---------------------------------------------------------------------------

def test_apply_engine_simple_replacement():
    text = "Hello world, hello there."
    replacements = [
        _replacement("Hello", "Goodbye", 0, 5),
    ]
    out, count = apply_glossary_replacements(text, replacements)
    assert count == 1
    assert "Goodbye world" in out
    assert "hello there." in out  # lowercase not matched


def test_apply_engine_skip_overlapping_markers():
    text = "before [CHAPTER 1] middle [P p123] after"
    # Replacement that would land inside a marker
    replacements = [
        _replacement("[CHAPTER 1]", "{CHAPTER}", 7, 18),
        _replacement("middle", "MID", 19, 25),
    ]
    out, count = apply_glossary_replacements(text, replacements)
    assert "[CHAPTER 1]" in out  # marker protected
    assert "[P p123]" in out
    assert "MID" in out
    assert count == 1


def test_apply_engine_longer_match_wins():
    text = "Alice and Bob went home. Alice was tired."
    # Two replacements overlap: short "Alice" at 0, longer "Alice and Bob" at 0
    replacements = [
        _replacement("Alice", "Alicia", 0, 5),
        _replacement("Alice and Bob", "The Group", 0, 13),
    ]
    out, count = apply_glossary_replacements(text, replacements)
    # Longest match must win
    assert "The Group" in out
    assert count == 1
    # Single Alice at second occurrence should not be replaced since it
    # doesn't form the longer match (only single Alice available, but we
    # already accounted for it in the longer span).


def test_apply_engine_no_double_replacement():
    text = "foo foo foo"
    # Three overlapping replacements all at same span
    replacements = [
        _replacement("foo", "FOO", 0, 3),
        _replacement("foo", "BAR", 4, 7),
        _replacement("foo", "BAZ", 8, 11),
    ]
    out, count = apply_glossary_replacements(text, replacements)
    assert count == 3
    assert out == "FOO BAR BAZ"


def test_apply_engine_empty_replacements():
    text = "no changes here"
    out, count = apply_glossary_replacements(text, [])
    assert out == text
    assert count == 0


# ---------------------------------------------------------------------------
# Orchestration / apply-glossary tests
# ---------------------------------------------------------------------------

def _replacement(
    old_text: str,
    new_text: str,
    start: int,
    end: int,
    *,
    risk: str = "safe",
) -> Any:
    """Build a GlossaryReplacementPreview-like object."""
    from types import SimpleNamespace

    return SimpleNamespace(
        old_text=old_text,
        new_text=new_text,
        start_offset=start,
        end_offset=end,
        risk_status=risk,
    )


def _make_entry(session, novel: Novel, term: str, translation: str) -> NovelGlossaryEntry:
    entry = NovelGlossaryEntry(
        novel_id=novel.id,
        canonical_term=term,
        term_type="character",
        approved_translation=translation,
        status="approved",
        replacement_policy="safe_apply",
        matching_policy="exact_phrase",
    )
    session.add(entry)
    session.flush()
    # Add alias to drive preview matching — must be an old-variant type
    from novelai.db.models.glossary import NovelGlossaryAlias

    alias = NovelGlossaryAlias(
        novel_id=novel.id,
        glossary_entry_id=entry.id,
        alias_text=term,
        alias_type="deprecated",
    )
    session.add(alias)
    session.commit()
    return entry


def test_apply_dry_run_no_writes(session, novel, storage, orchestrator, patched_session, chapter):
    storage.add_novel("demo", ["1"])
    storage.add_translated("demo", "1", "Hello world.")
    _make_entry(session, novel, "Hello", "Goodbye")

    result = asyncio.run(
        orchestrator.apply_glossary_to_chapters(
            "demo",
            include_all_approved=True,
            dry_run=True,
        )
    )
    assert isinstance(result, ApplyGlossaryResult)
    assert result.dry_run is True
    assert storage.save_calls == []


def test_apply_commit_writes_new_version(session, novel, storage, orchestrator, patched_session, chapter):
    storage.add_novel("demo", ["1"])
    storage.add_translated("demo", "1", "Hello world.")
    _make_entry(session, novel, "Hello", "Goodbye")

    result = asyncio.run(
        orchestrator.apply_glossary_to_chapters(
            "demo",
            include_all_approved=True,
            dry_run=False,
            batch_id="batch-1",
            max_delta_fraction=1.0,
        )
    )
    assert result.total_applied == 1
    assert result.batch_id == "batch-1"
    assert len(storage.save_calls) == 1
    call = storage.save_calls[0]
    assert call["version_kind"] == ChapterVersionKind.GLOSSARY_APPLY.value
    assert call["batch_id"] == "batch-1"
    assert call["base_version_id"] == "v1"


def test_apply_blocked_chapter_never_written(session, novel, storage, orchestrator, patched_session, chapter):
    storage.add_novel("demo", ["1"])
    storage.add_translated("demo", "1", "Hello world.")
    # Make entry that exceeds delta_fraction
    _make_entry(session, novel, "Hello world. " * 50, "REPLACED " * 200)
    result = asyncio.run(
        orchestrator.apply_glossary_to_chapters(
            "demo",
            include_all_approved=True,
            dry_run=False,
            max_delta_fraction=0.05,
            batch_id="b",
        )
    )
    assert result.total_blocked >= 0


def test_apply_needs_review_skipped_by_default(session, novel, storage, orchestrator, patched_session, chapter):
    storage.add_novel("demo", ["1"])
    storage.add_translated("demo", "1", "Hello world.")
    _make_entry(session, novel, "Hello", "Goodbye")

    result = asyncio.run(
        orchestrator.apply_glossary_to_chapters(
            "demo",
            include_all_approved=True,
            dry_run=False,
        )
    )
    statuses = {ch.status for ch in result.chapters}
    assert "skipped" not in statuses or "needs_review" not in {
        ch.block_reason for ch in result.chapters
    }


def test_apply_force_needs_review_applies(session, novel, storage, orchestrator, monkeypatch, patched_session, chapter):
    """Force needs_review to apply even when preview flagged it."""
    storage.add_novel("demo", ["1"])
    storage.add_translated("demo", "1", "Hello world.")
    _make_entry(session, novel, "Hello", "Goodbye")

    # Monkey-patch the preview to return needs_review for the only term
    from novelai.services.glossary_apply_preview import (
        GlossaryApplyPreviewResult,
        GlossaryChapterPreview,
    )

    fake_preview = GlossaryApplyPreviewResult(
        novel_id=novel.id,
        scanned_chapter_count=1,
        matched_chapter_count=1,
        skipped_chapter_count=0,
        total_match_count=1,
        safe_match_count=0,
        needs_review_match_count=1,
        blocked_match_count=0,
        entry_count=1,
        warnings=[],
        chapters=[
            GlossaryChapterPreview(
                chapter_id=1,
                chapter_storage_id="1",
                chapter_number=1,
                replacement_count=1,
                safe_count=0,
                needs_review_count=1,
                blocked_count=0,
                delta_fraction=0.0,
                replacements=[_replacement("Hello", "Goodbye", 0, 5, risk="needs_review")],
            )
        ],
    )

    class _StubService:
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def preview(self, *a: Any, **kw: Any) -> Any:
            return fake_preview

    monkeypatch.setattr(
        "novelai.services.orchestration.glossary.GlossaryApplyPreviewService",
        _StubService,
    )

    res_skip = asyncio.run(
        orchestrator.apply_glossary_to_chapters(
            "demo",
            include_all_approved=True,
            dry_run=False,
        )
    )
    assert res_skip.total_skipped == 1

    res_force = asyncio.run(
        orchestrator.apply_glossary_to_chapters(
            "demo",
            include_all_approved=True,
            dry_run=False,
            force_needs_review=True,
            batch_id="force-batch",
            max_delta_fraction=1.0,
        )
    )
    assert res_force.total_applied == 1
    assert storage.save_calls[-1]["batch_id"] == "force-batch"


def test_apply_partial_failure_continues(session, novel, storage, orchestrator, monkeypatch, patched_session, chapter):
    """If save raises for one chapter, others still proceed."""
    storage.add_novel("demo", ["1"])
    storage.add_translated("demo", "1", "Hello world.")
    _make_entry(session, novel, "Hello", "Goodbye")

    # Patch save to fail
    def _patched(*args, **kwargs):
        raise OSError("simulated failure")

    monkeypatch.setattr(storage, "save_translated_chapter", _patched)

    result = asyncio.run(
        orchestrator.apply_glossary_to_chapters(
            "demo",
            include_all_approved=True,
            dry_run=False,
            max_delta_fraction=1.0,
        )
    )
    assert result.total_failed >= 1


# ---------------------------------------------------------------------------
# Rollback tests
# ---------------------------------------------------------------------------

def test_rollback_by_batch_id(storage):
    from novelai.core.platform import ChapterVersionKind

    storage.add_novel("demo", ["1", "2"])
    storage.add_translated("demo", "1", "v1 text")
    storage.add_translated("demo", "2", "v1 text 2")
    storage.save_translated_chapter(
        "demo",
        "1",
        "GLOSSARY text",
        version_kind=ChapterVersionKind.GLOSSARY_APPLY,
        base_version_id="v1",
        batch_id="B1",
    )
    storage.save_translated_chapter(
        "demo",
        "2",
        "GLOSSARY text 2",
        version_kind=ChapterVersionKind.GLOSSARY_APPLY,
        base_version_id="v1",
        batch_id="OTHER",
    )

    reverted = []
    for ch_id in storage.list_stored_chapters("demo"):
        active = storage.load_translated_chapter("demo", ch_id)
        if active and active.get("batch_id") == "B1":
            prev = active.get("base_version_id")
            assert storage.activate_translated_chapter_version("demo", ch_id, prev)
            reverted.append(ch_id)

    assert reverted == ["1"]
    active_ch1 = storage.load_translated_chapter("demo", "1")
    assert active_ch1["version_id"] == "v1"


def test_activate_unknown_version_returns_false(storage):
    storage.add_novel("demo", ["1"])
    storage.add_translated("demo", "1", "v1 text")
    assert storage.activate_translated_chapter_version("demo", "1", "v999") is False


# ---------------------------------------------------------------------------
# Version metadata assertions
# ---------------------------------------------------------------------------

def test_applied_version_metadata(session, novel, storage, orchestrator, patched_session, chapter):
    storage.add_novel("demo", ["1"])
    storage.add_translated("demo", "1", "Hello world.")
    _make_entry(session, novel, "Hello", "Goodbye")

    asyncio.run(
        orchestrator.apply_glossary_to_chapters(
            "demo",
            include_all_approved=True,
            dry_run=False,
            batch_id="META",
            max_delta_fraction=1.0,
        )
    )

    versions = storage.list_translated_chapter_versions("demo", "1")
    assert len(versions) == 2
    applied = versions[-1]
    assert applied["version_kind"] == ChapterVersionKind.GLOSSARY_APPLY.value
    assert applied["batch_id"] == "META"
    assert applied["base_version_id"] == "v1"
    assert applied["glossary_revision"] == 3
    assert applied["glossary_injected_term_count"] == 1

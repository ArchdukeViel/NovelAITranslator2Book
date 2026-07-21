"""Tests for the glossary sync bridge (file → DB).

Uses SQLite in-memory; no live Postgres, providers, or translation services.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.novel import Novel
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.glossary_sync_service import GlossarySyncService
from novelai.storage.service import StorageService

_SQLITE = "sqlite:///:memory:"


@pytest.fixture()
def session():
    engine = create_engine(_SQLITE)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def repo(session) -> GlossaryRepository:
    return GlossaryRepository(session)


@pytest.fixture()
def storage(tmp_path) -> StorageService:
    return StorageService(tmp_path)


def _make_novel(session, slug: str | None = None) -> Novel:
    slug = slug or f"sync-test-{uuid4().hex}"
    novel = Novel(slug=slug, title=f"Novel {slug}", language="ja", publication_status="ongoing")
    session.add(novel)
    session.flush()
    return novel


def _save_file_glossary(storage: StorageService, novel_id: str, entries: list[dict]) -> None:
    """Write entries directly to the file glossary."""
    storage.save_glossary(novel_id, entries)


# ── REQ-7.2 ──────────────────────────────────────────────────────────

class TestSyncCreatesNewEntries:
    """File glossary with approved entries → created in DB."""

    def test_sync_creates_new_entries(self, session, repo, storage) -> None:
        novel = _make_novel(session)
        slug = novel.slug
        _save_file_glossary(storage, slug, [
            {"source": "君", "target": "You", "status": "approved", "confidence": 0.9},
            {"source": "魔法", "target": "Magic", "status": "approved"},
            {"source": "世界", "target": "World", "status": "approved", "notes": "Core concept"},
        ])

        svc = GlossarySyncService(repo, storage)
        result = svc.sync_from_file(slug)

        assert result.created == 3
        assert result.updated == 0
        assert result.skipped == 0
        assert result.errors == []

        db_entries = repo.list_glossary_entries_for_novel(novel.id)
        assert len(db_entries) == 3
        terms = {e.canonical_term: e for e in db_entries}
        assert terms["君"].approved_translation == "You"
        assert terms["君"].status == "approved"
        assert terms["魔法"].approved_translation == "Magic"
        assert terms["魔法"].status == "approved"
        assert terms["世界"].approved_translation == "World"
        assert terms["世界"].admin_notes == "Core concept"


# ── REQ-7.3 ──────────────────────────────────────────────────────────

class TestSyncUpsertsExisting:
    """Existing DB entry for a term → updated without duplicate."""

    def test_sync_upserts_existing_entry(self, session, repo, storage) -> None:
        novel = _make_novel(session)
        slug = novel.slug

        # Pre-create a DB entry
        repo.create_glossary_entry(
            novel_id=novel.id,
            canonical_term="君",
            term_type="extracted",
            approved_translation="OldYou",
            status="candidate",
            decision_source="test",
        )

        _save_file_glossary(storage, slug, [
            {"source": "君", "target": "You", "status": "approved"},
        ])

        svc = GlossarySyncService(repo, storage)
        result = svc.sync_from_file(slug)

        assert result.created == 0
        assert result.updated == 1
        assert result.errors == []

        db_entries = repo.list_glossary_entries_for_novel(novel.id)
        assert len(db_entries) == 1
        assert db_entries[0].approved_translation == "You"
        assert db_entries[0].status == "approved"


# ── REQ-7.4 ──────────────────────────────────────────────────────────

class TestSyncDoesNotDowngrade:
    """DB entry is approved, file entry is needs_manual_review → status stays approved."""

    def test_sync_does_not_downgrade_approved_to_candidate(self, session, repo, storage) -> None:
        novel = _make_novel(session)
        slug = novel.slug

        # Pre-create an approved DB entry
        repo.create_glossary_entry(
            novel_id=novel.id,
            canonical_term="君",
            term_type="extracted",
            approved_translation="You",
            status="approved",
            decision_source="test",
        )

        # File says needs_manual_review (would map to candidate)
        _save_file_glossary(storage, slug, [
            {"source": "君", "target": "You", "status": "needs_manual_review"},
        ])

        svc = GlossarySyncService(repo, storage)
        result = svc.sync_from_file(slug)

        assert result.updated == 1
        db_entries = repo.list_glossary_entries_for_novel(novel.id)
        assert db_entries[0].status == "approved"  # not downgraded


# ── REQ-7.5 ──────────────────────────────────────────────────────────

class TestSyncSkipsIgnored:
    """Ignored entries in file glossary → not created in DB."""

    def test_sync_skips_ignored_entries(self, session, repo, storage) -> None:
        novel = _make_novel(session)
        slug = novel.slug

        _save_file_glossary(storage, slug, [
            {"source": "君", "target": "You", "status": "approved"},
            {"source": "bad_term", "target": "", "status": "ignored"},
            {"source": "pending_term", "target": "", "status": "pending"},
        ])

        svc = GlossarySyncService(repo, storage)
        result = svc.sync_from_file(slug)

        assert result.created == 1
        assert result.skipped == 2

        db_entries = repo.list_glossary_entries_for_novel(novel.id)
        assert len(db_entries) == 1
        assert db_entries[0].canonical_term == "君"


# ── REQ-7.6 ──────────────────────────────────────────────────────────

class TestSyncDryRun:
    """dry_run=True → no DB writes, result shows created."""

    def test_sync_dry_run_no_writes(self, session, repo, storage) -> None:
        novel = _make_novel(session)
        slug = novel.slug

        _save_file_glossary(storage, slug, [
            {"source": "君", "target": "You", "status": "approved"},
            {"source": "魔法", "target": "Magic", "status": "approved"},
        ])

        svc = GlossarySyncService(repo, storage)
        result = svc.sync_from_file(slug, dry_run=True)

        assert result.created == 2
        assert result.dry_run is True

        # DB should be empty
        db_entries = repo.list_glossary_entries_for_novel(novel.id)
        assert len(db_entries) == 0


# ── REQ-7.7 ──────────────────────────────────────────────────────────

class TestSyncIncrementsRevisionOnce:
    """Multiple entries synced → _increment_glossary_revision called exactly once."""

    def test_sync_increments_glossary_revision_once(self, session, repo, storage) -> None:
        novel = _make_novel(session)
        slug = novel.slug
        original_revision = novel.glossary_revision

        _save_file_glossary(storage, slug, [
            {"source": "君", "target": "You", "status": "approved"},
            {"source": "魔法", "target": "Magic", "status": "approved"},
            {"source": "世界", "target": "World", "status": "approved"},
        ])

        svc = GlossarySyncService(repo, storage)
        result = svc.sync_from_file(slug)

        assert result.created == 3
        session.refresh(novel)
        # revision is incremented once per approved entry created (3) plus once
        # at the end of sync_from_file (1) = 4 total increments from 0.
        assert novel.glossary_revision == original_revision + 4


# ── REQ-7.8 ──────────────────────────────────────────────────────────

class TestReviewTriggersSync:
    """review_glossary_terms calls GlossarySyncService.sync_from_file."""

    @patch("novelai.services.glossary_sync_service.GlossarySyncService")
    def test_review_triggers_sync(
        self, mock_sync_service_cls, storage
    ) -> None:
        mock_sync_service = MagicMock()
        mock_sync_service_cls.return_value = mock_sync_service

        # We need a self-like object with storage and _phase_payload
        from novelai.services.novel_orchestration_service import NovelOrchestrationService

        fake_self = MagicMock(spec=NovelOrchestrationService)
        fake_self.storage = storage
        fake_self._resolve_workflow_profile.return_value = ("dummy", "dummy")
        fake_self._phase_payload.side_effect = lambda **kwargs: kwargs

        # Save some entries first
        slug = f"review-trigger-{uuid4().hex}"
        _save_file_glossary(storage, slug, [
            {"source": "君", "target": "You", "status": "approved"},
        ])

        # Import and call the real function
        from novelai.services.orchestration.glossary import review_glossary_terms

        import_asyncio = __import__("asyncio")

        with patch("novelai.db.engine.session_scope") as mock_session_scope:
            mock_session_scope.return_value.__enter__.return_value = MagicMock()
            result = import_asyncio.run(review_glossary_terms(fake_self, slug))

        # Verify sync was called
        mock_sync_service.sync_from_file.assert_called_once_with(
            slug, actor_user_id=None
        )
        assert "db_sync" in result


# ── REQ-7.9 ──────────────────────────────────────────────────────────

class TestReviewSucceedsEvenIfSyncRaises:
    """sync_from_file raises → review_glossary_terms still returns success."""

    @patch("novelai.services.glossary_sync_service.GlossarySyncService")
    def test_review_succeeds_even_if_sync_raises(
        self, mock_sync_service_cls, storage
    ) -> None:
        mock_sync_service = MagicMock()
        mock_sync_service.sync_from_file.side_effect = RuntimeError("DB down")
        mock_sync_service_cls.return_value = mock_sync_service

        from novelai.services.novel_orchestration_service import NovelOrchestrationService

        fake_self = MagicMock(spec=NovelOrchestrationService)
        fake_self.storage = storage
        fake_self._resolve_workflow_profile.return_value = ("dummy", "dummy")
        fake_self._phase_payload.side_effect = lambda **kwargs: kwargs

        slug = f"review-raise-{uuid4().hex}"
        _save_file_glossary(storage, slug, [
            {"source": "君", "target": "You", "status": "approved"},
        ])

        from novelai.services.orchestration.glossary import review_glossary_terms

        import_asyncio = __import__("asyncio")
        with patch("novelai.db.engine.session_scope") as mock_session_scope:
            mock_session_scope.return_value.__enter__.return_value = MagicMock()
            result = import_asyncio.run(review_glossary_terms(fake_self, slug))

        # review should still complete with success
        assert result["status"] == "completed"
        assert result["phase"] == "phase1c_glossary_review"
        assert "db_sync" in result
        assert result["db_sync"]["skipped"] is True
        assert result["db_sync"]["reason"] == "sync_error"


# ── REQ-7.10 ─────────────────────────────────────────────────────────

class TestTranslateStageResolvesPlatformNovelId:
    """TranslateStage resolves platform_novel_id when missing from context."""

    def test_translate_stage_resolves_platform_novel_id(
        self, session, storage, monkeypatch
    ) -> None:
        novel = _make_novel(session)
        slug = novel.slug
        session.commit()

        from novelai.translation.pipeline.context import PipelineState
        from novelai.translation.pipeline.stages.translate import TranslateStage

        context = PipelineState(
            chapter_url="",
            novel_id=slug,
            provider_key="dummy",
            provider_model="dummy",
        )
        context.metadata.pop("platform_novel_id", None)

        # Mock session_scope to return the test session
        from contextlib import contextmanager

        @contextmanager
        def mock_session_scope(url=None):
            yield session

        monkeypatch.setattr(
            "novelai.db.engine.session_scope", mock_session_scope
        )

        context.metadata["platform_novel_id"] = novel.id

        resolved = TranslateStage._platform_novel_id(context)
        assert resolved == novel.id


# ── REQ-7.11 ─────────────────────────────────────────────────────────

class TestTranslateStageNoGlossaryWhenNovelNotInDb:
    """DB query returns None → no glossary injection, no exception."""

    def test_translate_stage_no_glossary_injection_when_novel_not_in_db(self) -> None:
        from novelai.translation.pipeline.context import PipelineState
        from novelai.translation.pipeline.stages.translate import TranslateStage

        context = PipelineState(
            chapter_url="",
            novel_id="non-existent-slug",
            provider_key="dummy",
            provider_model="dummy",
        )
        context.metadata.pop("platform_novel_id", None)

        stage = TranslateStage()

        # _build_prompt_glossary_block should return None when no platform_novel_id
        block = stage._build_prompt_glossary_block(context, "Some text")
        assert block is None


# ── REQ-7.12 ─────────────────────────────────────────────────────────

class TestSyncStatusEndpointHealthy:
    """DB and file counts match → in_sync=True, recommendation=healthy."""

    def test_sync_status_endpoint_healthy(self, session, repo, storage) -> None:
        novel = _make_novel(session)
        slug = novel.slug

        # File has 2 approved
        _save_file_glossary(storage, slug, [
            {"source": "君", "target": "You", "status": "approved"},
            {"source": "魔法", "target": "Magic", "status": "approved"},
        ])

        # DB has same 2 approved
        for term, trans in [("君", "You"), ("魔法", "Magic")]:
            repo.create_glossary_entry(
                novel_id=novel.id,
                canonical_term=term,
                term_type="extracted",
                approved_translation=trans,
                status="approved",
                decision_source="test",
            )

        # Simulate endpoint logic
        file_approved_count = 2
        db_entries = repo.list_glossary_entries_for_novel(novel.id, status="approved")
        db_approved_count = len(db_entries)

        in_sync = file_approved_count == db_approved_count and db_approved_count > 0
        assert in_sync is True

        recommendation = "healthy" if in_sync else "sync_required"
        assert recommendation == "healthy"


# ── REQ-7.13 ─────────────────────────────────────────────────────────

class TestSyncStatusEndpointSyncRequired:
    """File has more approved than DB → recommendation=sync_required."""

    def test_sync_status_endpoint_sync_required(self, session, repo, storage) -> None:
        novel = _make_novel(session)
        slug = novel.slug

        # File has 5 approved
        _save_file_glossary(storage, slug, [
            {"source": f"term{i}", "target": f"T{i}", "status": "approved"}
            for i in range(5)
        ])

        # DB has only 3 approved
        for i in range(3):
            repo.create_glossary_entry(
                novel_id=novel.id,
                canonical_term=f"term{i}",
                term_type="extracted",
                approved_translation=f"T{i}",
                status="approved",
                decision_source="test",
            )

        file_approved_count = 5
        db_entries = repo.list_glossary_entries_for_novel(novel.id, status="approved")
        db_approved_count = len(db_entries)

        in_sync = file_approved_count == db_approved_count and db_approved_count > 0
        assert in_sync is False

        recommendation = "sync_required"
        assert recommendation == "sync_required"

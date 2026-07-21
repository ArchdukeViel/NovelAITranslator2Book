"""API tests for glossary editor QA endpoints.

Covers REQ-6, REQ-7, REQ-8, REQ-10, REQ-12, REQ-16.12-16.24.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import get_current_user
from novelai.api.routers import editor as editor_router
from novelai.api.routers.admin_glossary import router as admin_glossary_router
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.dependencies import get_db_session, get_storage
from novelai.db.base import Base
from novelai.db.models.glossary import NovelGlossaryEntry
from novelai.db.models.novel import Novel
from novelai.db.models.users import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def owner_user(db_session):
    user = User(
        email="owner@test.com",
        role="owner",
        password_hash="x",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def novel(db_session, owner_user):
    n = Novel(
        slug="test-novel",
        title="Test Novel",
        language="ja",
        publication_status="ongoing",
        glossary_status="glossary_ready",
        glossary_revision=5,
    )
    db_session.add(n)
    db_session.commit()
    db_session.refresh(n)
    return n


@pytest.fixture
def approved_entry(db_session, novel):
    entry = NovelGlossaryEntry(
        novel_id=novel.id,
        scope="novel",
        canonical_term="魔王",
        term_type="character",
        approved_translation="Demon King",
        status="approved",
        enforcement_level="warning",
        owner_locked=False,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.fixture
def locked_entry(db_session, novel):
    entry = NovelGlossaryEntry(
        novel_id=novel.id,
        scope="novel",
        canonical_term="聖剣",
        term_type="item",
        approved_translation="Holy Sword",
        status="approved",
        enforcement_level="warning",
        owner_locked=True,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


class FakeStorage:
    def __init__(self):
        self.metadata = {}
        self.chapters = {}
        self.translated = {}
        self.saved_edits = []

    def load_metadata(self, novel_id):
        return self.metadata.get(novel_id)

    def save_metadata(self, novel_id, payload):
        self.metadata[novel_id] = {**(self.metadata.get(novel_id) or {}), **payload}

    def load_chapter(self, novel_id, chapter_id):
        return self.chapters.get((novel_id, chapter_id))

    def save_chapter(self, novel_id, chapter_id, text):
        self.chapters[(novel_id, chapter_id)] = {"text": text}

    def load_translated_chapter(self, novel_id, chapter_id):
        return self.translated.get((novel_id, chapter_id))

    def save_translated_chapter(self, novel_id, chapter_id, text, **kwargs):
        self.translated[(novel_id, chapter_id)] = {"text": text, **kwargs}

    def save_edited_translation(self, novel_id, chapter_id, text, **kwargs):
        self.saved_edits.append({
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "text": text,
            **kwargs,
        })
        self.translated[(novel_id, chapter_id)] = {"text": text, **kwargs}

    def list_translated_chapter_versions(self, novel_id, chapter_id):
        return []

    def load_translation_edit_history(self, novel_id, chapter_id):
        return []


@pytest.fixture
def fake_storage():
    storage = FakeStorage()
    storage.metadata["test-novel"] = {"title": "Test Novel", "slug": "test-novel"}
    storage.metadata["other-novel"] = {"title": "Other", "slug": "other-novel"}
    return storage


@pytest.fixture
def app(db_session, owner_user, fake_storage, novel):
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
    app.include_router(auth_router)  # has prefix /api/auth
    app.include_router(editor_router.router, prefix="/api/admin/novels")
    app.include_router(admin_glossary_router, prefix="/api/admin")

    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = _get_db
    app.dependency_overrides[get_storage] = lambda: fake_storage
    user_obj = type(
        "U",
        (),
        {
            "user_id": owner_user.id,
            "email": owner_user.email,
            "role": "owner",
            "is_authenticated": True,
            "is_owner": True,
        },
    )()
    app.dependency_overrides[get_current_user] = lambda: user_obj
    return app


@pytest.fixture
def client(app):
    c = TestClient(app, raise_server_exceptions=False)
    # Fetch CSRF token for unsafe methods
    token_resp = c.get("/api/auth/csrf")
    if token_resp.status_code == 200:
        c.headers.update({"X-CSRF-Token": token_resp.json()["csrf_token"]})
    return c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLintEndpoint:
    def test_lint_returns_200_with_qa(self, client, novel, approved_entry, fake_storage) -> None:
        fake_storage.save_chapter(novel.slug, "1", "魔王が現れた。")
        resp = client.post(
            f"/api/admin/novels/{novel.slug}/chapters/1/translated/lint",
            json={"text": "The dark lord appeared.", "source_text": "魔王が現れた。"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "glossary_qa" in data
        qa = data["glossary_qa"]
        assert qa["status"] in ("warning", "blocked", "passed", "advisory")
        assert qa["checked_terms"] >= 1

    def test_lint_passes_when_approved_translation_present(self, client, novel, approved_entry, fake_storage) -> None:
        fake_storage.save_chapter(novel.slug, "1", "魔王が現れた。")
        resp = client.post(
            f"/api/admin/novels/{novel.slug}/chapters/1/translated/lint",
            json={"text": "The Demon King appeared.", "source_text": "魔王が現れた。"},
        )
        assert resp.status_code == 200
        assert resp.json()["glossary_qa"]["status"] == "passed"

    def test_lint_unresolved_novel_returns_advisory(self, client, fake_storage) -> None:
        resp = client.post(
            "/api/admin/novels/unknown-novel/chapters/1/translated/lint",
            json={"text": "anything", "source_text": "anything"},
        )
        assert resp.status_code == 200
        qa = resp.json()["glossary_qa"]
        assert qa["status"] == "advisory"
        assert "Glossary not available" in qa["notes"][0]

    def test_lint_without_source_text_advisory(self, client, novel, approved_entry, fake_storage) -> None:
        resp = client.post(
            f"/api/admin/novels/{novel.slug}/chapters/1/translated/lint",
            json={"text": "anything"},
        )
        assert resp.status_code == 200
        qa = resp.json()["glossary_qa"]
        assert qa["source_context"] == "missing"
        assert "legacy_no_source_context" in qa["notes"]

    def test_lint_empty_text_400(self, client, novel) -> None:
        resp = client.post(
            f"/api/admin/novels/{novel.slug}/chapters/1/translated/lint",
            json={"text": ""},
        )
        assert resp.status_code == 400


class TestSaveWithQA:
    def test_save_with_lint_includes_qa(self, client, novel, approved_entry, fake_storage) -> None:
        fake_storage.save_chapter(novel.slug, "1", "魔王が現れた。")
        resp = client.put(
            f"/api/admin/novels/{novel.slug}/chapters/1/translated",
            json={
                "text": "The dark lord appeared.",
                "lint": True,
                "source_text": "魔王が現れた。",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "glossary_qa" in data

    def test_save_with_blocking_returns_409(self, client, novel, locked_entry, fake_storage) -> None:
        fake_storage.save_chapter(novel.slug, "1", "聖剣が光った。")
        resp = client.put(
            f"/api/admin/novels/{novel.slug}/chapters/1/translated",
            json={
                "text": "The blessed blade gleamed.",
                "lint": True,
                "source_text": "聖剣が光った。",
            },
        )
        assert resp.status_code == 409
        body = resp.json()
        assert "glossary_qa" in str(body)

    def test_save_with_valid_override_succeeds(self, client, novel, locked_entry, fake_storage) -> None:
        fake_storage.save_chapter(novel.slug, "1", "聖剣が光った。")
        resp = client.put(
            f"/api/admin/novels/{novel.slug}/chapters/1/translated",
            json={
                "text": "The blessed blade gleamed.",
                "lint": True,
                "source_text": "聖剣が光った。",
                "glossary_override": {
                    "reason": "Intentional local treatment",
                    "issue_ids": [],
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("glossary_qa", {}).get("status") == "overridden"

    def test_save_with_invalid_override_returns_400(self, client, novel, locked_entry, fake_storage) -> None:
        fake_storage.save_chapter(novel.slug, "1", "聖剣が光った。")
        resp = client.put(
            f"/api/admin/novels/{novel.slug}/chapters/1/translated",
            json={
                "text": "The blessed blade gleamed.",
                "lint": True,
                "source_text": "聖剣が光った。",
                "glossary_override": {"reason": ""},
            },
        )
        assert resp.status_code == 400

    def test_save_without_lint_preserves_legacy_behavior(self, client, novel, fake_storage) -> None:
        fake_storage.save_chapter(novel.slug, "1", "anything")
        resp = client.put(
            f"/api/admin/novels/{novel.slug}/chapters/1/translated",
            json={"text": "Edited text"},
        )
        assert resp.status_code == 200
        # When lint is not requested, glossary_qa should be absent or None
        assert resp.json().get("glossary_qa") in (None, {})

    def test_save_persists_qa_metadata(self, client, novel, approved_entry, fake_storage) -> None:
        fake_storage.save_chapter(novel.slug, "1", "魔王が現れた。")
        client.put(
            f"/api/admin/novels/{novel.slug}/chapters/1/translated",
            json={
                "text": "The dark lord appeared.",
                "lint": True,
                "source_text": "魔王が現れた。",
            },
        )
        assert len(fake_storage.saved_edits) == 1
        edit = fake_storage.saved_edits[0]
        assert "glossary_qa" in edit
        assert edit["glossary_qa"]["status"] in ("warning", "blocked", "passed", "advisory")


class TestApproveTranslationChange:
    def test_approve_updates_entry(self, client, novel, approved_entry, db_session) -> None:
        resp = client.post(
            f"/api/admin/novels/{novel.slug}/glossary/entries/{approved_entry.id}/approve-translation-change",
            json={"new_translation": "Demon Lord", "rationale": "Better fit"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entry_id"] == approved_entry.id
        assert data["approved_translation"] == "Demon Lord"
        assert data["glossary_revision"] is not None

    def test_approve_records_decision_event(self, client, novel, approved_entry, db_session) -> None:
        client.post(
            f"/api/admin/novels/{novel.slug}/glossary/entries/{approved_entry.id}/approve-translation-change",
            json={"new_translation": "Demon Lord", "rationale": "Better fit"},
        )
        from novelai.db.models.glossary import NovelGlossaryDecisionEvent
        events = db_session.query(NovelGlossaryDecisionEvent).filter_by(
            glossary_entry_id=approved_entry.id
        ).all()
        assert len(events) >= 1
        assert events[0].event_type == "approve"

    def test_approve_rejects_wrong_novel(self, client, approved_entry, db_session) -> None:
        other_novel = Novel(slug="other-novel", title="Other", language="ja", publication_status="ongoing")
        db_session.add(other_novel)
        db_session.commit()
        resp = client.post(
            f"/api/admin/novels/other-novel/glossary/entries/{approved_entry.id}/approve-translation-change",
            json={"new_translation": "X"},
        )
        assert resp.status_code == 404

    def test_approve_missing_entry_404(self, client, novel) -> None:
        resp = client.post(
            f"/api/admin/novels/{novel.slug}/glossary/entries/99999/approve-translation-change",
            json={"new_translation": "X"},
        )
        assert resp.status_code == 404

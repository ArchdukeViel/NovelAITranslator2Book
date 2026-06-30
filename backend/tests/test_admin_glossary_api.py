"""Tests for owner/admin glossary API routes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

# Import all DB models so Base.metadata.create_all sees FK targets.
import novelai.db.models.chapter
import novelai.db.models.genre
import novelai.db.models.jobs
import novelai.db.models.system
import novelai.db.models.tag  # noqa: F401
from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.admin_glossary import router as admin_glossary_router
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.dependencies import get_db_session, get_storage
from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.glossary import NovelGlossaryAlias, NovelGlossaryDecisionEvent, NovelGlossaryEntry
from novelai.db.models.novel import Novel
from novelai.db.models.users import User


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=True)
    sess = Session()
    yield sess
    sess.close()


@pytest.fixture()
def chapter_storage():
    return FakeChapterStorage()


@pytest.fixture()
def app(db_session, chapter_storage):
    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
    current: dict = {"user": None}

    def _user_override():
        return current["user"] or SessionUser(user_id=None, email=None, role="guest")

    def _db_override():
        yield db_session
        db_session.commit()

    test_app.dependency_overrides[get_db_session] = _db_override
    test_app.dependency_overrides[get_storage] = lambda: chapter_storage
    test_app.dependency_overrides[get_current_user] = _user_override
    test_app.include_router(auth_router)
    test_app.include_router(admin_glossary_router, prefix="/api/admin")
    test_app.state.current_user = current
    return test_app


@pytest.fixture()
def client(app):
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def owner_client(app, db_session):
    user = User(email="owner@example.com", role="owner")
    db_session.add(user)
    db_session.flush()
    set_user(app, user_id=user.id, role="owner")
    client = TestClient(app, raise_server_exceptions=True)
    token_resp = client.get("/api/auth/csrf")
    client.headers.update({"X-CSRF-Token": token_resp.json()["csrf_token"]})
    yield client
    set_user(app)


def set_user(app: FastAPI, user_id: int | None = None, role: str = "guest") -> None:
    app.state.current_user["user"] = SessionUser(
        user_id=user_id,
        email=f"user{user_id}@test.com" if user_id else None,
        role=role,
    )


class FakeChapterStorage:
    def __init__(self) -> None:
        self.raw: dict[tuple[str, str], dict[str, Any]] = {}
        self.translated: dict[tuple[str, str], dict[str, Any]] = {}

    def add_raw(self, novel_id: str, chapter_id: str, text: str) -> None:
        self.raw[(novel_id, chapter_id)] = {
            "id": chapter_id,
            "text": text,
            "source_key": "kakuyomu",
            "input_adapter_key": "kakuyomu",
        }

    def add_translated(self, novel_id: str, chapter_id: str, text: str) -> None:
        self.translated[(novel_id, chapter_id)] = {
            "id": chapter_id,
            "text": text,
        }

    def list_stored_chapters(self, novel_id: str) -> list[str]:
        chapter_ids = {
            chapter_id
            for stored_novel_id, chapter_id in {*self.raw.keys(), *self.translated.keys()}
            if stored_novel_id == novel_id
        }
        return sorted(chapter_ids)

    def load_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        item = self.raw.get((novel_id, chapter_id))
        return deepcopy(item) if item is not None else None

    def load_translated_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
        item = self.translated.get((novel_id, chapter_id))
        return deepcopy(item) if item is not None else None


def _seed_novel(db_session, slug: str = "glossary-api") -> Novel:
    novel = Novel(slug=slug, title=f"Novel {slug}", language="ja", status="ongoing")
    db_session.add(novel)
    db_session.flush()
    return novel


def _seed_chapter(db_session, novel: Novel, number: int) -> Chapter:
    chapter = Chapter(novel_id=novel.id, chapter_number=number, title=f"Chapter {number}")
    db_session.add(chapter)
    db_session.flush()
    return chapter


def _seed_candidate_chapter_text(chapter_storage: FakeChapterStorage, novel: Novel) -> None:
    chapter_storage.add_raw(novel.slug, "1", "ポコットで会った。ポコットは村です。")
    chapter_storage.add_translated(
        novel.slug,
        "1",
        "Pocott Village welcomed travelers. Pocott Village remained peaceful.",
    )


def _create_entry(owner_client: TestClient, novel_id: int | str, canonical_term: str = "Pocott") -> dict:
    resp = owner_client.post(
        f"/api/admin/novels/{novel_id}/glossary",
        json={
            "canonical_term": canonical_term,
            "term_type": "place",
            "approved_translation": canonical_term,
            "status": "candidate",
        },
    )
    assert resp.status_code == 200
    return resp.json()


def _create_alias(owner_client: TestClient, novel_id: int | str, entry_id: int, alias_text: str = "Pokot") -> dict:
    resp = owner_client.post(
        f"/api/admin/novels/{novel_id}/glossary/entries/{entry_id}/aliases",
        json={"alias_text": alias_text, "alias_type": "banned", "applies_to": "qa"},
    )
    assert resp.status_code == 200
    return resp.json()


def _create_qa_finding(owner_client: TestClient, novel_id: int | str, entry_id: int) -> dict:
    resp = owner_client.post(
        f"/api/admin/novels/{novel_id}/glossary/qa-findings",
        json={
            "glossary_entry_id": entry_id,
            "finding_type": "banned_alias",
            "severity": "warning",
            "matched_text": "Pokot",
            "suggested_text": "Pocott",
        },
    )
    assert resp.status_code == 200
    return resp.json()


def test_guest_and_normal_user_cannot_manage_admin_glossary(client, app, db_session) -> None:
    novel = _seed_novel(db_session)

    guest_resp = client.get(f"/api/admin/novels/{novel.id}/glossary")
    assert guest_resp.status_code == 401

    user = User(email="reader@example.com", role="user")
    db_session.add(user)
    db_session.flush()
    set_user(app, user_id=user.id, role="user")

    user_resp = client.post(
        f"/api/admin/novels/{novel.id}/glossary",
        json={"canonical_term": "Pocott", "term_type": "place"},
    )
    assert user_resp.status_code == 403


def test_owner_unsafe_write_without_csrf_fails(app, db_session) -> None:
    novel = _seed_novel(db_session)
    user = User(email="owner-no-csrf@example.com", role="owner")
    db_session.add(user)
    db_session.flush()
    set_user(app, user_id=user.id, role="owner")
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.post(
        f"/api/admin/novels/{novel.id}/glossary",
        json={"canonical_term": "Pocott", "term_type": "place"},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Invalid CSRF token."


def test_owner_can_create_list_and_update_glossary_entry(owner_client, db_session) -> None:
    novel = _seed_novel(db_session)

    created = _create_entry(owner_client, novel.id)
    list_resp = owner_client.get(f"/api/admin/novels/{novel.id}/glossary")
    update_resp = owner_client.patch(
        f"/api/admin/novels/{novel.id}/glossary/entries/{created['id']}",
        json={"approved_translation": "Pocott Village", "public_visible": True},
    )

    assert list_resp.status_code == 200
    assert [item["canonical_term"] for item in list_resp.json()] == ["Pocott"]
    assert update_resp.status_code == 200
    assert update_resp.json()["approved_translation"] == "Pocott Village"
    assert update_resp.json()["public_visible"] is True


def test_owner_can_use_admin_novel_slug_for_glossary_routes(owner_client, db_session) -> None:
    novel = _seed_novel(db_session, "slug-route-novel")

    created = _create_entry(owner_client, novel.slug, canonical_term="Pocott")
    list_resp = owner_client.get(f"/api/admin/novels/{novel.slug}/glossary")
    qa_resp = owner_client.get(f"/api/admin/novels/{novel.slug}/glossary/qa-findings")
    events_resp = owner_client.get(f"/api/admin/novels/{novel.slug}/glossary/entries/{created['id']}/events")

    assert created["novel_id"] == novel.id
    assert list_resp.status_code == 200
    assert [item["canonical_term"] for item in list_resp.json()] == ["Pocott"]
    assert qa_resp.status_code == 200
    assert qa_resp.json() == []
    assert events_resp.status_code == 200
    assert events_resp.json()[0]["novel_id"] == novel.id


def test_owner_can_preview_glossary_candidate_import_without_writing(
    owner_client,
    db_session,
    chapter_storage,
) -> None:
    novel = _seed_novel(db_session, "candidate-preview")
    _seed_chapter(db_session, novel, 1)
    _seed_candidate_chapter_text(chapter_storage, novel)

    resp = owner_client.post(
        f"/api/admin/novels/{novel.slug}/glossary/candidates/import/preview",
        json={"max_candidates": 1},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["novel_id"] == novel.id
    assert payload["mode"] == "preview"
    assert payload["candidates_found"] == 1
    assert payload["candidates_created"] == 0
    assert payload["candidates"][0]["term"] == "Pocott Village"
    assert payload["candidates"][0]["action"] == "preview"
    assert payload["candidates"][0]["chapter_numbers"] == [1]
    assert payload["candidates"][0]["chapter_refs"] == ["1"]
    assert "welcomed travelers" not in str(payload)
    assert db_session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id).count() == 0


def test_owner_can_apply_glossary_candidate_import_as_reviewing_entries(
    owner_client,
    db_session,
    chapter_storage,
) -> None:
    novel = _seed_novel(db_session, "candidate-apply")
    _seed_chapter(db_session, novel, 1)
    _seed_candidate_chapter_text(chapter_storage, novel)

    resp = owner_client.post(
        f"/api/admin/novels/{novel.id}/glossary/candidates/import/apply",
        json={"max_candidates": 1},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["mode"] == "apply"
    assert payload["candidates_created"] == 1
    assert payload["candidates_merged"] == 0
    assert payload["candidates_skipped"] == 0
    assert payload["candidates"][0]["action"] == "created"
    assert payload["candidates"][0]["notes"] == "Created as a Reviewing candidate from saved chapters."

    entry = db_session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id, canonical_term="Pocott Village").one()
    assert entry.status == "candidate"
    assert entry.enforcement_level == "none"
    assert entry.owner_locked is False
    event = db_session.query(NovelGlossaryDecisionEvent).filter_by(glossary_entry_id=entry.id, event_type="create").one()
    assert event.decision_source == "candidate_import"


def test_candidate_import_is_scoped_to_requested_novel(
    owner_client,
    db_session,
    chapter_storage,
) -> None:
    novel_a = _seed_novel(db_session, "candidate-scope-a")
    novel_b = _seed_novel(db_session, "candidate-scope-b")
    _seed_chapter(db_session, novel_a, 1)
    _seed_chapter(db_session, novel_b, 1)
    _seed_candidate_chapter_text(chapter_storage, novel_a)

    resp = owner_client.post(
        f"/api/admin/novels/{novel_a.id}/glossary/candidates/import/apply",
        json={"max_candidates": 1},
    )

    assert resp.status_code == 200
    assert db_session.query(NovelGlossaryEntry).filter_by(novel_id=novel_a.id).count() == 1
    assert db_session.query(NovelGlossaryEntry).filter_by(novel_id=novel_b.id).count() == 0


def test_candidate_import_request_validation_errors(owner_client, db_session) -> None:
    novel = _seed_novel(db_session, "candidate-validation")

    resp = owner_client.post(
        f"/api/admin/novels/{novel.id}/glossary/candidates/import/preview",
        json={"max_candidates": 0},
    )

    assert resp.status_code == 422
    assert "max_candidates" in str(resp.json()["detail"])


def test_entry_routes_reject_cross_novel_access(owner_client, db_session) -> None:
    novel_a = _seed_novel(db_session, "entry-scope-a")
    novel_b = _seed_novel(db_session, "entry-scope-b")
    entry = _create_entry(owner_client, novel_a.id)

    requests = [
        owner_client.get(f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry['id']}"),
        owner_client.patch(
            f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry['id']}",
            json={"approved_translation": "Wrong Novel"},
        ),
        owner_client.post(
            f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry['id']}/status",
            json={"status": "approved"},
        ),
        owner_client.post(f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry['id']}/lock", json={}),
        owner_client.post(f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry['id']}/unlock", json={}),
        owner_client.post(f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry['id']}/deprecate", json={}),
    ]

    assert [resp.status_code for resp in requests] == [404, 404, 404, 404, 404, 404]
    assert owner_client.get(f"/api/admin/novels/{novel_a.id}/glossary/entries/{entry['id']}").status_code == 200


def test_not_found_behavior_for_missing_novel_entry_alias_and_qa(owner_client, db_session) -> None:
    novel = _seed_novel(db_session, "missing-resources")

    assert owner_client.get("/api/admin/novels/999999/glossary").status_code == 404
    assert owner_client.get(f"/api/admin/novels/{novel.id}/glossary/entries/999999").status_code == 404
    assert (
        owner_client.patch(
            f"/api/admin/novels/{novel.id}/glossary/aliases/999999",
            json={"alias_text": "Missing"},
        ).status_code
        == 404
    )
    assert (
        owner_client.patch(
            f"/api/admin/novels/{novel.id}/glossary/qa-findings/999999/status",
            json={"status": "dismissed"},
        ).status_code
        == 404
    )


def test_alias_add_list_and_deprecate_work(owner_client, db_session) -> None:
    novel = _seed_novel(db_session)
    entry = _create_entry(owner_client, novel.id, "Albert")

    add_resp = owner_client.post(
        f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/aliases",
        json={"alias_text": "Alberto", "alias_type": "banned", "applies_to": "qa"},
    )
    list_resp = owner_client.get(f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/aliases")
    dep_resp = owner_client.post(
        f"/api/admin/novels/{novel.id}/glossary/aliases/{add_resp.json()['id']}/deprecate",
        json={"rationale": "Owner deprecated this variant."},
    )

    assert add_resp.status_code == 200
    assert add_resp.json()["novel_id"] == novel.id
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["alias_text"] == "Alberto"
    assert dep_resp.status_code == 200
    assert dep_resp.json()["alias_type"] == "deprecated"


def test_alias_routes_reject_cross_novel_access(owner_client, db_session) -> None:
    novel_a = _seed_novel(db_session, "alias-scope-a")
    novel_b = _seed_novel(db_session, "alias-scope-b")
    entry = _create_entry(owner_client, novel_a.id, "Albert")
    alias = _create_alias(owner_client, novel_a.id, entry["id"], "Alberto")

    responses = [
        owner_client.get(f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry['id']}/aliases"),
        owner_client.post(
            f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry['id']}/aliases",
            json={"alias_text": "Wrong Novel", "alias_type": "observed"},
        ),
        owner_client.patch(
            f"/api/admin/novels/{novel_b.id}/glossary/aliases/{alias['id']}",
            json={"alias_text": "Wrong Novel"},
        ),
        owner_client.post(f"/api/admin/novels/{novel_b.id}/glossary/aliases/{alias['id']}/deprecate", json={}),
    ]

    assert [resp.status_code for resp in responses] == [404, 404, 404, 404]
    assert db_session.query(NovelGlossaryAlias).filter_by(novel_id=novel_b.id).count() == 0


def test_provenance_add_and_list_treats_source_as_provenance_only(owner_client, db_session) -> None:
    novel = _seed_novel(db_session)
    entry = _create_entry(owner_client, novel.id)

    add_resp = owner_client.post(
        f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/provenance",
        json={
            "source_site": "kakuyomu",
            "source_adapter": "kakuyomu",
            "source_novel_id": "16817330655991571532",
            "observed_translated_term": "Pocott",
            "evidence_ref": "audit:chapter-3",
            "evidence_quality": "mojibake",
        },
    )
    novel_list = owner_client.get(f"/api/admin/novels/{novel.id}/glossary/provenance")
    entry_list = owner_client.get(f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/provenance")

    assert add_resp.status_code == 200
    assert add_resp.json()["novel_id"] == novel.id
    assert add_resp.json()["source_site"] == "kakuyomu"
    assert novel_list.status_code == 200
    assert len(novel_list.json()) == 1
    assert entry_list.status_code == 200
    assert entry_list.json()[0]["source_novel_id"] == "16817330655991571532"
    assert db_session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id).count() == 1


def test_provenance_routes_reject_cross_novel_entry_access(owner_client, db_session) -> None:
    novel_a = _seed_novel(db_session, "provenance-scope-a")
    novel_b = _seed_novel(db_session, "provenance-scope-b")
    entry = _create_entry(owner_client, novel_a.id)

    list_resp = owner_client.get(f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry['id']}/provenance")
    add_resp = owner_client.post(
        f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry['id']}/provenance",
        json={"source_site": "kakuyomu", "source_adapter": "kakuyomu"},
    )
    novel_b_list = owner_client.get(f"/api/admin/novels/{novel_b.id}/glossary/provenance")

    assert list_resp.status_code == 404
    assert add_resp.status_code == 404
    assert novel_b_list.status_code == 200
    assert novel_b_list.json() == []


def test_status_change_creates_decision_event_and_events_are_listed(owner_client, db_session) -> None:
    novel = _seed_novel(db_session)
    entry = _create_entry(owner_client, novel.id, "World Tree")

    status_resp = owner_client.post(
        f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/status",
        json={"status": "approved", "rationale": "Owner approved."},
    )
    events_resp = owner_client.get(f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/events")

    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "approved"
    assert events_resp.status_code == 200
    assert [event["event_type"] for event in events_resp.json()] == ["create", "approve"]
    assert db_session.query(NovelGlossaryDecisionEvent).filter_by(event_type="approve").count() == 1


def test_lock_unlock_deprecate_and_alias_updates_create_decision_events(owner_client, db_session) -> None:
    novel = _seed_novel(db_session, "event-cases")
    entry = _create_entry(owner_client, novel.id, "Order of Knights")
    alias = _create_alias(owner_client, novel.id, entry["id"], "Kingdom Knights")

    owner_client.post(f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/lock", json={})
    owner_client.post(f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/unlock", json={})
    owner_client.patch(
        f"/api/admin/novels/{novel.id}/glossary/aliases/{alias['id']}",
        json={"alias_type": "allowed"},
    )
    owner_client.post(f"/api/admin/novels/{novel.id}/glossary/aliases/{alias['id']}/deprecate", json={})
    owner_client.post(f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/deprecate", json={})

    events = owner_client.get(f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/events").json()
    assert [event["event_type"] for event in events] == [
        "create",
        "alias_change",
        "lock",
        "unlock",
        "alias_change",
        "alias_change",
        "deprecate",
    ]


def test_decision_event_listing_is_scoped_by_novel_and_entry(owner_client, db_session) -> None:
    novel_a = _seed_novel(db_session, "event-scope-a")
    novel_b = _seed_novel(db_session, "event-scope-b")
    entry_a = _create_entry(owner_client, novel_a.id, "Pocott")
    entry_b = _create_entry(owner_client, novel_b.id, "Pocott")

    owner_client.post(
        f"/api/admin/novels/{novel_a.id}/glossary/entries/{entry_a['id']}/status",
        json={"status": "approved"},
    )

    novel_a_events = owner_client.get(f"/api/admin/novels/{novel_a.id}/glossary/events").json()
    novel_b_events = owner_client.get(f"/api/admin/novels/{novel_b.id}/glossary/events").json()
    wrong_entry_events = owner_client.get(
        f"/api/admin/novels/{novel_b.id}/glossary/entries/{entry_a['id']}/events"
    )

    assert [event["novel_id"] for event in novel_a_events] == [novel_a.id, novel_a.id]
    assert [event["novel_id"] for event in novel_b_events] == [novel_b.id]
    assert [event["glossary_entry_id"] for event in novel_b_events] == [entry_b["id"]]
    assert wrong_entry_events.status_code == 404


def test_same_canonical_term_can_exist_in_different_novels(owner_client, db_session) -> None:
    novel_a = _seed_novel(db_session, "term-a")
    novel_b = _seed_novel(db_session, "term-b")

    entry_a = _create_entry(owner_client, novel_a.id, "Pocott")
    entry_b = _create_entry(owner_client, novel_b.id, "Pocott")

    assert entry_a["id"] != entry_b["id"]
    assert owner_client.get(f"/api/admin/novels/{novel_a.id}/glossary").json()[0]["id"] == entry_a["id"]
    assert owner_client.get(f"/api/admin/novels/{novel_b.id}/glossary").json()[0]["id"] == entry_b["id"]


def test_routes_do_not_require_source_site_or_source_novel_id_as_owner(owner_client, db_session) -> None:
    novel = _seed_novel(db_session)

    entry = _create_entry(owner_client, novel.id, "Ori")

    assert entry["novel_id"] == novel.id
    assert entry["canonical_term"] == "Ori"
    assert db_session.query(NovelGlossaryEntry).filter_by(novel_id=novel.id).count() == 1


def test_manual_qa_finding_create_list_and_status_update(owner_client, db_session) -> None:
    novel = _seed_novel(db_session)
    entry = _create_entry(owner_client, novel.id, "House Vanclyft")

    create_resp = owner_client.post(
        f"/api/admin/novels/{novel.id}/glossary/qa-findings",
        json={
            "glossary_entry_id": entry["id"],
            "finding_type": "banned_alias",
            "severity": "warning",
            "matched_text": "Vancroft",
            "suggested_text": "House Vanclyft",
        },
    )
    list_resp = owner_client.get(f"/api/admin/novels/{novel.id}/glossary/qa-findings")
    update_resp = owner_client.patch(
        f"/api/admin/novels/{novel.id}/glossary/qa-findings/{create_resp.json()['id']}/status",
        json={"status": "dismissed", "reviewer_notes": "Manual review complete."},
    )

    assert create_resp.status_code == 200
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["finding_type"] == "banned_alias"
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "dismissed"
    assert update_resp.json()["resolved_at"] is not None


def test_qa_finding_update_rejects_cross_novel_access(owner_client, db_session) -> None:
    novel_a = _seed_novel(db_session, "qa-scope-a")
    novel_b = _seed_novel(db_session, "qa-scope-b")
    entry = _create_entry(owner_client, novel_a.id, "Pocott")
    finding = _create_qa_finding(owner_client, novel_a.id, entry["id"])

    update_resp = owner_client.patch(
        f"/api/admin/novels/{novel_b.id}/glossary/qa-findings/{finding['id']}/status",
        json={"status": "dismissed"},
    )
    novel_b_list = owner_client.get(f"/api/admin/novels/{novel_b.id}/glossary/qa-findings")

    assert update_resp.status_code == 404
    assert novel_b_list.status_code == 200
    assert novel_b_list.json() == []


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"canonical_term": "", "term_type": "place"}, "canonical_term"),
        ({"canonical_term": "Pocott", "term_type": "invalid"}, "term_type"),
        ({"canonical_term": "Pocott", "term_type": "place", "status": "invalid"}, "status"),
    ],
)
def test_entry_create_validation_errors(owner_client, db_session, payload, field) -> None:
    novel = _seed_novel(db_session, f"entry-validation-{field}")

    resp = owner_client.post(f"/api/admin/novels/{novel.id}/glossary", json=payload)

    assert resp.status_code == 422
    assert field in str(resp.json()["detail"])


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"alias_text": "", "alias_type": "observed"}, "alias_text"),
        ({"alias_text": "Pokot", "alias_type": "invalid"}, "alias_type"),
        ({"alias_text": "Pokot", "alias_type": "observed", "applies_to": "chapter"}, "applies_to"),
    ],
)
def test_alias_create_validation_errors(owner_client, db_session, payload, field) -> None:
    novel = _seed_novel(db_session, f"alias-validation-{field}")
    entry = _create_entry(owner_client, novel.id)

    resp = owner_client.post(f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/aliases", json=payload)

    assert resp.status_code == 422
    assert field in str(resp.json()["detail"])


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"source_site": "", "source_adapter": "kakuyomu"}, "source_site"),
        ({"source_site": "kakuyomu", "source_adapter": ""}, "source_adapter"),
        ({"source_site": "kakuyomu", "source_adapter": "kakuyomu", "evidence_quality": "unknown"}, "evidence_quality"),
    ],
)
def test_provenance_validation_errors(owner_client, db_session, payload, field) -> None:
    novel = _seed_novel(db_session, f"provenance-validation-{field}")
    entry = _create_entry(owner_client, novel.id)

    resp = owner_client.post(f"/api/admin/novels/{novel.id}/glossary/entries/{entry['id']}/provenance", json=payload)

    assert resp.status_code == 422
    assert field in str(resp.json()["detail"])


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"finding_type": "unknown", "severity": "warning"}, "finding_type"),
        ({"finding_type": "banned_alias", "severity": "none"}, "severity"),
        ({"finding_type": "banned_alias", "severity": "warning", "status": "closed"}, "status"),
        ({"finding_type": "banned_alias", "severity": "warning", "matched_text": ""}, "matched_text"),
    ],
)
def test_qa_finding_validation_errors(owner_client, db_session, payload, field) -> None:
    novel = _seed_novel(db_session, f"qa-validation-{field}")

    resp = owner_client.post(f"/api/admin/novels/{novel.id}/glossary/qa-findings", json=payload)

    assert resp.status_code == 422
    assert field in str(resp.json()["detail"])


def test_qa_finding_status_validation_error(owner_client, db_session) -> None:
    novel = _seed_novel(db_session, "qa-status-validation")
    entry = _create_entry(owner_client, novel.id)
    finding = _create_qa_finding(owner_client, novel.id, entry["id"])

    resp = owner_client.patch(
        f"/api/admin/novels/{novel.id}/glossary/qa-findings/{finding['id']}/status",
        json={"status": "closed"},
    )

    assert resp.status_code == 422
    assert "status" in str(resp.json()["detail"])

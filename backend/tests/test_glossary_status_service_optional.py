"""Optional property coverage for glossary status transitions."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.glossary import NovelGlossaryDecisionEvent
from novelai.db.models.novel import Novel
from novelai.services.glossary_status_service import GlossaryStatusService


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)


def _novel(session, prefix: str = "gs") -> Novel:
    slug = f"{prefix}-{uuid4().hex}"
    novel = Novel(slug=slug, title="Glossary Status", language="ja", status="ongoing")
    session.add(novel)
    session.flush()
    return novel


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None)
@given(st.integers(min_value=0, max_value=1_000))
def test_glossary_ready_transition_increments_revision(session, revision: int) -> None:
    novel = _novel(session, "ready-transition")
    novel.glossary_revision = revision
    session.commit()

    updated = GlossaryStatusService(session).transition_status(
        novel.slug,
        target_status="glossary_ready",
        actor_user_id=17,
    )

    assert updated.glossary_revision == revision + 1


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None)
@given(st.integers(min_value=0, max_value=1_000))
def test_glossary_skipped_transition_preserves_revision(session, revision: int) -> None:
    novel = _novel(session, "skipped-transition")
    novel.glossary_revision = revision
    session.commit()

    updated = GlossaryStatusService(session).transition_status(
        novel.slug,
        target_status="glossary_skipped",
        actor_user_id=17,
    )

    assert updated.glossary_revision == revision


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], database=None)
@given(st.sampled_from(["glossary_pending", "glossary_ready", "glossary_skipped"]))
def test_every_status_transition_writes_decision_event(session, target_status: str) -> None:
    novel = _novel(session, f"event-{target_status}")
    novel.glossary_status = "glossary_pending"
    session.commit()

    updated = GlossaryStatusService(session).transition_status(
        novel.slug,
        target_status=target_status,
        actor_user_id=99,
    )

    event = session.query(NovelGlossaryDecisionEvent).filter_by(novel_id=updated.id).order_by(NovelGlossaryDecisionEvent.id.desc()).first()
    assert event is not None
    assert event.actor_user_id == 99
    assert json.loads(event.old_value_json) == {"glossary_status": "glossary_pending"}
    assert json.loads(event.new_value_json) == {"glossary_status": target_status}
    assert event.created_at is not None

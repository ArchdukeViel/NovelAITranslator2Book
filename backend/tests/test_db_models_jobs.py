"""Tests for CrawlJob, TranslationJob, and ProviderRequest ORM models."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.jobs import CrawlJob, ProviderRequest, TranslationJob
from novelai.db.models.novel import Novel

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
def novel(session):
    n = Novel(slug="test-novel", title="Test Novel", language="ja", publication_status="ongoing")
    session.add(n)
    session.commit()
    return n


@pytest.fixture()
def chapter(session, novel):
    c = Chapter(novel_id=novel.id, chapter_number=1, title="Chapter 1")
    session.add(c)
    session.commit()
    return c


class TestCrawlJob:
    def test_create_crawl_job(self, session, novel) -> None:
        job = CrawlJob(novel_id=novel.id, source_url="https://example.com", status="pending")
        session.add(job)
        session.commit()
        result = session.query(CrawlJob).filter_by(novel_id=novel.id).one()
        assert result.status == "pending"
        assert result.id is not None

    def test_default_status_pending(self, session) -> None:
        job = CrawlJob()
        session.add(job)
        session.commit()
        assert job.status == "pending"

    def test_status_update(self, session) -> None:
        job = CrawlJob(status="pending")
        session.add(job)
        session.commit()
        job.status = "completed"
        session.commit()
        result = session.query(CrawlJob).filter_by(id=job.id).one()
        assert result.status == "completed"

    def test_error_message_nullable(self, session) -> None:
        job = CrawlJob(status="failed", error_message="Network error")
        session.add(job)
        session.commit()
        assert job.error_message == "Network error"

    def test_repr(self, session) -> None:
        job = CrawlJob(status="running")
        session.add(job)
        session.commit()
        assert "running" in repr(job)


class TestTranslationJob:
    def test_create_translation_job(self, session, novel, chapter) -> None:
        job = TranslationJob(
            novel_id=novel.id,
            chapter_id=chapter.id,
            provider_key="gemini",
            provider_model="gemini-2.5-flash",
            status="pending",
        )
        session.add(job)
        session.commit()
        result = session.query(TranslationJob).filter_by(novel_id=novel.id).one()
        assert result.provider_key == "gemini"
        assert result.status == "pending"

    def test_default_status_pending(self, session) -> None:
        job = TranslationJob()
        session.add(job)
        session.commit()
        assert job.status == "pending"

    def test_token_and_cost_fields(self, session) -> None:
        job = TranslationJob(
            status="completed",
            token_input=1000,
            token_output=800,
            estimated_cost=0.0018,
        )
        session.add(job)
        session.commit()
        result = session.query(TranslationJob).filter_by(id=job.id).one()
        assert result.token_input == 1000
        assert result.token_output == 800
        assert result.estimated_cost == pytest.approx(0.0018)

    def test_repr(self, session) -> None:
        job = TranslationJob(status="running")
        session.add(job)
        session.commit()
        assert "running" in repr(job)


class TestProviderRequest:
    def test_create_provider_request(self, session) -> None:
        job = TranslationJob(status="running")
        session.add(job)
        session.commit()
        req = ProviderRequest(
            job_id=job.id,
            provider_key="gemini",
            provider_model="gemini-2.5-flash",
            input_tokens=500,
            output_tokens=400,
            latency_ms=1200,
            status="success",
        )
        session.add(req)
        session.commit()
        result = session.query(ProviderRequest).filter_by(job_id=job.id).one()
        assert result.provider_key == "gemini"
        assert result.status == "success"

    def test_cascade_delete_with_job(self, session) -> None:
        job = TranslationJob(status="completed")
        session.add(job)
        session.commit()
        req = ProviderRequest(job_id=job.id, status="success")
        session.add(req)
        session.commit()
        req_id = req.id
        session.delete(job)
        session.commit()
        assert session.query(ProviderRequest).filter_by(id=req_id).one_or_none() is None

    def test_no_secret_fields(self) -> None:
        """ProviderRequest must not have API key or auth header columns."""
        cols = {c.name for c in ProviderRequest.__table__.columns}
        forbidden = {"api_key", "auth_header", "authorization", "secret", "token"}
        assert not cols & forbidden, f"Forbidden columns found: {cols & forbidden}"

    def test_repr(self, session) -> None:
        req = ProviderRequest(provider_key="openai", status="success")
        session.add(req)
        session.commit()
        assert "openai" in repr(req)
        assert "success" in repr(req)

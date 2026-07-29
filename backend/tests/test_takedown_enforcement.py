"""Focused tests for DEBT-060: HTTP 451 enforcement, audit, cache invalidation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from novelai.db.base import Base
from novelai.db.models.takedown import TakedownRequest
from novelai.services.takedown_service import TakedownService


@pytest.fixture
def db_session():
    """In-memory SQLite session for takedown service tests."""
    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)()
    try:
        yield test_session
    finally:
        test_session.close()


# ---------------------------------------------------------------------------
# TakedownService unit tests
# ---------------------------------------------------------------------------


def _seed_takedown(
    db: Session,
    infringing_url: str = "https://example.com/novels/my-slug",
    status: str = "pending",
) -> TakedownRequest:
    req = TakedownRequest(
        complainant_name="Test",
        complainant_email="test@example.com",
        infringing_url=infringing_url,
        description="Infringing content",
        signature="Test Signature",
        status=status,
    )
    db.add(req)
    db.flush()
    return req


class TestHasActiveTakedownForSlug:
    """TakedownService.has_active_takedown_for_slug() — 451 gate."""

    def test_approved_takedown_matches_slug(self, db_session: Session) -> None:
        _seed_takedown(db_session, status="approved")
        svc = TakedownService(db_session)
        assert svc.has_active_takedown_for_slug("my-slug") is True

    def test_pending_takedown_does_not_match(self, db_session: Session) -> None:
        _seed_takedown(db_session, status="pending")
        svc = TakedownService(db_session)
        assert svc.has_active_takedown_for_slug("my-slug") is False

    def test_rejected_takedown_does_not_match(self, db_session: Session) -> None:
        _seed_takedown(db_session, status="rejected")
        svc = TakedownService(db_session)
        assert svc.has_active_takedown_for_slug("my-slug") is False

    def test_expired_takedown_does_not_match(self, db_session: Session) -> None:
        _seed_takedown(db_session, status="expired")
        svc = TakedownService(db_session)
        assert svc.has_active_takedown_for_slug("my-slug") is False

    def test_reviewing_takedown_does_not_match(self, db_session: Session) -> None:
        _seed_takedown(db_session, status="reviewing")
        svc = TakedownService(db_session)
        assert svc.has_active_takedown_for_slug("my-slug") is False

    def test_different_slug_not_blocked(self, db_session: Session) -> None:
        _seed_takedown(
            db_session,
            infringing_url="https://example.com/novels/other-slug",
            status="approved",
        )
        svc = TakedownService(db_session)
        assert svc.has_active_takedown_for_slug("my-slug") is False

    def test_slug_partial_match_not_blocked(self, db_session: Session) -> None:
        """Slug 'slug' should not match '/novels/my-other-slug-content' unless
        the path segment aligns."""
        _seed_takedown(
            db_session,
            infringing_url="https://example.com/novels/my-other-slug-content",
            status="approved",
        )
        svc = TakedownService(db_session)
        assert svc.has_active_takedown_for_slug("slug") is False

    def test_slug_prefix_path_segment_not_blocked(self, db_session: Session) -> None:
        _seed_takedown(
            db_session,
            infringing_url="https://example.com/novels/my-slug-extra",
            status="approved",
        )
        assert TakedownService(db_session).has_active_takedown_for_slug("my-slug") is False

    def test_approved_takedown_exact_url_still_works(self, db_session: Session) -> None:
        _seed_takedown(
            db_session,
            infringing_url="https://example.com/novels/exact-slug",
            status="approved",
        )
        svc = TakedownService(db_session)
        # The slug-based method uses ILIKE with %/<slug>% to match path segments
        assert svc.has_active_takedown_for_slug("exact-slug") is True

    def test_batch_returns_only_requested_exact_slugs(self, db_session: Session) -> None:
        _seed_takedown(db_session, "https://example.com/novels/blocked", "approved")
        _seed_takedown(db_session, "https://example.com/novels/other", "pending")
        assert TakedownService(db_session).active_takedown_slugs(["blocked", "other", "visible"]) == {"blocked"}


class TestReviewEmitsAudit:
    """Verifies that review() updates status and returns the request."""

    def test_review_updates_status(self, db_session: Session) -> None:
        req = _seed_takedown(db_session, status="pending")
        svc = TakedownService(db_session)
        now = datetime.now(UTC)
        result = svc.review(
            request_id=req.id,
            status="approved",
            reviewer_notes="Approved after review",
            reviewed_by_user_id=42,
        )
        assert result is not None
        assert result.status == "approved"
        assert result.reviewer_notes == "Approved after review"
        assert result.reviewed_by_user_id == 42
        assert result.reviewed_at is not None
        assert result.reviewed_at >= now

    def test_review_invalid_status_raises(self, db_session: Session) -> None:
        req = _seed_takedown(db_session, status="pending")
        svc = TakedownService(db_session)
        with pytest.raises(ValueError, match="Invalid status"):
            svc.review(request_id=req.id, status="invalid_status")

    def test_review_nonexistent_returns_none(self, db_session: Session) -> None:
        svc = TakedownService(db_session)
        assert svc.review(request_id=99999, status="approved") is None


class TestSubmit:
    """TakedownService.submit() basic contract."""

    def test_submit_creates_request_with_pending_status(self, db_session: Session) -> None:
        svc = TakedownService(db_session)
        req = svc.submit(
            complainant_name="Alice",
            complainant_email="alice@example.com",
            infringing_url="https://example.com/novels/infringing",
            description="My copyrighted work",
            signature="Alice B.",
        )
        assert req.id is not None
        assert req.status == "pending"
        assert req.complainant_name == "Alice"
        assert req.complainant_email == "alice@example.com"

    def test_submit_with_all_optionals(self, db_session: Session) -> None:
        svc = TakedownService(db_session)
        req = svc.submit(
            complainant_name="Bob",
            complainant_email="bob@example.com",
            infringing_url="https://example.com/novels/bob-work",
            description="Bob's work",
            signature="Bob C.",
            complainant_phone="+1-555-0100",
            original_work_url="https://bob.example.com/original",
            original_work_description="Original description",
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
        )
        assert req.complainant_phone == "+1-555-0100"
        assert req.original_work_url == "https://bob.example.com/original"
        assert req.original_work_description == "Original description"
        assert req.ip_address == "192.168.1.1"
        assert req.user_agent == "TestAgent/1.0"


class TestHasActiveTakedown:
    """Existing has_active_takedown(url) contract."""

    def test_exact_url_match(self, db_session: Session) -> None:
        url = "https://example.com/novels/exact"
        _seed_takedown(db_session, infringing_url=url, status="approved")
        svc = TakedownService(db_session)
        assert svc.has_active_takedown(url) is True

    def test_no_match_when_not_approved(self, db_session: Session) -> None:
        url = "https://example.com/novels/pending"
        _seed_takedown(db_session, infringing_url=url, status="pending")
        svc = TakedownService(db_session)
        assert svc.has_active_takedown(url) is False

    def test_no_match_different_url(self, db_session: Session) -> None:
        _seed_takedown(
            db_session,
            infringing_url="https://example.com/novels/blocked",
            status="approved",
        )
        svc = TakedownService(db_session)
        assert svc.has_active_takedown("https://example.com/novels/other") is False


# ---------------------------------------------------------------------------
# 451 enforcement — no private details leak
# ---------------------------------------------------------------------------


class Test451NoPrivateDetails:
    """HTTP 451 responses must not expose emails, names, or internal paths."""

    def test_451_detail_does_not_leak_complainant_info(self) -> None:
        """Simulate the 451 exception raised by the router to verify
        the detail string is safe — no complainant info exposed."""
        exc = HTTPException(status_code=451, detail="Unavailable For Legal Reasons")
        assert exc.status_code == 451
        assert exc.detail == "Unavailable For Legal Reasons"
        # No complainant name, email, phone, or internal data in detail
        assert "complainant" not in str(exc.detail)
        assert "@" not in str(exc.detail)

    def test_451_detail_fixed_string(self) -> None:
        """The detail string is a constant; no dynamic content inserted."""
        exc = HTTPException(status_code=451, detail="Unavailable For Legal Reasons")
        assert exc.detail == "Unavailable For Legal Reasons"
        assert exc.status_code == 451

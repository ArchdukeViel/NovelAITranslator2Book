from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from novelai.db.base import Base
from novelai.db.models.novel import Novel
from novelai.db.models.users import NovelRequest, User
from novelai.services.novel_request_service import NovelRequestService


def test_request_listing_joins_novel_slugs_in_one_query() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _record_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    try:
        with Session(engine) as session:
            user = User(email="requester@example.com", role="user")
            novel = Novel(slug="requested-novel", title="Requested", language="ja", publication_status="ongoing")
            approved = Novel(slug="approved-novel", title="Approved", language="ja", publication_status="ongoing")
            session.add_all([user, novel, approved])
            session.flush()
            request = NovelRequest(
                user_id=user.id,
                request_type="novel",
                novel_id=novel.id,
                approved_novel_id=approved.id,
                status="pending",
            )
            session.add(request)
            session.commit()
            statements.clear()

            service = NovelRequestService(db_session=session)
            listed = service.list_requests()

            assert len(listed) == 1
            assert listed[0]["slug"] == "requested-novel"
            assert listed[0]["approved_slug"] == "approved-novel"
            assert len(statements) == 1

            updated = service.update_request_status(str(request.id), " APPROVED ", approved_novel_id=approved.id)
            assert updated["status"] == "approved"
            assert updated["approved_slug"] == "approved-novel"
    finally:
        Base.metadata.drop_all(engine)

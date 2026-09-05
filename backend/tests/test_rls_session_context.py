"""Test verifying RLS session context propagation in session_scope.

Reference: REQ-016 / F-16 (postgres-database-hardening-and-security).
Ensures SET LOCAL app.current_user_id is injected in transaction context.
"""

from unittest.mock import MagicMock

from novelai.db.engine import session_scope


def test_session_scope_sets_rls_current_user_id(monkeypatch) -> None:
    mock_session = MagicMock()
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_session.get_bind.return_value = mock_bind

    monkeypatch.setattr("novelai.db.engine.get_sessionmaker", lambda url: lambda: mock_session)

    user_id = "11111111-2222-3333-4444-555555555555"
    with session_scope(current_user_id=user_id) as s:
        assert s is mock_session

    # Verify RLS session context was executed
    mock_session.execute.assert_called_once()
    call_args = mock_session.execute.call_args
    sql_text = str(call_args[0][0])
    assert "set_config('app.current_user_id'" in sql_text or "SET LOCAL app.current_user_id" in sql_text
    assert call_args[0][1] == {"uid": user_id}

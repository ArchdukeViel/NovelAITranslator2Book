from __future__ import annotations

from novelai.config.settings import session_cookie_secure, settings


def test_staging_and_production_force_secure_session_cookies(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", False)

    monkeypatch.setattr(settings, "ENV", "staging")
    assert session_cookie_secure() is True

    monkeypatch.setattr(settings, "ENV", "production")
    assert session_cookie_secure() is True

    monkeypatch.setattr(settings, "ENV", "development")
    assert session_cookie_secure() is False

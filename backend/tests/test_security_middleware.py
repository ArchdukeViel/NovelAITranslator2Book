"""Tests for security headers, trusted proxy IP resolution, and allowed hosts.

Does NOT test the production config validator (see test_production_config.py).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from novelai.api.middleware.security import (
    SecurityHeadersMiddleware,
    get_client_ip,
    is_allowed_host,
)
from novelai.config.settings import settings

# ── helpers ──────────────────────────────────────────────────────────

def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/hello")
    async def hello() -> dict[str, str]:
        return {"message": "ok"}

    app.add_middleware(SecurityHeadersMiddleware)
    return app


# ── SecurityHeadersMiddleware ────────────────────────────────────────

class TestSecurityHeadersMiddleware:
    def test_x_content_type_options(self):
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/hello")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_referrer_policy(self):
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/hello")
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_x_frame_options(self):
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/hello")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_hsts_included_when_configured(self):
        original = settings.HSTS_MAX_AGE_SECONDS
        try:
            settings.HSTS_MAX_AGE_SECONDS = 31536000
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/hello")
            hsts = resp.headers.get("Strict-Transport-Security", "")
            assert "max-age=31536000" in hsts
            assert "includeSubDomains" in hsts
        finally:
            settings.HSTS_MAX_AGE_SECONDS = original

    def test_hsts_omitted_when_zero(self):
        original = settings.HSTS_MAX_AGE_SECONDS
        try:
            settings.HSTS_MAX_AGE_SECONDS = 0
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/hello")
            assert "Strict-Transport-Security" not in resp.headers
        finally:
            settings.HSTS_MAX_AGE_SECONDS = original

    def test_headers_omitted_when_disabled(self):
        original_enabled = settings.SECURITY_HEADERS_ENABLED
        original_hsts = settings.HSTS_MAX_AGE_SECONDS
        try:
            settings.SECURITY_HEADERS_ENABLED = False
            settings.HSTS_MAX_AGE_SECONDS = 31536000
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/hello")
            assert "X-Content-Type-Options" not in resp.headers
            assert "Referrer-Policy" not in resp.headers
            assert "X-Frame-Options" not in resp.headers
            assert "Strict-Transport-Security" not in resp.headers
        finally:
            settings.SECURITY_HEADERS_ENABLED = original_enabled
            settings.HSTS_MAX_AGE_SECONDS = original_hsts

    def test_health_alias_endpoints_get_headers(self):
        original = settings.HSTS_MAX_AGE_SECONDS
        try:
            settings.HSTS_MAX_AGE_SECONDS = 0
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/hello")
            assert resp.status_code == 200
        finally:
            settings.HSTS_MAX_AGE_SECONDS = original


# ── get_client_ip ────────────────────────────────────────────────────

def _make_request(client_addr: str | None = None, xff: str | None = None) -> Request:
    """Build a minimal Starlette Request with mocked ASGI scope."""
    scope: dict[str, object] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": (client_addr, 54321) if client_addr else None,
        "server": ("test", 80),
        "scheme": "http",
        "query_string": b"",
        "root_path": "",
    }
    if xff:
        assert isinstance(scope["headers"], list)
        scope["headers"].append((b"x-forwarded-for", xff.encode()))
    return Request(scope=scope)  # type: ignore[arg-type]


class TestGetClientIp:
    def test_no_proxy_config_returns_direct_ip(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", [])
        req = _make_request(client_addr="1.2.3.4")
        assert get_client_ip(req) == "1.2.3.4"

    def test_xff_respected_from_trusted_proxy(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", ["10.0.0.0/8"])
        req = _make_request(client_addr="10.0.0.1", xff="5.6.7.8")
        assert get_client_ip(req) == "5.6.7.8"

    def test_xff_ignored_from_untrusted_source(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", ["10.0.0.0/8"])
        req = _make_request(client_addr="9.9.9.9", xff="5.6.7.8")
        assert get_client_ip(req) == "9.9.9.9"

    def test_first_xff_ip_used_when_multiple(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", ["10.0.0.0/8"])
        req = _make_request(client_addr="10.0.0.1", xff="1.2.3.4, 5.6.7.8")
        assert get_client_ip(req) == "1.2.3.4"

    def test_no_client_returns_unknown(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", [])
        req = _make_request(client_addr=None)
        assert get_client_ip(req) == "unknown"

    def test_trusted_proxy_no_xff_returns_direct(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", ["10.0.0.0/8"])
        req = _make_request(client_addr="10.0.0.1")
        assert get_client_ip(req) == "10.0.0.1"


# ── is_allowed_host ──────────────────────────────────────────────────

class TestIsAllowedHost:
    def test_empty_list_allows_all(self, monkeypatch):
        monkeypatch.setattr(settings, "ALLOWED_HOSTS", [])
        assert is_allowed_host("evil.com") is True

    def test_allowed_host_passes(self, monkeypatch):
        monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["example.com", "api.example.com"])
        assert is_allowed_host("example.com") is True

    def test_disallowed_host_blocked(self, monkeypatch):
        monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["example.com"])
        assert is_allowed_host("evil.com") is False

    def test_port_stripped(self, monkeypatch):
        monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["example.com"])
        assert is_allowed_host("example.com:8080") is True

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["Example.COM"])
        assert is_allowed_host("example.com") is True

    def test_none_host_blocked(self, monkeypatch):
        monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["example.com"])
        assert is_allowed_host(None) is False

"""Tests for security headers, trusted proxy IP resolution, and allowed hosts.

Does NOT test the production config validator (see test_production_config.py).
"""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from novelai.api.app import create_app
from novelai.api.middleware.security import (
    RequestBodyEnforcementMiddleware,
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


def _make_body_app() -> FastAPI:
    app = FastAPI()

    @app.post("/api/auth/check")
    async def auth_check(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.post("/api/items")
    async def items(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.delete("/api/items")
    async def delete_item(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.post("/api/public/analytics/events")
    async def analytics(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.post("/outside")
    async def outside(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    app.add_middleware(RequestBodyEnforcementMiddleware)
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


class TestRequestBodyEnforcementMiddleware:
    def test_oversize_response_keeps_security_headers(self, monkeypatch):
        monkeypatch.setattr(settings, "WEB_MAX_JSON_BODY_BYTES", 4)
        app = _make_body_app()
        app.add_middleware(SecurityHeadersMiddleware)
        secret = "do-not-echo"
        with TestClient(app) as client:
            response = client.post(
                "/api/items",
                content=secret,
                headers={"content-type": "application/json"},
            )
        assert response.status_code == 413
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert secret not in response.text

    def test_limit_classes_and_body_replay(self, monkeypatch):
        monkeypatch.setattr(settings, "WEB_MAX_AUTH_BODY_BYTES", 8)
        monkeypatch.setattr(settings, "WEB_MAX_JSON_BODY_BYTES", 12)
        monkeypatch.setattr(settings, "ANALYTICS_INGEST_MAX_BODY_BYTES", 10)
        with TestClient(_make_body_app()) as client:
            assert client.post(
                "/api/auth/check", content=b"12345678", headers={"content-type": "application/json"}
            ).json() == {"size": 8}
            assert (
                client.post(
                    "/api/auth/check", content=b"123456789", headers={"content-type": "application/json"}
                ).status_code
                == 413
            )
            assert (
                client.post(
                    "/api/items", content=b"123456789012", headers={"content-type": "application/json"}
                ).status_code
                == 200
            )
            assert (
                client.post(
                    "/api/items", content=b"1234567890123", headers={"content-type": "application/json"}
                ).status_code
                == 413
            )
            assert (
                client.post(
                    "/api/public/analytics/events", content=b"12345678901", headers={"content-type": "application/json"}
                ).status_code
                == 413
            )

    def test_json_media_types(self):
        with TestClient(_make_body_app()) as client:
            for content_type in (
                "application/json",
                "application/json; charset=utf-8",
                "application/problem+json",
            ):
                assert (
                    client.post("/api/items", content=b"{}", headers={"content-type": content_type}).status_code == 200
                )

    def test_wrong_or_missing_content_type_rejected_without_echo(self):
        secret = b"do-not-echo"
        with TestClient(_make_body_app()) as client:
            for headers in ({"content-type": "text/plain"}, {}):
                response = client.post("/api/items", content=secret, headers=headers)
                assert response.status_code == 415
                assert secret.decode() not in response.text

    def test_empty_body_without_content_type_is_allowed(self):
        with TestClient(_make_body_app()) as client:
            response = client.post("/api/items", content=b"")
        assert response.status_code == 200
        assert response.json() == {"size": 0}

    def test_non_api_path_is_unaffected(self, monkeypatch):
        monkeypatch.setattr(settings, "WEB_MAX_JSON_BODY_BYTES", 1)
        with TestClient(_make_body_app()) as client:
            response = client.post("/outside", content=b"plain text", headers={"content-type": "text/plain"})
        assert response.status_code == 200
        assert response.json() == {"size": 10}

    def test_non_json_api_method_still_has_size_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "WEB_MAX_JSON_BODY_BYTES", 4)
        with TestClient(_make_body_app()) as client:
            allowed = client.request("DELETE", "/api/items", content=b"1234")
            rejected = client.request("DELETE", "/api/items", content=b"12345")
        assert allowed.status_code == 200
        assert rejected.status_code == 413

    def test_declared_oversize_rejected_before_receive_or_app(self, monkeypatch):
        monkeypatch.setattr(settings, "WEB_MAX_JSON_BODY_BYTES", 4)
        app_called = False
        receive_called = False
        sent: list[dict] = []

        async def app(scope, receive, send):
            nonlocal app_called
            app_called = True

        async def receive():
            nonlocal receive_called
            receive_called = True
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/items",
            "headers": [(b"content-length", b"5"), (b"content-type", b"application/json")],
        }
        asyncio.run(RequestBodyEnforcementMiddleware(app)(scope, receive, send))
        assert app_called is False
        assert receive_called is False
        assert sent[0]["status"] == 413

    def test_actual_stream_size_defeats_false_content_length(self, monkeypatch):
        monkeypatch.setattr(settings, "WEB_MAX_JSON_BODY_BYTES", 4)
        messages = iter(
            (
                {"type": "http.request", "body": b"123", "more_body": True},
                {"type": "http.request", "body": b"45", "more_body": False},
            )
        )
        sent: list[dict] = []
        app_called = False

        async def app(scope, receive, send):
            nonlocal app_called
            app_called = True

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/items",
            "headers": [(b"content-length", b"1"), (b"content-type", b"application/json")],
        }
        asyncio.run(RequestBodyEnforcementMiddleware(app)(scope, receive, send))
        assert app_called is False
        assert sent[0]["status"] == 413
        assert "12345" not in json.dumps(sent, default=str)

    def test_duplicate_content_type_is_rejected(self):
        async def app(scope, receive, send):
            raise AssertionError("duplicate content type must not reach app")

        messages = iter(({"type": "http.request", "body": b"{}", "more_body": False},))
        sent: list[dict] = []

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/items",
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-type", b"text/plain"),
            ],
        }
        asyncio.run(RequestBodyEnforcementMiddleware(app)(scope, receive, send))
        assert sent[0]["status"] == 415


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


class TestHostedAppSecurity:
    def test_create_app_enforces_configured_allowed_hosts(self, monkeypatch):
        monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["preview.example"])
        app = create_app()

        with TestClient(app, base_url="https://preview.example") as client:
            assert client.get("/health/live").status_code == 200
            assert client.get("/health/live", headers={"Host": "evil.example"}).status_code == 400

    def test_preview_can_force_secure_session_cookie(self, monkeypatch):
        monkeypatch.setattr(settings, "ENV", "preview")
        monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", True)
        monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["preview.example"])
        app = create_app()

        with TestClient(app, base_url="https://preview.example") as client:
            response = client.get("/api/auth/csrf")

        assert response.status_code == 200
        assert "secure" in response.headers["set-cookie"].lower()

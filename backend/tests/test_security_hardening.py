from __future__ import annotations

import hashlib
import logging
import shutil
import socket
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from novelai.api.error_handlers import add_error_handlers
from novelai.core.errors import ProviderError, ProviderErrorCode, SourceError
from novelai.core.security import redact_secret_text, redact_sensitive
from novelai.infrastructure.http.client import (
    _PinnedAsyncNetworkBackend,
    create_async_client,
    validate_safe_url,
)
from novelai.logging_config import SimpleFormatter, StructuredFormatter
from novelai.services.admin_service import AdminService
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.storage.service import StorageService


@pytest.fixture
def workspace_tmp_path(request: pytest.FixtureRequest) -> Path:
    digest = hashlib.sha256(request.node.nodeid.encode("utf-8")).hexdigest()[:12]
    base = Path("backend/tests/.tmp/security_hardening") / digest
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    return base


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/novel",
        "http://localhost/novel",
        "http://localhost.localdomain/novel",
        "http://127.0.0.1/novel",
        "http://0.0.0.0/novel",
        "http://[::1]/novel",
        "http://10.0.0.1/novel",
        "http://172.16.0.1/novel",
        "http://192.168.1.1/novel",
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal/computeMetadata/v1/",
        "https://user:secret@example.com/novel",
    ],
)
def test_validate_safe_url_rejects_private_or_secret_bearing_urls(url: str) -> None:
    with pytest.raises(SourceError):
        validate_safe_url(url)


def test_validate_safe_url_allows_http_public_hostname_when_resolution_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import socket

    def raise_gaierror(*_args: Any, **_kwargs: Any) -> None:
        raise socket.gaierror()

    monkeypatch.setattr(socket, "getaddrinfo", raise_gaierror)

    assert validate_safe_url("https://example.invalid/novel") == "https://example.invalid/novel"


@pytest.mark.asyncio
async def test_pinned_transport_dials_only_the_validated_public_address(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []

    def resolve_public(*_args: Any, **_kwargs: Any) -> list[tuple[Any, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 0))]

    class Delegate:
        async def connect_tcp(self, host: str, port: int, **_kwargs: Any) -> str:
            calls.append((host, port))
            return "stream"

    monkeypatch.setattr(socket, "getaddrinfo", resolve_public)

    stream = await _PinnedAsyncNetworkBackend(Delegate()).connect_tcp("example.com", 443)

    assert stream == "stream"
    assert calls == [("93.184.216.34", 443)]


@pytest.mark.asyncio
async def test_pinned_transport_rejects_private_resolution_before_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def resolve_private(*_args: Any, **_kwargs: Any) -> list[tuple[Any, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 0))]

    class Delegate:
        async def connect_tcp(self, host: str, port: int, **_kwargs: Any) -> str:
            calls.append(host)
            return "stream"

    monkeypatch.setattr(socket, "getaddrinfo", resolve_private)

    with pytest.raises(SourceError, match="private/reserved"):
        await _PinnedAsyncNetworkBackend(Delegate()).connect_tcp("example.com", 443)

    assert calls == []


@pytest.mark.asyncio
async def test_default_async_client_uses_pinned_transport() -> None:
    client = create_async_client()
    try:
        assert isinstance(client._transport, httpx.AsyncHTTPTransport)
        pool = client._transport._pool
        assert isinstance(pool._network_backend, _PinnedAsyncNetworkBackend)
    finally:
        await client.aclose()


@pytest.mark.parametrize("novel_id", ["../escape", "..%2Fescape", r"C:\secret", r"\\server\share"])
def test_storage_rejects_path_like_novel_ids(workspace_tmp_path: Path, novel_id: str) -> None:
    storage = StorageService(workspace_tmp_path)

    with pytest.raises(ValueError):
        storage.save_metadata(novel_id, {"title": "Unsafe"})


@pytest.mark.parametrize("chapter_id", ["../escape", "..%2Fescape", r"C:\secret", r"\\server\share"])
def test_storage_rejects_path_like_chapter_ids(workspace_tmp_path: Path, chapter_id: str) -> None:
    storage = StorageService(workspace_tmp_path)
    storage.save_metadata("novel1", {"title": "Safe"})

    with pytest.raises(ValueError):
        storage.save_chapter("novel1", chapter_id, "chapter text")


def test_storage_rejects_asset_paths_that_escape_novel_root(workspace_tmp_path: Path) -> None:
    storage = StorageService(workspace_tmp_path)
    storage.save_metadata("novel1", {"title": "Safe"})

    with pytest.raises(ValueError):
        storage.resolve_asset_path("novel1", "../outside.txt")


def _security_test_client() -> TestClient:
    app = FastAPI()
    add_error_handlers(app)

    @app.get("/http-secret")
    async def http_secret() -> None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BAD_REQUEST",
                "message": "bad api_key=SECRET_VALUE",
                "details": {
                    "api_key": "SECRET_VALUE",
                    "headers": {"Authorization": "Bearer SECRET_VALUE"},
                },
            },
        )

    @app.get("/provider-secret")
    async def provider_secret() -> None:
        raise ProviderError(
            ProviderErrorCode.UNKNOWN,
            provider_key="gemini",
            provider_model="google/gemma-test",
            message="provider failed api_key=SECRET_VALUE",
            details={"headers": {"Authorization": "Bearer SECRET_VALUE"}},
        )

    @app.get("/unknown-secret")
    async def unknown_secret() -> None:
        raise RuntimeError(r"boom api_key=SECRET_VALUE C:\private\storage\file.json")

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("path", ["/http-secret", "/provider-secret", "/unknown-secret"])
def test_api_error_responses_do_not_leak_secrets_or_tracebacks(path: str) -> None:
    response = _security_test_client().get(path)

    assert response.status_code >= 400
    body = response.text
    assert "SECRET_VALUE" not in body
    assert "Traceback" not in body
    assert "C:\\private" not in body
    payload = response.json()
    assert "code" in payload
    assert "message" in payload
    assert "explanation" in payload


def test_redaction_helpers_scrub_nested_secret_values() -> None:
    payload = redact_sensitive(
        {
            "api_key": "SECRET_VALUE",
            "headers": {"Authorization": "Bearer SECRET_VALUE"},
            "message": "token=SECRET_VALUE",
        }
    )

    assert "SECRET_VALUE" not in str(payload)
    assert redact_secret_text("Authorization: Bearer SECRET_VALUE") == "Authorization: [REDACTED]"
    assert redact_secret_text("https://example.test/callback?token=SECRET_VALUE&ok=1") == (
        "https://example.test/callback?token=[REDACTED]&ok=1"
    )


def test_log_formatters_redact_secret_values() -> None:
    record = logging.LogRecord(
        "novelai.test",
        logging.ERROR,
        __file__,
        1,
        "Authorization: Bearer SECRET_VALUE api_key=SECRET_VALUE",
        (),
        None,
    )
    record.extra_fields = {"token": "SECRET_VALUE"}  # type: ignore[attr-defined]

    assert "SECRET_VALUE" not in SimpleFormatter().format(record)
    assert "SECRET_VALUE" not in StructuredFormatter().format(record)


def test_admin_runtime_state_does_not_expose_absolute_path(workspace_tmp_path: Path) -> None:
    preferences = PreferencesService(workspace_tmp_path)
    preferences.set_preferred_provider("dummy")
    service = AdminService(
        preferences=preferences,
        translation_cache=TranslationCache(workspace_tmp_path),
        usage=UsageService(workspace_tmp_path),
        activity_runner=object(),  # type: ignore[arg-type]
        storage=StorageService(workspace_tmp_path),
    )

    record = service.runtime_state_record("preferences")

    assert record["path"] == "runtime/preferences.json"
    assert str(workspace_tmp_path) not in str(record)


def test_gitignore_excludes_secret_backups_and_runtime_state() -> None:
    # Resolve repository root robustly regardless of current working directory
    repo_root = Path(__file__).resolve().parents[2]
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        ".env",
        "data/runtime/",
        "backups/",
        "*.bak",
        "*.zip",
        "*.tar.gz",
        "frontend/*.tsbuildinfo",
    ):
        assert pattern in gitignore

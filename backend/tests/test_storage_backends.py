"""Tests for the native Cloudflare R2 gateway boundary and local double."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from urllib.parse import parse_qs, unquote

import httpx
import pytest

from novelai.config.settings import settings
from novelai.storage.backends import _reset_r2_storage, get_r2_storage
from novelai.storage.backends.r2_gateway import (
    InMemoryR2GatewayStorage,
    R2GatewayError,
    R2GatewayStorage,
)


class TestInMemoryR2GatewayStorage:
    @pytest.fixture
    def store(self) -> InMemoryR2GatewayStorage:
        return InMemoryR2GatewayStorage()

    def test_save_and_load(self, store: InMemoryR2GatewayStorage) -> None:
        store.save("hello.txt", b"world")
        assert store.load("hello.txt") == b"world"

    def test_copy_object(self, store: InMemoryR2GatewayStorage) -> None:
        store.save("source.txt", b"payload")
        store.copy_object("source.txt", "nested/destination.txt")
        assert store.load("nested/destination.txt") == b"payload"

    def test_load_missing_raises(self, store: InMemoryR2GatewayStorage) -> None:
        with pytest.raises(FileNotFoundError):
            store.load("does-not-exist.txt")

    def test_overwrite_and_delete(self, store: InMemoryR2GatewayStorage) -> None:
        store.save("x.txt", b"one")
        store.save("x.txt", b"two")
        assert store.load("x.txt") == b"two"
        store.delete("x.txt")
        assert not store.exists("x.txt")

    def test_list_and_size(self, store: InMemoryR2GatewayStorage) -> None:
        store.save("a.txt", b"abc")
        store.save("nested/b.txt", b"12345")
        assert store.list_keys("", recursive=True) == ["a.txt", "nested/b.txt"]
        assert store.list_keys("nested") == ["nested/b.txt"]
        assert store.total_size_bytes() == 8

    def test_compare_and_swap(self, store: InMemoryR2GatewayStorage) -> None:
        assert store.compare_and_swap("x.txt", None, b"one") is True
        assert store.compare_and_swap("x.txt", b"wrong", b"two") is False
        assert store.compare_and_swap("x.txt", b"one", b"two") is True
        assert store.load("x.txt") == b"two"

    def test_mkdirs_is_virtual_noop(self, store: InMemoryR2GatewayStorage) -> None:
        store.mkdirs("some/path")
        assert not store.has_keys("some/path")

    def test_probe_readiness_is_local(self, store: InMemoryR2GatewayStorage) -> None:
        assert store.probe_readiness() is True


class GatewayTransport:
    def __init__(self, store: InMemoryR2GatewayStorage) -> None:
        self.store = store

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.raw_path.decode("ascii")).split("?", 1)[0]
        request_id = request.headers.get("x-request-id", "test-request")
        headers = {"x-request-id": request_id}
        if path == "/v1/health":
            return httpx.Response(200, json={"status": "ok"}, headers=headers, request=request)
        if path == "/v1/app/list":
            params = parse_qs(request.url.query.decode("ascii"))
            prefix = params.get("prefix", [""])[0]
            recursive = params.get("recursive", ["false"])[0] == "true"
            page = self.store.list_objects(prefix, recursive=recursive)
            return httpx.Response(
                200,
                json={
                    "objects": [self._object_json(item) for item in page.objects],
                    "delimited_prefixes": list(page.prefixes),
                    "cursor": None,
                    "truncated": False,
                },
                headers=headers,
                request=request,
            )
        marker = "/v1/app/objects/"
        if not path.startswith(marker):
            return httpx.Response(404, json={"error_code": "route_not_found"}, headers=headers, request=request)
        key = path[len(marker) :]
        if request.method == "PUT":
            existing = self.store.head(key) if self.store.exists(key) else None
            if request.headers.get("if-none-match") == "*" and existing is not None:
                return httpx.Response(
                    412, json={"error_code": "conditional_write_failed"}, headers=headers, request=request
                )
            data = request.read()
            metadata = {
                "logical-sha256": request.headers.get("x-r2-meta-logical-sha256", ""),
                "checksum-sha256": request.headers.get("x-r2-checksum-sha256", ""),
            }
            metadata = {name: value for name, value in metadata.items() if value}
            self.store.save(
                key,
                data,
                content_type=request.headers.get("x-r2-content-type"),
                content_encoding=request.headers.get("x-r2-content-encoding"),
                metadata=metadata,
            )
            return httpx.Response(201, headers={**headers, "etag": self.store.head(key).etag or ""}, request=request)
        try:
            metadata = self.store.head(key)
        except FileNotFoundError:
            return httpx.Response(404, json={"error_code": "object_not_found"}, headers=headers, request=request)
        response_headers = {
            **headers,
            "content-length": str(metadata.size_bytes),
            "etag": f'"{metadata.etag}"'
            if metadata.etag and not metadata.etag.startswith('"')
            else metadata.etag or "",
            "last-modified": metadata.last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
            if metadata.last_modified
            else "",
            "content-type": metadata.content_type or "application/octet-stream",
        }
        if metadata.checksum_sha256:
            response_headers["x-r2-checksum-sha256"] = metadata.checksum_sha256
        for name, value in metadata.metadata.items():
            response_headers[f"x-r2-meta-{name}"] = value
        if request.method == "HEAD":
            return httpx.Response(200, headers=response_headers, request=request)
        data = self.store.load(key)
        status = 200
        range_header = request.headers.get("range")
        if range_header and range_header.startswith("bytes="):
            start_text, end_text = range_header.removeprefix("bytes=").split("-", 1)
            start = int(start_text)
            end = int(end_text) if end_text else len(data) - 1
            data = data[start : end + 1]
            status = 206
            response_headers["content-length"] = str(len(data))
            response_headers["content-range"] = f"bytes {start}-{start + len(data) - 1}/*"
        return httpx.Response(status, content=data, headers=response_headers, request=request)

    @staticmethod
    def _object_json(item: Any) -> dict[str, Any]:
        return {
            "key": item.key,
            "size_bytes": item.size_bytes,
            "etag": item.etag,
            "last_modified": item.last_modified.isoformat() if item.last_modified else None,
            "content_type": item.content_type,
            "content_encoding": item.content_encoding,
            "checksum_sha256": item.checksum_sha256,
            "metadata": item.metadata,
        }


@pytest.fixture
def gateway() -> Generator[R2GatewayStorage]:
    store = InMemoryR2GatewayStorage()
    client = httpx.Client(
        base_url="https://gateway.test",
        transport=httpx.MockTransport(GatewayTransport(store)),
    )
    backend = R2GatewayStorage(
        bucket="test-dokushodo",
        bucket_class="app",
        gateway_url="https://gateway.test",
        client_id="app-client",
        client_secret="app-secret",
        client=client,
    )
    yield backend
    client.close()


class TestR2GatewayStorage:
    def test_save_load_and_metadata(self, gateway: R2GatewayStorage) -> None:
        gateway.save("novels/1/a.bin", b"world", content_type="application/octet-stream")
        assert gateway.load("novels/1/a.bin") == b"world"
        assert gateway.head("novels/1/a.bin").content_type == "application/octet-stream"

    def test_load_range_and_checksum_metadata(self, gateway: R2GatewayStorage) -> None:
        result = gateway.put_immutable("novels/1/range.bin", b"abcdef", logical_sha256="digest")
        assert result.created is True
        assert gateway.load_range("novels/1/range.bin", start=1, end=3) == b"bcd"
        assert gateway.head("novels/1/range.bin").checksum_sha256

    def test_immutable_write_is_idempotent(self, gateway: R2GatewayStorage) -> None:
        result = gateway.put_immutable("novels/1/a.json.gz", b"data", logical_sha256="digest")
        assert result.created is True
        retry = gateway.put_immutable("novels/1/a.json.gz", b"data", logical_sha256="digest")
        assert retry.created is False

    def test_list_and_size_use_gateway_contract(self, gateway: R2GatewayStorage) -> None:
        gateway.save("novels/1/a", b"1")
        gateway.save("novels/1/nested/b", b"12345")
        assert gateway.list_keys("novels/1", recursive=True) == ["novels/1/a", "novels/1/nested/b"]
        assert gateway.total_size_bytes() == 6

    def test_provider_failure_is_redacted(self) -> None:
        def denied(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"error_code": "provider_unavailable", "secret": "hidden"}, request=request)

        client = httpx.Client(base_url="https://gateway.test", transport=httpx.MockTransport(denied))
        backend = R2GatewayStorage(
            bucket="test-dokushodo",
            bucket_class="app",
            gateway_url="https://gateway.test",
            client_id="app-client",
            client_secret="app-secret",
            client=client,
        )
        with pytest.raises(R2GatewayError, match="status=503") as raised:
            backend.head("novels/1/missing")
        assert "hidden" not in str(raised.value)
        client.close()


class TestGetR2Storage:
    def test_factory_requires_gateway_identity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_r2_storage()
        monkeypatch.setattr(settings, "R2_GATEWAY_URL", "https://gateway.test")
        monkeypatch.setattr(settings, "R2_GATEWAY_CLIENT_ID", "app-client")
        from pydantic import SecretStr

        monkeypatch.setattr(settings, "R2_GATEWAY_CLIENT_SECRET", SecretStr("app-secret"))
        assert isinstance(get_r2_storage(), R2GatewayStorage)

    def test_singleton_and_reset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "R2_GATEWAY_URL", "https://gateway.test")
        monkeypatch.setattr(settings, "R2_GATEWAY_CLIENT_ID", "app-client")
        from pydantic import SecretStr

        monkeypatch.setattr(settings, "R2_GATEWAY_CLIENT_SECRET", SecretStr("app-secret"))
        _reset_r2_storage()
        first = get_r2_storage()
        assert first is get_r2_storage()
        _reset_r2_storage()
        assert first is not get_r2_storage()

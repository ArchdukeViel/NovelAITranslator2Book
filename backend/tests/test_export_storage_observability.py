"""Focused export manifest and scheduled freshness tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from novelai.services.admin_service import AdminService
from novelai.services.export_manifest_service import (
    FRESHNESS_ERROR,
    FRESHNESS_FRESH,
    FRESHNESS_MISSING,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SUCCEEDED,
    build_manifest,
    compute_export_freshness,
    compute_export_input_metadata,
    latest_export,
    list_manifests,
    load_export_freshness_status,
    read_manifest,
    run_export_freshness_check,
    write_manifest,
)
from novelai.storage.backends.base import StorageBackend
from novelai.storage.service import StorageService


class MemoryBackend(StorageBackend):
    _BACKING = "s3"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_exists_for: str | None = None

    @staticmethod
    def _key(path: str | Path) -> str:
        return str(path).replace("\\", "/").strip("/")

    def save(self, path: str | Path, data: bytes) -> None:
        self.objects[self._key(path)] = data

    def load(self, path: str | Path) -> bytes:
        key = self._key(path)
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]

    def delete(self, path: str | Path) -> None:
        self.objects.pop(self._key(path), None)

    def exists(self, path: str | Path) -> bool:
        key = self._key(path)
        if key == self.fail_exists_for:
            raise OSError("temporary storage failure")
        return key in self.objects

    def list_keys(self, prefix: str | Path, *, recursive: bool = False) -> list[str]:
        normalized = self._key(prefix)
        if normalized:
            normalized += "/"
        keys = [key for key in self.objects if key.startswith(normalized)]
        if recursive:
            return sorted(keys)
        return sorted(key for key in keys if "/" not in key[len(normalized) :])

    def has_keys(self, prefix: str | Path) -> bool:
        normalized = self._key(prefix)
        if normalized:
            normalized += "/"
        return any(key.startswith(normalized) for key in self.objects)

    def total_size_bytes(self) -> int:
        return sum(map(len, self.objects.values()))

    def mkdirs(self, path: str | Path) -> None:
        return None


def _storage(tmp_path: Path) -> tuple[StorageService, MemoryBackend]:
    backend = MemoryBackend()
    storage = StorageService(tmp_path, backend=backend)
    storage.list_novels = lambda: ["n1"]  # type: ignore[method-assign]
    storage.load_metadata = lambda novel_id: {  # type: ignore[method-assign]
        "updated_at": "2026-01-01T00:00:00Z",
        "glossary_revision": 5,
        "glossary_hash": "g5",
        "chapters": [],
    }
    return storage, backend


def _manifest(storage: StorageService, *, artifact_key: str = "exports/n1/book.epub", **values: Any) -> dict[str, Any]:
    manifest = build_manifest(
        novel_id="n1",
        export_format="epub",
        status=STATUS_SUCCEEDED,
        artifact_key=artifact_key,
        novel_updated_at="2026-01-01T00:00:00Z",
        glossary_revision=5,
        glossary_hash="g5",
        chapter_set_hash="4f53cda18c2baa0c",
        translation_version_count=0,
        translation_versions_hash="4f53cda18c2baa0c",
        export_template_version="epub",
        export_profile_hash="44136fa355b3678a",
    )
    manifest.update(values)
    write_manifest(storage, "n1", manifest)
    return manifest


def test_manifest_schema_and_initial_freshness() -> None:
    pending = build_manifest(novel_id="n1", export_format="epub")
    succeeded = build_manifest(
        novel_id="n1",
        export_format="epub",
        status=STATUS_SUCCEEDED,
        translation_versions_hash="translations",
        chapter_set_hash="chapters",
        export_profile_hash="profile",
    )
    failed = build_manifest(
        novel_id="n1",
        export_format="epub",
        status=STATUS_FAILED,
        failure_code="render_error",
        failure_message="safe failure",
    )

    assert pending["status"] == STATUS_PENDING
    assert succeeded["freshness_status"] == FRESHNESS_FRESH
    assert succeeded["freshness_checked_at"] == succeeded["completed_at"]
    assert succeeded["translation_versions_hash"] == "translations"
    assert succeeded["chapter_set_hash"] == "chapters"
    assert failed["failure_message"] == "safe failure"
    assert "text" not in json.dumps(succeeded)


def test_storage_backend_safe_manifest_io(tmp_path: Path) -> None:
    storage, _ = _storage(tmp_path)
    first = build_manifest(novel_id="n1", export_format="epub", status=STATUS_SUCCEEDED)
    second = build_manifest(novel_id="n1", export_format="html", status=STATUS_SUCCEEDED)
    second["export_id"] = "later"
    write_manifest(storage, "n1", first)
    write_manifest(storage, "n1", second)

    loaded = read_manifest(storage, "n1", first["export_id"])
    assert loaded and loaded["export_id"] == first["export_id"]
    assert len(list_manifests(storage, "n1")) == 2
    assert latest_export(storage, "n1", "html") == second


def test_input_metadata_hashes_revision_data_without_content(tmp_path: Path) -> None:
    storage, _ = _storage(tmp_path)
    storage.load_metadata = lambda novel_id: {  # type: ignore[method-assign]
        "updated_at": "2026-01-01T00:00:00Z",
        "glossary_revision": 5,
        "chapters": [{"id": "1", "title": "First"}],
    }
    storage.load_translated_chapter = lambda novel_id, chapter_id: {  # type: ignore[method-assign]
        "version_id": "v2",
        "text": "private translated content",
    }

    metadata = compute_export_input_metadata(storage, "n1", "epub", export_options={"toc": True})

    assert metadata["translation_version_count"] == 1
    assert metadata["export_template_version"] == "epub"
    assert "private translated content" not in json.dumps(metadata)
    assert len(metadata["translation_versions_hash"]) == 16
    assert len(metadata["chapter_set_hash"]) == 16
    assert len(metadata["export_profile_hash"]) == 16


def test_canonical_freshness_comparison() -> None:
    current = {
        "translation_versions_hash": "t1",
        "chapter_set_hash": "c1",
        "novel_updated_at": "n1",
        "glossary_revision": 1,
        "export_template_version": "epub",
        "export_profile_hash": "p1",
    }
    assert compute_export_freshness(dict(current), current) == (FRESHNESS_FRESH, None)
    assert compute_export_freshness({**current, "translation_versions_hash": "old"}, current) == (
        FRESHNESS_STALE,
        "translation_changed",
    )
    assert compute_export_freshness({**current, "chapter_set_hash": "old"}, current) == (
        FRESHNESS_STALE,
        "chapter_order_changed",
    )
    assert compute_export_freshness({}, current) == (FRESHNESS_UNKNOWN, None)
    assert compute_export_freshness({"translation_versions_hash": "t1"}, {}) == (FRESHNESS_UNKNOWN, None)


def test_scan_persists_fresh_stale_missing_and_unknown(tmp_path: Path) -> None:
    storage, backend = _storage(tmp_path)
    fresh = _manifest(storage, artifact_key="exports/n1/fresh.epub")
    stale = _manifest(storage, artifact_key="exports/n1/stale.epub", export_id="stale", glossary_revision=4)
    missing = _manifest(storage, artifact_key="exports/n1/missing.epub", export_id="missing")
    unknown = _manifest(storage, artifact_key="exports/n1/unknown.epub", export_id="unknown")
    for field, _ in (
        ("translation_versions_hash", None),
        ("chapter_set_hash", None),
        ("novel_updated_at", None),
        ("glossary_revision", None),
        ("glossary_hash", None),
        ("export_template_version", None),
        ("export_profile_hash", None),
    ):
        unknown.pop(field, None)
    write_manifest(storage, "n1", unknown)
    for key in (fresh["artifact_key"], stale["artifact_key"], unknown["artifact_key"]):
        backend.save(key, b"artifact")

    result = run_export_freshness_check(storage, batch_size=2, max_artifacts=10)

    assert result["status"] == "succeeded"
    assert result["summary"] == {
        "scanned": 4,
        "fresh": 1,
        "stale": 1,
        "missing": 1,
        "unknown": 1,
        "error": 0,
        "skipped_locked": 0,
    }
    assert read_manifest(storage, "n1", stale["export_id"])["freshness_stale_reason"] == "glossary_changed"  # type: ignore[index]
    assert read_manifest(storage, "n1", missing["export_id"])["freshness_status"] == FRESHNESS_MISSING  # type: ignore[index]
    assert read_manifest(storage, "n1", unknown["export_id"])["freshness_status"] == FRESHNESS_UNKNOWN  # type: ignore[index]
    assert load_export_freshness_status(storage)["summary"]["scanned"] == 4


def test_scan_continues_after_artifact_error_and_is_bounded(tmp_path: Path) -> None:
    storage, backend = _storage(tmp_path)
    broken = _manifest(storage, artifact_key="exports/n1/broken.epub", export_id="z-broken")
    good = _manifest(storage, artifact_key="exports/n1/good.epub", export_id="y-good")
    extra = _manifest(storage, artifact_key="exports/n1/extra.epub", export_id="x-extra")
    backend.fail_exists_for = broken["artifact_key"]
    backend.save(good["artifact_key"], b"artifact")
    backend.save(extra["artifact_key"], b"artifact")

    result = run_export_freshness_check(storage, batch_size=1, max_artifacts=2)

    assert result["status"] == "partially_succeeded"
    assert result["summary"]["scanned"] == 2
    assert result["summary"]["error"] == 1
    assert result["summary"]["fresh"] == 1
    persisted = read_manifest(storage, "n1", broken["export_id"])
    assert persisted and persisted["freshness_status"] == FRESHNESS_ERROR
    assert persisted["freshness_error_message"] == "OSError"


def test_scan_skips_when_file_lock_is_held(tmp_path: Path, monkeypatch) -> None:
    storage, _ = _storage(tmp_path)

    def blocked(self) -> bool:
        raise TimeoutError

    monkeypatch.setattr("novelai.storage.file_lock.InterProcessFileLock.acquire", blocked)
    result = run_export_freshness_check(storage)

    assert result["status"] == "skipped_locked"
    assert result["summary"]["skipped_locked"] == 1
    assert load_export_freshness_status(storage)["status"] == "skipped_locked"


def test_admin_service_exposes_persisted_freshness_and_status(tmp_path: Path, monkeypatch) -> None:
    storage, _ = _storage(tmp_path)
    manifest = _manifest(storage, freshness_status=FRESHNESS_STALE, freshness_stale_reason="translation_changed")
    service = object.__new__(AdminService)
    service.storage = storage
    monkeypatch.setattr("novelai.services.admin_service.settings.EXPORT_FRESHNESS_CHECK_ENABLED", True)

    listed = service.list_novel_exports("n1")["manifests"]
    assert listed[0]["freshness_status"] == FRESHNESS_STALE
    assert listed[0]["freshness_stale_reason"] == "translation_changed"
    assert service.latest_novel_export("n1", "epub")["export_id"] == manifest["export_id"]
    assert service.export_freshness_status()["last_run"]["status"] == "never_run"

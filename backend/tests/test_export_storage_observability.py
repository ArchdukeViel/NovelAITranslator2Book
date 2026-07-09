"""Tests for export storage observability — manifests, freshness, admin APIs."""

from __future__ import annotations

import json
from pathlib import Path

from novelai.services.export_manifest_service import (
    STATUS_FAILED,
    STATUS_LEGACY_UNKNOWN,
    STATUS_PENDING,
    STATUS_SUCCEEDED,
    build_manifest,
    compute_export_freshness,
    latest_export,
    list_manifests,
    read_manifest,
    write_manifest,
)


class TestManifestSchema:
    def test_build_minimal_manifest(self) -> None:
        m = build_manifest(novel_id="n1", export_format="epub")
        assert m["novel_id"] == "n1"
        assert m["format"] == "epub"
        assert m["status"] == STATUS_PENDING
        assert "export_id" in m
        assert "manifest_key" in m
        assert "artifact_key" in m
        assert "created_at" in m

    def test_build_succeeded_manifest(self) -> None:
        m = build_manifest(
            novel_id="n1", export_format="epub", status=STATUS_SUCCEEDED,
            output_filename="n1.epub", chapter_count=10, file_size_bytes=2048,
            checksum="abc123",
        )
        assert m["status"] == STATUS_SUCCEEDED
        assert m["output_filename"] == "n1.epub"
        assert m["chapter_count"] == 10
        assert m["file_size_bytes"] == 2048
        assert m["checksum"] == "abc123"
        assert "completed_at" in m

    def test_build_failed_manifest(self) -> None:
        m = build_manifest(
            novel_id="n1", export_format="epub", status=STATUS_FAILED,
            failure_code="render_error", failure_message="EPUB render failed",
        )
        assert m["status"] == STATUS_FAILED
        assert m["failure_code"] == "render_error"
        assert m["failure_message"] == "EPUB render failed"
        assert "failed_at" in m

    def test_manifest_no_absolute_paths(self) -> None:
        m = build_manifest(novel_id="n1", export_format="epub", status=STATUS_SUCCEEDED)
        dumped = str(m)
        assert "C:" not in dumped
        assert "/app/" not in dumped
        assert "secret" not in dumped.lower()
        assert "key" not in dumped.lower() or m["artifact_key"].startswith("exports/")

    def test_export_id_deterministic(self) -> None:
        """Same input produces same export_id (within same second)."""
        m1 = build_manifest(novel_id="n1", export_format="epub")
        m2 = build_manifest(novel_id="n1", export_format="epub")
        assert m1["export_id"] == m2["export_id"]

    def test_different_formats_different_keys(self) -> None:
        epub = build_manifest(novel_id="n1", export_format="epub")
        html = build_manifest(novel_id="n1", export_format="html")
        assert epub["export_id"] != html["export_id"]
        assert epub["manifest_key"] != html["manifest_key"]

    def test_manifest_serializable(self) -> None:
        m = build_manifest(novel_id="n1", export_format="epub", status=STATUS_SUCCEEDED,
                           export_options={"include_toc": True, "title": "Test"})
        json.dumps(m)


class TestManifestPersistence:
    def test_write_and_read(self, tmp_path: Path) -> None:
        from novelai.storage.service import StorageService
        storage = StorageService(tmp_path)
        m = build_manifest(novel_id="n1", export_format="epub", status=STATUS_SUCCEEDED)
        write_manifest(storage, "n1", m)
        loaded = read_manifest(storage, "n1", m["export_id"])
        assert loaded is not None
        assert loaded["export_id"] == m["export_id"]
        assert loaded["status"] == STATUS_SUCCEEDED

    def test_list_manifests(self, tmp_path: Path) -> None:
        from novelai.storage.service import StorageService
        storage = StorageService(tmp_path)
        m1 = build_manifest(novel_id="n1", export_format="epub", status=STATUS_SUCCEEDED)
        m2 = build_manifest(novel_id="n1", export_format="html", status=STATUS_SUCCEEDED)
        write_manifest(storage, "n1", m1)
        write_manifest(storage, "n1", m2)
        manifests = list_manifests(storage, "n1")
        assert len(manifests) == 2

    def test_latest_export_by_format(self, tmp_path: Path) -> None:
        from novelai.storage.service import StorageService
        storage = StorageService(tmp_path)
        m1 = build_manifest(novel_id="n1", export_format="epub", status=STATUS_SUCCEEDED)
        m2 = build_manifest(novel_id="n1", export_format="epub", status=STATUS_SUCCEEDED)
        write_manifest(storage, "n1", m1)
        write_manifest(storage, "n1", m2)
        latest = latest_export(storage, "n1", "epub")
        assert latest is not None
        assert latest["export_id"] == m2["export_id"]

    def test_no_manifests_returns_empty(self, tmp_path: Path) -> None:
        from novelai.storage.service import StorageService
        storage = StorageService(tmp_path)
        assert list_manifests(storage, "n1") == []

    def test_read_nonexistent(self, tmp_path: Path) -> None:
        from novelai.storage.service import StorageService
        storage = StorageService(tmp_path)
        assert read_manifest(storage, "n1", "nonexistent") is None


class TestExportFreshness:
    def test_current_freshness(self, tmp_path: Path) -> None:
        from novelai.storage.service import StorageService
        storage = StorageService(tmp_path)
        m = build_manifest(novel_id="n1", export_format="epub", status=STATUS_SUCCEEDED,
                           glossary_revision=5, novel_updated_at="2026-01-01T00:00:00Z")
        state = compute_export_freshness(storage, "n1", m,
                                        current_glossary_revision=5,
                                        current_novel_updated_at="2026-01-01T00:00:00Z")
        assert state == "current"

    def test_stale_glossary_revision(self, tmp_path: Path) -> None:
        from novelai.storage.service import StorageService
        storage = StorageService(tmp_path)
        m = build_manifest(novel_id="n1", export_format="epub", status=STATUS_SUCCEEDED,
                           glossary_revision=5)
        state = compute_export_freshness(storage, "n1", m, current_glossary_revision=6)
        assert state == "stale"

    def test_unknown_legacy_manifest(self, tmp_path: Path) -> None:
        from novelai.storage.service import StorageService
        storage = StorageService(tmp_path)
        m = build_manifest(novel_id="n1", export_format="epub", status=STATUS_LEGACY_UNKNOWN)
        state = compute_export_freshness(storage, "n1", m)
        assert state == "unknown_legacy_manifest"

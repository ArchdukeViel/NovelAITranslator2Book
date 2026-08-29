from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState, ChapterStateTransition
from novelai.core.platform import ChapterVersionKind
from novelai.core.security import validate_storage_identifier
from novelai.storage.jobs import (
    _get_checkpoints_dir,
    _get_state_dir,
    create_checkpoint,
    list_checkpoints,
    load_chapter_state,
    restore_from_checkpoint,
    rollback_to_state,
    save_chapter_state,
    update_chapter_state,
)
from novelai.storage.r2_catalog import (
    activate_translated_chapter_version as _r2_activate_translated_chapter_version,
)
from novelai.storage.r2_catalog import (
    clear_chapter_image_assets as _r2_clear_chapter_image_assets,
)
from novelai.storage.r2_catalog import (
    count_stored_chapters as _r2_count_stored_chapters,
)
from novelai.storage.r2_catalog import (
    count_translated_chapters as _r2_count_translated_chapters,
)
from novelai.storage.r2_catalog import (
    delete_novel as _r2_delete_novel,
)
from novelai.storage.r2_catalog import (
    get_novel_chapter_summary as _r2_get_novel_chapter_summary,
)
from novelai.storage.r2_catalog import (
    list_metadata_history as _r2_list_metadata_history,
)
from novelai.storage.r2_catalog import (
    list_novels as _r2_list_novels,
)
from novelai.storage.r2_catalog import (
    list_stored_chapters as _r2_list_stored_chapters,
)
from novelai.storage.r2_catalog import (
    list_translated_chapter_versions as _r2_list_translated_chapter_versions,
)
from novelai.storage.r2_catalog import (
    list_translated_chapters as _r2_list_translated_chapters,
)
from novelai.storage.r2_catalog import (
    load_chapter as _r2_load_chapter,
)
from novelai.storage.r2_catalog import (
    load_chapter_media_state as _r2_load_chapter_media_state,
)
from novelai.storage.r2_catalog import (
    load_glossary as _r2_load_glossary,
)
from novelai.storage.r2_catalog import (
    load_metadata as _r2_load_metadata,
)
from novelai.storage.r2_catalog import (
    load_metadata_snapshot as _r2_load_metadata_snapshot,
)
from novelai.storage.r2_catalog import (
    load_source_state as _r2_load_source_state,
)
from novelai.storage.r2_catalog import (
    load_translated_chapter as _r2_load_translated_chapter,
)
from novelai.storage.r2_catalog import (
    load_translated_chapter_by_version_id as _r2_load_translated_chapter_by_version_id,
)
from novelai.storage.r2_catalog import (
    load_translation_edit_history as _r2_load_translation_edit_history,
)
from novelai.storage.r2_catalog import (
    resolve_active_generation_id as _r2_resolve_active_generation_id,
)
from novelai.storage.r2_catalog import (
    resolve_asset_path as _r2_resolve_asset_path,
)
from novelai.storage.r2_catalog import (
    resolve_onboarding_status as _r2_resolve_onboarding_status,
)
from novelai.storage.r2_catalog import (
    resolve_storage_novel_id as _r2_resolve_storage_novel_id,
)
from novelai.storage.r2_catalog import (
    save_chapter as _r2_save_chapter,
)
from novelai.storage.r2_catalog import (
    save_chapter_image_asset as _r2_save_chapter_image_asset,
)
from novelai.storage.r2_catalog import (
    save_chapter_media_state as _r2_save_chapter_media_state,
)
from novelai.storage.r2_catalog import (
    save_edited_translation as _r2_save_edited_translation,
)
from novelai.storage.r2_catalog import (
    save_glossary as _r2_save_glossary,
)
from novelai.storage.r2_catalog import (
    save_metadata as _r2_save_metadata,
)
from novelai.storage.r2_catalog import (
    save_source_state as _r2_save_source_state,
)
from novelai.storage.r2_catalog import (
    save_translated_chapter as _r2_save_translated_chapter,
)
from novelai.storage.r2_catalog import (
    update_onboarding_status as _r2_update_onboarding_status,
)
from novelai.storage.runtime_contracts import (
    _fetch_cache_dir,
    _runtime_dir,
    _translation_runtime_dir,
    cleanup_expired_runtime_data,
    cleanup_fetch_cache,
    cleanup_pipeline_events,
    delete_translation_bundle,
    fetch_cache_conditional_headers,
    list_chunk_attempt_records,
    list_provider_request_records,
    load_translation_run_manifest,
    read_fetch_cache_entry,
    read_translation_bundle,
    read_translation_chunks,
    read_translation_output,
    save_chunk_attempt_record,
    save_fetch_cache_entry,
    save_provider_request_record,
    save_translation_bundle,
    save_translation_chunks,
    save_translation_output,
    save_translation_run_manifest,
    update_translation_chunk_status,
)
from novelai.storage.traceability import (
    _read_json_file,
    _trace_dir,
    append_pipeline_event,
    append_pipeline_events,
    list_pipeline_events,
    load_all_scheduler_states,
    load_chunk_states,
    load_scheduler_state,
    save_scheduler_state,
    upsert_chunk_state,
    upsert_chunk_states,
)

logger = logging.getLogger(__name__)


def _fsync_directory(directory: Path) -> None:
    """Best-effort fsync of a directory so a rename is durable.

    Failures are debug-level only; directory fsync is unsupported on some
    platforms and must never break the write.
    """
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        logger.debug("Directory fsync failed for %s", directory, exc_info=True)
    finally:
        os.close(fd)


class StorageService:
    _test_db_session: Any

    if TYPE_CHECKING:

        def activate_translated_chapter_version(self, *args: Any, **kwargs: Any) -> Any: ...
        def build_chapter_payload(self, *args: Any, **kwargs: Any) -> Any: ...
        def clear_chapter_image_assets(self, *args: Any, **kwargs: Any) -> Any: ...
        def count_stored_chapters(self, *args: Any, **kwargs: Any) -> Any: ...
        def count_translated_chapters(self, *args: Any, **kwargs: Any) -> Any: ...
        def delete_novel(self, *args: Any, **kwargs: Any) -> Any: ...
        def existing_chapter_hash(self, *args: Any, **kwargs: Any) -> Any: ...
        def get_chapters_by_state(self, *args: Any, **kwargs: Any) -> Any: ...
        def get_chapter_progress(self, *args: Any, **kwargs: Any) -> Any: ...
        def get_chapters_with_errors(self, *args: Any, **kwargs: Any) -> Any: ...
        def get_novel_chapter_summary(self, *args: Any, **kwargs: Any) -> Any: ...
        def get_scraping_progress(self, *args: Any, **kwargs: Any) -> Any: ...
        def list_metadata_history(self, *args: Any, **kwargs: Any) -> Any: ...
        def list_novels(self, *args: Any, **kwargs: Any) -> Any: ...
        def list_stored_chapters(self, *args: Any, **kwargs: Any) -> Any: ...
        def list_translated_chapter_versions(self, *args: Any, **kwargs: Any) -> Any: ...
        def list_translated_chapters(self, *args: Any, **kwargs: Any) -> Any: ...
        def load_chapter(self, *args: Any, **kwargs: Any) -> Any: ...
        def load_chapter_media_state(self, *args: Any, **kwargs: Any) -> Any: ...
        def load_glossary(self, *args: Any, **kwargs: Any) -> Any: ...
        def load_metadata(self, *args: Any, **kwargs: Any) -> Any: ...
        def load_metadata_for_crawl(self, *args: Any, **kwargs: Any) -> Any: ...
        def load_metadata_snapshot(self, *args: Any, **kwargs: Any) -> Any: ...
        def load_source_state(self, *args: Any, **kwargs: Any) -> Any: ...
        def load_translated_chapter(self, *args: Any, **kwargs: Any) -> Any: ...
        def load_translated_chapter_by_version_id(self, *args: Any, **kwargs: Any) -> Any: ...
        def load_translation_edit_history(self, *args: Any, **kwargs: Any) -> Any: ...
        def query_chapters(self, *args: Any, **kwargs: Any) -> Any: ...
        def resolve_active_generation_id(self, *args: Any, **kwargs: Any) -> Any: ...
        def resolve_asset_path(self, *args: Any, **kwargs: Any) -> Any: ...
        def resolve_onboarding_status(self, *args: Any, **kwargs: Any) -> Any: ...
        def save_chapter(self, *args: Any, **kwargs: Any) -> Any: ...
        def save_chapter_image_asset(self, *args: Any, **kwargs: Any) -> Any: ...
        def save_chapter_media_state(self, *args: Any, **kwargs: Any) -> Any: ...
        def save_edited_translation(self, *args: Any, **kwargs: Any) -> Any: ...
        def save_glossary(self, *args: Any, **kwargs: Any) -> Any: ...
        def save_metadata(self, *args: Any, **kwargs: Any) -> Any: ...
        def save_source_state(self, *args: Any, **kwargs: Any) -> Any: ...
        def save_translated_chapter(self, *args: Any, **kwargs: Any) -> Any: ...
        def update_onboarding_status(self, *args: Any, **kwargs: Any) -> Any: ...

    """R2-backed content service with a stable domain-facing facade.

    `Path` values used internally are logical object-key paths only. They are
    never treated as local content paths when the production R2 backend is in
    use. Runtime/cache/checkpoint services use `settings.RUNTIME_DIR` instead.
    """

    SCHEMA_VERSION = 2
    OCR_STATUSES = {"pending", "reviewed", "skipped", "failed"}
    REEMBED_STATUSES = {"pending", "completed", "failed", "skipped"}

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _text_paragraphs(text: str) -> list[str]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []
        return [paragraph for paragraph in re.split(r"\n{2,}", normalized) if paragraph]

    @staticmethod
    def _normalize_source_blocks(blocks: Any) -> list[dict[str, Any]]:
        if not isinstance(blocks, list):
            return []

        normalized: list[dict[str, Any]] = []
        previous_type: str | None = None
        line_index = 0
        break_index = 0
        source_order = 0
        for item in blocks:
            if not isinstance(item, dict):
                continue
            block_type = item.get("type")
            if block_type == "break":
                if previous_type == "break" or not normalized:
                    continue
                break_index += 1
                source_order += 1
                normalized.append(
                    {
                        "type": "break",
                        "source_block_id": str(item.get("source_block_id") or f"b{break_index:04d}"),
                        "source_order": source_order,
                    }
                )
                previous_type = "break"
                continue
            if block_type != "line":
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            line_index += 1
            source_order += 1
            normalized.append(
                {
                    "type": "line",
                    "source_block_id": f"s{line_index:04d}",
                    "paragraph_id": f"p{line_index:04d}",
                    "text": text.strip("\n"),
                    "source_order": source_order,
                }
            )
            previous_type = "line"
        if normalized and normalized[-1].get("type") == "break":
            normalized.pop()
        return normalized

    @staticmethod
    def _clean_string(value: Any, default: str | None = None) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return default

    def __init__(self, base_dir: Path | None = None, backend: Any | None = None) -> None:
        if backend is not None:
            self._backend = backend
        elif base_dir is not None:
            if settings.ENV != "test":
                raise ValueError("StorageService requires an explicit R2 backend outside test isolation")
            # Tests use the same R2 semantics as production, with an isolated
            # in-memory object store. The path remains a logical test root for
            # runtime helper services and is never used as canonical storage.
            from novelai.storage.backends.r2 import InMemoryR2Storage

            self._backend = InMemoryR2Storage()
        elif settings.ENV == "test":
            from novelai.storage.backends.r2 import InMemoryR2Storage

            self._backend = InMemoryR2Storage()
        else:
            from novelai.storage.backends import get_r2_storage

            self._backend = get_r2_storage()

        if getattr(self._backend, "_BACKING", None) != "r2":
            raise TypeError("StorageService requires the Cloudflare R2 backend")
        # This path is only the disposable runtime root used by checkpoints,
        # traceability, and fetch/translation coordination. Canonical novel
        # content is never rooted beneath it.
        self.base_dir = (base_dir or settings.RUNTIME_DIR).resolve()
        self._initial_runtime_dir = settings.RUNTIME_DIR.resolve()

    # Runtime and R2 boundary helpers.

    def _rel(self, path: Path) -> str:
        """Convert absolute Path to backend-relative key."""
        return str(path.relative_to(self.base_dir))

    def _read_text_optional(self, path: Path) -> str | None:
        """Read an optional disposable runtime file."""
        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical content must be read through PostgreSQL references and exact R2 keys")
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    def _read_text(self, path: Path) -> str:
        """Read a disposable runtime file."""
        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical content must be read through PostgreSQL references and exact R2 keys")
        return path.read_text(encoding="utf-8")

    def _write_text(self, path: Path, content: str) -> None:
        """Write a disposable runtime file."""
        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical content must be written as an immutable R2 artifact")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_text_atomic(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        """Write ``content`` to ``path`` atomically.

        Writes to a unique temp file in the same directory, flushes and fsyncs
        it, then replaces the target with ``os.replace`` so readers never see a
        partial file. Best-effort fsyncs the parent directory and removes the
        temp file on failure before the rename.

        Canonical R2 content never uses this method; it is limited to
        disposable local runtime files.
        """
        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical content must not use filesystem atomic rename")
        from novelai.utils.filesystem import replace_with_retry

        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        replaced = False
        try:
            temp_path.write_text(content, encoding=encoding)
            # Bounded retry for transient Windows WinError-5 file locks so an
            # antivirus/reader-held handle cannot flake the atomic rename.
            replace_with_retry(temp_path, path)
            replaced = True
            _fsync_directory(path.parent)
        except Exception as exc:
            if not replaced:
                with contextlib.suppress(OSError):
                    temp_path.unlink(missing_ok=True)
                logger.warning("Atomic write failed for %s: %s", path, exc)
            raise

    def _write_json_atomic(self, path: Path, payload: Any, *, encoding: str = "utf-8") -> None:
        """Serialize ``payload`` as JSON and write it atomically."""
        self._write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2), encoding=encoding)

    def _path_exists(self, path: Path) -> bool:
        """Check an exact disposable runtime file."""
        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical content existence is represented by PostgreSQL references")
        return path.exists()

    def _is_dir_present(self, path: Path) -> bool:
        """Return True when at least one descendant object exists under *path*.

        This helper is limited to disposable local runtime directories.
        """
        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical content directories do not exist; use exact R2 keys")
        return path.is_dir() and any(path.iterdir())

    def _unlink_path(self, path: Path) -> None:
        """Delete a disposable runtime file."""
        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical R2 artifacts are immutable and are never unlinked here")
        path.unlink(missing_ok=True)

    def _mkdirs(self, path: Path) -> None:
        """Create a disposable runtime directory."""
        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical R2 prefixes are virtual and do not use mkdir")
        path.mkdir(parents=True, exist_ok=True)

    def probe(self) -> bool:
        """Verify configured backend write/read/delete behavior."""
        return self.probe_readiness()

    def probe_readiness(self) -> bool:
        """Check backend availability without mutating storage.

        Readiness probes run frequently from reverse-proxy health checks, so
        they must not create and delete objects on every request. The full
        write/read/delete verification remains available through ``probe``
        for owner diagnostics and scheduled validation.
        """
        probe = getattr(self._backend, "probe_readiness", None)
        if callable(probe):
            return bool(probe())
        return bool(self._backend.exists(self._rel(self.base_dir)))

    def _list_dir(self, path: Path) -> list[Path]:
        """List immediate children via storage backend."""
        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical R2 prefixes are not local directories")
        return sorted(path.iterdir()) if path.is_dir() else []

    def _glob(self, path: Path, pattern: str) -> list[Path]:
        """List children matching glob pattern via storage backend."""
        import fnmatch

        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical R2 prefixes are not local directories")
        return sorted(item for item in path.iterdir() if fnmatch.fnmatch(item.name, pattern)) if path.is_dir() else []

    def _rmtree(self, path: Path) -> None:
        """Remove directory tree via storage backend."""
        if not self._is_runtime_path(path):
            raise RuntimeError("Canonical R2 artifacts are immutable and are never removed as a local tree")
        if path.exists():
            shutil.rmtree(path)

    def list_keys_under(self, prefix: str | Path, *, recursive: bool = True) -> list[str]:
        """List R2 keys for diagnostics and backup tooling only."""

        if isinstance(prefix, Path):
            prefix_str = prefix.as_posix()
        else:
            prefix_str = str(prefix).replace("\\", "/")
        if prefix_str and not prefix_str.endswith("/"):
            prefix_str = prefix_str + "/"
        return self._backend.list_keys(prefix_str, recursive=recursive)

    def read_payload(self, key: str) -> dict[str, Any] | None:
        """Read and decode one JSON object for diagnostics and backup tooling."""

        try:
            raw = self._backend.load(key)
        except FileNotFoundError, OSError:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError, UnicodeDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _r2_artifacts(self) -> Any:
        from novelai.storage.artifacts import R2ArtifactRepository
        from novelai.storage.backends.r2 import R2Storage

        if not isinstance(self._backend, R2Storage):
            raise RuntimeError("Immutable artifact methods require the R2 backend")
        return R2ArtifactRepository(self._backend)

    def resolve_storage_novel_id(self, novel_id: str) -> str:
        """Resolve a public/source slug to the immutable PostgreSQL ID for R2 keys."""

        return _r2_resolve_storage_novel_id(self, novel_id)

    @property
    def r2_backend(self) -> Any:
        """Return the canonical R2 backend for storage-domain services."""

        from novelai.storage.backends.r2 import R2Storage

        if not isinstance(self._backend, R2Storage):
            raise RuntimeError("This operation requires the canonical R2 backend")
        return self._backend

    def save_raw_chapter_artifact(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        *,
        title: str | None = None,
        source_key: str | None = None,
        source_url: str | None = None,
        artifact_payload: dict[str, Any] | None = None,
        storage_novel_id: str | None = None,
    ) -> Any:
        """Write one immutable R2 raw chapter artifact and return its reference."""

        from novelai.storage.artifacts import StoredArtifact

        payload = dict(artifact_payload) if isinstance(artifact_payload, dict) else {}
        payload.setdefault("schema_version", self.SCHEMA_VERSION)
        payload.setdefault("id", str(chapter_id))
        payload.setdefault("title", title)
        payload.setdefault("source_key", source_key)
        payload.setdefault("source_url", source_url)
        payload.setdefault(
            "raw",
            {
                "text": text,
                "paragraphs": self._text_paragraphs(text),
            },
        )
        raw_payload = payload.get("raw")
        if not isinstance(raw_payload, dict):
            raw_payload = {"text": text, "paragraphs": self._text_paragraphs(text)}
            payload["raw"] = raw_payload
        raw_payload.setdefault("text", text)
        raw_payload.setdefault("paragraphs", self._text_paragraphs(text))
        stored = self._r2_artifacts().put_json(
            storage_novel_id=storage_novel_id or self.resolve_storage_novel_id(novel_id),
            kind="chapters",
            identity=str(chapter_id),
            payload=payload,
        )
        return StoredArtifact(
            key=stored.key,
            logical_sha256=stored.logical_sha256,
            size_bytes=stored.size_bytes,
            created=stored.created,
        )

    def _is_runtime_path(self, path: Path) -> bool:
        """Return whether ``path`` is inside the disposable local runtime root."""

        if getattr(self._backend, "_BACKING", "r2") != "r2":
            return False
        runtime_root = self._runtime_root()
        try:
            path.resolve().relative_to(runtime_root.resolve())
        except ValueError:
            return False
        return True

    def _runtime_root(self) -> Path:
        """Return the current disposable runtime root for this facade.

        Tests and isolated tools may temporarily redirect ``settings.RUNTIME_DIR``
        after constructing a storage facade. Honor that redirect while keeping
        explicit storage roots isolated beneath ``<base_dir>/runtime`` by
        default.
        """

        configured_root = settings.RUNTIME_DIR.resolve()
        if configured_root != self._initial_runtime_dir:
            return configured_root
        if self.base_dir == configured_root:
            return configured_root
        return (self.base_dir / "runtime").resolve()

    def save_translation_artifact(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        *,
        provider_key: str | None = None,
        provider_model: str | None = None,
        source_hash: str | None = None,
        translation_run_id: str | None = None,
        raw_generation_id: str | None = None,
        glossary_hash: str | None = None,
        prompt_template_version: str | None = None,
        artifact_payload: dict[str, Any] | None = None,
        storage_novel_id: str | None = None,
    ) -> Any:
        """Write one immutable R2 translation artifact and return its reference."""

        from novelai.storage.artifacts import StoredArtifact

        payload = dict(artifact_payload) if isinstance(artifact_payload, dict) else {}
        payload.update(
            {
                "schema_version": self.SCHEMA_VERSION,
                "chapter_id": str(chapter_id),
                "text": text,
                "paragraphs": self._text_paragraphs(text),
                "provider_key": provider_key,
                "provider_model": provider_model,
                "source_content_hash": source_hash,
                "translation_run_id": translation_run_id,
                "raw_generation_id": raw_generation_id,
                "glossary_hash": glossary_hash,
                "prompt_template_version": prompt_template_version,
            }
        )
        stored = self._r2_artifacts().put_json(
            storage_novel_id=storage_novel_id or self.resolve_storage_novel_id(novel_id),
            kind="translations",
            identity=str(chapter_id),
            payload=payload,
        )
        return StoredArtifact(
            key=stored.key,
            logical_sha256=stored.logical_sha256,
            size_bytes=stored.size_bytes,
            created=stored.created,
        )

    def load_r2_json_artifact(self, key: str) -> dict[str, Any]:
        """Load one exact immutable R2 JSON key; never enumerate a prefix."""

        return self._r2_artifacts().load_json(key)

    def runtime_path(self, *parts: str) -> Path:
        """Resolve a disposable runtime path outside the R2 object namespace."""
        return self._runtime_root() / Path(*parts)

    def backups_path(self, *parts: str) -> Path:
        """Resolve a disposable local backup-work path."""
        return self.runtime_path("backups", *parts)

    @staticmethod
    def _normalize_image_manifest(images: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not images:
            return []

        normalized: list[dict[str, Any]] = []
        for image in images:
            if not isinstance(image, dict):
                continue
            item = dict(image)
            local_path = item.get("local_path")
            if isinstance(local_path, Path):
                item["local_path"] = local_path.as_posix()
            normalized.append(item)
        normalized.sort(key=lambda item: int(item.get("index", 0)))
        return normalized

    @staticmethod
    def _normalize_named_dict_items(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                normalized.append(dict(item))
        return normalized

    @staticmethod
    def _normalize_version_kind(
        value: Any, default: ChapterVersionKind = ChapterVersionKind.MACHINE_TRANSLATION
    ) -> str:
        if isinstance(value, ChapterVersionKind):
            return value.value
        if isinstance(value, str) and value in {kind.value for kind in ChapterVersionKind}:
            return value
        return default.value

    @staticmethod
    def _next_translation_version_id(versions: list[dict[str, Any]]) -> str:
        used = {str(version.get("version_id")) for version in versions if version.get("version_id") is not None}
        index = len(used) + 1
        while f"v{index}" in used:
            index += 1
        return f"v{index}"

    @staticmethod
    def _next_edit_history_id(entries: list[dict[str, Any]]) -> str:
        used = {str(entry.get("id")) for entry in entries if entry.get("id") is not None}
        index = len(used) + 1
        while f"e{index}" in used:
            index += 1
        return f"e{index}"

    @staticmethod
    def _normalize_optional_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except TypeError, ValueError:
            return None

    @staticmethod
    def _serialize_checkpoint_state(state_data: dict[str, Any] | None) -> dict[str, Any] | None:
        """Convert chapter state payload to JSON-safe data for checkpoints."""
        if not isinstance(state_data, dict):
            return None

        current_state_raw = state_data.get("current_state")
        if isinstance(current_state_raw, ChapterState):
            current_state = current_state_raw.value
        else:
            current_state = current_state_raw if isinstance(current_state_raw, str) else ChapterState.SCRAPED.value

        transitions: list[dict[str, Any]] = []
        for transition in state_data.get("transitions", []):
            if isinstance(transition, ChapterStateTransition):
                from_state = transition.from_state.value if transition.from_state else None
                to_state = transition.to_state.value if transition.to_state else None
                timestamp = (
                    transition.timestamp.isoformat()
                    if isinstance(transition.timestamp, datetime)
                    else transition.timestamp
                )
                error = transition.error
            elif isinstance(transition, dict):
                from_state_raw = transition.get("from_state")
                to_state_raw = transition.get("to_state")
                if isinstance(from_state_raw, ChapterState):
                    from_state = from_state_raw.value
                else:
                    from_state = from_state_raw if isinstance(from_state_raw, str) else None

                if isinstance(to_state_raw, ChapterState):
                    to_state = to_state_raw.value
                else:
                    to_state = to_state_raw if isinstance(to_state_raw, str) else None

                timestamp_raw = transition.get("timestamp")
                timestamp = timestamp_raw.isoformat() if isinstance(timestamp_raw, datetime) else timestamp_raw
                error = transition.get("error")
            else:
                continue

            transitions.append(
                {
                    "from_state": from_state,
                    "to_state": to_state,
                    "timestamp": timestamp,
                    "error": error,
                }
            )

        last_updated_raw = state_data.get("last_updated")
        last_updated = last_updated_raw.isoformat() if isinstance(last_updated_raw, datetime) else last_updated_raw

        return {
            "chapter_id": state_data.get("chapter_id"),
            "current_state": current_state,
            "transitions": transitions,
            "last_updated": last_updated,
            "error_count": int(state_data.get("error_count", 0) or 0),
            "retry_count": int(state_data.get("retry_count", 0) or 0),
        }

    # Disposable runtime state only. Canonical novel content is assigned to
    # the PostgreSQL/R2 functions below after the class definition.
    _get_state_dir = _get_state_dir
    save_chapter_state = save_chapter_state
    load_chapter_state = load_chapter_state
    update_chapter_state = update_chapter_state
    _get_checkpoints_dir = _get_checkpoints_dir
    create_checkpoint = create_checkpoint
    list_checkpoints = list_checkpoints
    restore_from_checkpoint = restore_from_checkpoint
    rollback_to_state = rollback_to_state
    _trace_dir = _trace_dir
    _read_json_file = _read_json_file
    append_pipeline_event = append_pipeline_event
    append_pipeline_events = append_pipeline_events
    list_pipeline_events = list_pipeline_events
    upsert_chunk_state = upsert_chunk_state
    upsert_chunk_states = upsert_chunk_states
    load_chunk_states = load_chunk_states
    save_scheduler_state = save_scheduler_state
    load_scheduler_state = load_scheduler_state
    load_all_scheduler_states = load_all_scheduler_states
    _runtime_dir = _runtime_dir
    _translation_runtime_dir = _translation_runtime_dir
    _fetch_cache_dir = _fetch_cache_dir
    save_translation_chunks = save_translation_chunks
    read_translation_chunks = read_translation_chunks
    update_translation_chunk_status = update_translation_chunk_status
    save_chunk_attempt_record = save_chunk_attempt_record
    cleanup_expired_runtime_data = cleanup_expired_runtime_data
    cleanup_fetch_cache = cleanup_fetch_cache
    cleanup_pipeline_events = cleanup_pipeline_events
    list_chunk_attempt_records = list_chunk_attempt_records
    save_translation_bundle = save_translation_bundle
    read_translation_bundle = read_translation_bundle
    delete_translation_bundle = delete_translation_bundle
    save_translation_output = save_translation_output
    read_translation_output = read_translation_output
    save_provider_request_record = save_provider_request_record
    list_provider_request_records = list_provider_request_records
    save_fetch_cache_entry = save_fetch_cache_entry
    read_fetch_cache_entry = read_fetch_cache_entry
    fetch_cache_conditional_headers = fetch_cache_conditional_headers
    save_translation_run_manifest = save_translation_run_manifest
    load_translation_run_manifest = load_translation_run_manifest


# R2 content operations are exposed through the PostgreSQL catalog and exact R2 references.
# Generation publication is owned by R2GenerationActivationService.


def _build_chapter_payload(
    storage: StorageService,
    novel_id: str,
    chapter_id: str,
    text: str,
    title: str | None = None,
    source_key: str | None = None,
    source_url: str | None = None,
    images: list[dict[str, Any]] | None = None,
    source_blocks: list[dict[str, Any]] | None = None,
    input_adapter_key: str | None = None,
    origin_type: str | None = None,
    origin_uri_or_path: str | None = None,
    document_type: str | None = None,
    unit_type: str | None = None,
    import_order: int | None = None,
    context_group_id: str | None = None,
    region_metadata: list[dict[str, Any]] | None = None,
    ocr_artifacts: list[dict[str, Any]] | None = None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical raw chapter payload before immutable upload."""

    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    existing_raw = existing.get("raw") if isinstance(existing, dict) else None
    existing_raw = existing_raw if isinstance(existing_raw, dict) else None
    payload: dict[str, Any] = {
        "id": safe_chapter_id,
        "title": title if title is not None else (existing.get("title") if isinstance(existing, dict) else None),
        "source_key": source_key,
        "source_url": source_url,
    }
    for key, value in (
        ("input_adapter_key", input_adapter_key),
        ("origin_type", origin_type),
        ("origin_uri_or_path", origin_uri_or_path),
        ("document_type", document_type),
        ("unit_type", unit_type),
        ("context_group_id", context_group_id),
    ):
        if value is not None:
            payload[key] = value
    if import_order is not None:
        payload["import_order"] = int(import_order)
    if region_metadata is not None:
        payload["region_metadata"] = storage._normalize_named_dict_items(region_metadata)
    if ocr_artifacts is not None:
        payload["ocr_artifacts"] = storage._normalize_named_dict_items(ocr_artifacts)
    resolved_images = (
        existing_raw.get("images")
        if images is None and existing_raw is not None and existing_raw.get("images") is not None
        else storage._normalize_image_manifest(images)
    )
    raw: dict[str, Any] = {
        "id": safe_chapter_id,
        "scraped_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "text": text,
        "paragraphs": storage._text_paragraphs(text),
        "images": resolved_images,
    }
    if source_blocks is not None:
        raw["source_blocks"] = storage._normalize_source_blocks(source_blocks)
    elif existing_raw is not None and existing_raw.get("source_blocks") is not None:
        raw["source_blocks"] = existing_raw.get("source_blocks")
    payload["raw"] = raw
    return payload


def _existing_chapter_hash(storage: StorageService, novel_id: str, chapter_id: str) -> str | None:
    chapter = storage.load_chapter(novel_id, chapter_id)
    text = chapter.get("text") if isinstance(chapter, dict) else None
    return storage._hash_text(text) if isinstance(text, str) else None


def _query_chapters(storage: StorageService, novel_id: str) -> Any:
    from novelai.services.query_builder import ChapterQueryBuilder

    state_dir = storage._get_state_dir(novel_id)
    return ChapterQueryBuilder(
        state_dir,
        path_exists=lambda: storage._is_dir_present(state_dir),
        list_files=lambda: storage._glob(state_dir, "*.json"),
        read_file=lambda path: storage._read_text(path),
    )


def _get_chapters_by_state(storage: StorageService, novel_id: str, state: ChapterState) -> list[str]:
    return [result.chapter_id for result in _query_chapters(storage, novel_id).by_state(state).execute()]


def _get_chapter_progress(storage: StorageService, novel_id: str) -> dict[str, int]:
    from novelai.core.chapter_state import ChapterState

    return {state.value: _query_chapters(storage, novel_id).by_state(state).count() for state in ChapterState}


def _get_chapters_with_errors(storage: StorageService, novel_id: str, limit: int = 100) -> list[str]:
    return [
        result.chapter_id
        for result in _query_chapters(storage, novel_id)
        .has_errors()
        .sort_by("errors", reverse=True)
        .limit(limit)
        .execute()
    ]


def _get_scraping_progress(storage: StorageService, novel_id: str) -> dict[str, Any]:
    results = _query_chapters(storage, novel_id).execute()
    error_count = sum(1 for result in results if result.error_count > 0)
    total = len(results)
    return {
        "total": total,
        "by_state": _get_chapter_progress(storage, novel_id),
        "with_errors": error_count,
        "success_rate": ((total - error_count) / total * 100) if total else 0.0,
    }


StorageService.build_chapter_payload = _build_chapter_payload  # type: ignore[method-assign]
StorageService.existing_chapter_hash = _existing_chapter_hash  # type: ignore[method-assign]
StorageService.get_chapters_by_state = _get_chapters_by_state  # type: ignore[method-assign]
StorageService.get_chapter_progress = _get_chapter_progress  # type: ignore[method-assign]
StorageService.query_chapters = _query_chapters  # type: ignore[method-assign]
StorageService.get_chapters_with_errors = _get_chapters_with_errors  # type: ignore[method-assign]
StorageService.get_scraping_progress = _get_scraping_progress  # type: ignore[method-assign]
StorageService.delete_novel = _r2_delete_novel  # type: ignore[method-assign]
StorageService.get_novel_chapter_summary = _r2_get_novel_chapter_summary  # type: ignore[method-assign]
StorageService.list_metadata_history = _r2_list_metadata_history  # type: ignore[method-assign]
StorageService.load_metadata_snapshot = _r2_load_metadata_snapshot  # type: ignore[method-assign]
StorageService.save_metadata = _r2_save_metadata  # type: ignore[method-assign]
StorageService.load_glossary = _r2_load_glossary  # type: ignore[method-assign]
StorageService.save_glossary = _r2_save_glossary  # type: ignore[method-assign]
StorageService.load_metadata = _r2_load_metadata  # type: ignore[method-assign]
StorageService.load_metadata_for_crawl = _r2_load_metadata  # type: ignore[method-assign]
StorageService.save_source_state = _r2_save_source_state  # type: ignore[method-assign]
StorageService.load_source_state = _r2_load_source_state  # type: ignore[method-assign]
StorageService.update_onboarding_status = _r2_update_onboarding_status  # type: ignore[method-assign]
StorageService.resolve_onboarding_status = _r2_resolve_onboarding_status  # type: ignore[method-assign]
StorageService.list_novels = _r2_list_novels  # type: ignore[method-assign]
StorageService.resolve_active_generation_id = _r2_resolve_active_generation_id  # type: ignore[method-assign]
StorageService.save_chapter = _r2_save_chapter  # type: ignore[method-assign]
StorageService.load_chapter = _r2_load_chapter  # type: ignore[method-assign]
StorageService.list_stored_chapters = _r2_list_stored_chapters  # type: ignore[method-assign]
StorageService.count_stored_chapters = _r2_count_stored_chapters  # type: ignore[method-assign]
StorageService.save_translated_chapter = _r2_save_translated_chapter  # type: ignore[method-assign]
StorageService.load_translated_chapter = _r2_load_translated_chapter  # type: ignore[method-assign]
StorageService.load_translated_chapter_by_version_id = _r2_load_translated_chapter_by_version_id  # type: ignore[method-assign]
StorageService.list_translated_chapter_versions = _r2_list_translated_chapter_versions  # type: ignore[method-assign]
StorageService.save_edited_translation = _r2_save_edited_translation  # type: ignore[method-assign]
StorageService.load_translation_edit_history = _r2_load_translation_edit_history  # type: ignore[method-assign]
StorageService.activate_translated_chapter_version = _r2_activate_translated_chapter_version  # type: ignore[method-assign]
StorageService.list_translated_chapters = _r2_list_translated_chapters  # type: ignore[method-assign]
StorageService.count_translated_chapters = _r2_count_translated_chapters  # type: ignore[method-assign]
StorageService.load_chapter_media_state = _r2_load_chapter_media_state  # type: ignore[method-assign]
StorageService.save_chapter_media_state = _r2_save_chapter_media_state  # type: ignore[method-assign]
StorageService.save_chapter_image_asset = _r2_save_chapter_image_asset  # type: ignore[method-assign]
StorageService.clear_chapter_image_assets = _r2_clear_chapter_image_assets  # type: ignore[method-assign]
StorageService.resolve_asset_path = _r2_resolve_asset_path  # type: ignore[method-assign]

"""Staged generations with manifest-last atomic activation (DEBT-GEN-01).

A generation is an immutable snapshot of a crawl run: staged chapters,
images, metadata, chapter index, and source state, tracked by a manifest
that is written *last* before the ``active_generation.json`` pointer is
swapped. Readers resolve the active generation through the pointer and fall
back to the legacy novel-directory layout when no generation exists, so
existing novels keep working unchanged.

Failed or cancelled crawls call :func:`rollback_generation`, which removes
the stage and leaves the previously active generation (or legacy layout)
untouched.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_utf8(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass
class GenerationManifest:
    """Manifest tracking a staged generation run matching Section 8 requirements."""

    generation_id: str
    novel_id: str
    source_key: str = ""
    source_work_id: str = ""
    mode: str = "update"  # "update" or "full"
    created_at: str = field(default_factory=_utc_now_iso)
    committed_at: str | None = None
    activated_at: str | None = None
    rolled_back_at: str | None = None
    status: str = "staging"  # "staging", "committed", "active", "failed"
    metadata_fingerprint: str = ""
    index_fingerprint: str = ""
    metadata_hash: str = ""
    chapter_index_hash: str = ""
    source_state_hash: str = ""
    expected_chapters: int = 0
    saved_chapters: int = 0
    reused_chapters: int = 0
    failed_chapters: int = 0
    removed_episode_ids: list[str] = field(default_factory=list)
    chapter_ids: list[str] = field(default_factory=list)
    source_hashes: dict[str, str] = field(default_factory=dict)
    structure_hashes: dict[str, str] = field(default_factory=dict)
    image_manifest_hashes: dict[str, str] = field(default_factory=dict)
    parser_versions: dict[str, str] = field(default_factory=dict)
    translation_versions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenerationManifest:
        return cls(
            generation_id=str(data.get("generation_id", "")),
            novel_id=str(data.get("novel_id", "")),
            source_key=str(data.get("source_key", "")),
            source_work_id=str(data.get("source_work_id", "")),
            mode=str(data.get("mode", "update")),
            created_at=str(data.get("created_at", _utc_now_iso())),
            committed_at=data.get("committed_at"),
            activated_at=data.get("activated_at"),
            rolled_back_at=data.get("rolled_back_at"),
            status=str(data.get("status", "staging")),
            metadata_fingerprint=str(data.get("metadata_fingerprint", "")),
            index_fingerprint=str(data.get("index_fingerprint", "")),
            metadata_hash=str(data.get("metadata_hash", "")),
            chapter_index_hash=str(data.get("chapter_index_hash", "")),
            source_state_hash=str(data.get("source_state_hash", "")),
            expected_chapters=int(data.get("expected_chapters", 0)),
            saved_chapters=int(data.get("saved_chapters", 0)),
            reused_chapters=int(data.get("reused_chapters", 0)),
            failed_chapters=int(data.get("failed_chapters", 0)),
            removed_episode_ids=list(data.get("removed_episode_ids", [])),
            chapter_ids=list(data.get("chapter_ids", [])),
            source_hashes=dict(data.get("source_hashes", {})),
            structure_hashes=dict(data.get("structure_hashes", {})),
            image_manifest_hashes=dict(data.get("image_manifest_hashes", {})),
            parser_versions=dict(data.get("parser_versions", {})),
            translation_versions=dict(data.get("translation_versions", {})),
        )


def _generations_dir(self: Any, novel_id: str) -> Path:
    novel_dir = self._novel_dir(novel_id)
    g_dir = novel_dir / "generations"
    self._mkdirs(g_dir)
    return g_dir


def _generation_dir(self: Any, novel_id: str, generation_id: str) -> Path:
    return self._generations_dir(novel_id) / generation_id


def _manifest_path(self: Any, novel_id: str, generation_id: str) -> Path:
    return self._generation_dir(novel_id, generation_id) / "generation_manifest.json"


def _load_manifest(self: Any, novel_id: str, generation_id: str) -> GenerationManifest | None:
    manifest_path = _manifest_path(self, novel_id, generation_id)
    if not self._path_exists(manifest_path):
        return None
    try:
        return GenerationManifest.from_dict(json.loads(self._read_text(manifest_path)))
    except Exception as exc:
        logger.warning("Failed to load generation manifest for %s/%s: %s", novel_id, generation_id, exc)
        return None


def _save_manifest(self: Any, novel_id: str, generation_id: str, manifest: GenerationManifest) -> None:
    manifest_path = _manifest_path(self, novel_id, generation_id)
    self._write_text_atomic(manifest_path, json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))


def create_generation_stage(
    self: Any,
    novel_id: str,
    generation_id: str,
    *,
    source_key: str = "",
    source_work_id: str = "",
    mode: str = "update",
    expected_chapters: int = 0,
    metadata_fingerprint: str = "",
    index_fingerprint: str = "",
) -> GenerationManifest:
    """Create a new staged generation directory and initial manifest."""
    g_dir = self._generation_dir(novel_id, generation_id)
    self._mkdirs(g_dir)
    manifest = GenerationManifest(
        generation_id=generation_id,
        novel_id=novel_id,
        source_key=source_key,
        source_work_id=source_work_id,
        mode=mode,
        expected_chapters=expected_chapters,
        metadata_fingerprint=metadata_fingerprint,
        index_fingerprint=index_fingerprint,
        status="staging",
    )
    _save_manifest(self, novel_id, generation_id, manifest)
    return manifest


def load_generation_manifest(
    self: Any,
    novel_id: str,
    generation_id: str,
) -> GenerationManifest | None:
    """Load a generation manifest if it exists."""
    return _load_manifest(self, novel_id, generation_id)


def get_active_generation(
    self: Any,
    novel_id: str,
) -> GenerationManifest | None:
    """Return the active generation manifest for a novel."""
    active_pointer_path = self._generations_dir(novel_id) / "active_generation.json"
    if not self._path_exists(active_pointer_path):
        return None
    try:
        data = json.loads(self._read_text(active_pointer_path))
        gen_id = data.get("active_generation_id")
        return self.load_generation_manifest(novel_id, gen_id) if gen_id else None
    except Exception as exc:
        logger.warning("Failed to read active_generation for %s: %s", novel_id, exc)
        return None


def list_generations(self: Any, novel_id: str) -> list[GenerationManifest]:
    """Return manifests for all generations of a novel (newest first)."""
    g_dir = self._generations_dir(novel_id)
    manifests: list[GenerationManifest] = []
    if not self._is_dir_present(g_dir):
        return manifests
    for entry in self._list_dir(g_dir):
        if not entry.is_dir() or entry.name == "active_generation.json":
            continue
        manifest = _load_manifest(self, novel_id, entry.name)
        if manifest is not None:
            manifests.append(manifest)
    manifests.sort(key=lambda m: m.created_at, reverse=True)
    return manifests


# ── staged content writes ────────────────────────────────────────────────


def _stage_dir(self: Any, novel_id: str, generation_id: str, *parts: str) -> Path:
    """Return a staged subdirectory, creating it when needed.

    Every ``part`` must be a directory component; file paths must use
    :func:`_stage_file` so the final component is never mistaken for a
    directory.
    """
    path = self._generation_dir(novel_id, generation_id).joinpath(*parts)
    self._mkdirs(path)
    return path


def _stage_file(self: Any, novel_id: str, generation_id: str, *parts: str) -> Path:
    """Return a staged file path, creating its parent directory when needed."""
    path = self._generation_dir(novel_id, generation_id).joinpath(*parts)
    self._mkdirs(path.parent)
    return path


def stage_generation_metadata(self: Any, novel_id: str, generation_id: str, meta: dict[str, Any]) -> str:
    """Stage the metadata snapshot used by the crawl run."""
    path = _stage_file(self, novel_id, generation_id, "metadata.json")
    content = json.dumps(meta, ensure_ascii=False, indent=2)
    self._write_text_atomic(path, content)
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is not None:
        manifest.metadata_hash = _sha256_utf8(content)
        _save_manifest(self, novel_id, generation_id, manifest)
    return manifest.metadata_hash if manifest is not None else _sha256_utf8(content)


def stage_generation_chapter_index(
    self: Any,
    novel_id: str,
    generation_id: str,
    chapter_index: list[dict[str, Any]],
) -> str:
    """Stage the chapter index snapshot used by the crawl run."""
    path = _stage_file(self, novel_id, generation_id, "chapter_index.json")
    content = json.dumps(chapter_index, ensure_ascii=False, indent=2)
    self._write_text_atomic(path, content)
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is not None:
        manifest.chapter_index_hash = _sha256_utf8(content)
        _save_manifest(self, novel_id, generation_id, manifest)
    return manifest.chapter_index_hash if manifest is not None else _sha256_utf8(content)


def stage_generation_source_state(
    self: Any,
    novel_id: str,
    generation_id: str,
    source_state: dict[str, Any],
) -> str:
    """Stage the source-state snapshot used by the crawl run."""
    path = _stage_file(self, novel_id, generation_id, "source_state.json")
    content = json.dumps(source_state, ensure_ascii=False, indent=2)
    self._write_text_atomic(path, content)
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is not None:
        manifest.source_state_hash = _sha256_utf8(content)
        _save_manifest(self, novel_id, generation_id, manifest)
    return manifest.source_state_hash if manifest is not None else _sha256_utf8(content)


def stage_generation_chapter(
    self: Any,
    novel_id: str,
    generation_id: str,
    chapter_id: str,
    payload: dict[str, Any],
    *,
    source_hash: str | None = None,
    structure_hash: str | None = None,
    image_manifest_hash: str | None = None,
    parser_version: str | None = None,
    translation_version: str | None = None,
) -> Path:
    """Stage one chapter bundle into a generation snapshot.

    ``payload`` is a current-schema chapter bundle as produced by
    ``save_chapter`` (raw + translation versions + media fields). The
    manifest is updated with hashes and counts after the bundle write.
    """
    self._normalize_media_fields(payload)
    payload["schema_version"] = self.SCHEMA_VERSION
    physical = _physical_chapter_filename(self, chapter_id)
    path = _stage_dir(self, novel_id, generation_id, "chapters") / physical
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    self._write_text_atomic(path, content)

    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is None:
        manifest = create_generation_stage(self, novel_id, generation_id)
    if chapter_id not in manifest.chapter_ids:
        manifest.chapter_ids.append(chapter_id)
    if source_hash:
        manifest.source_hashes[chapter_id] = source_hash
    if structure_hash:
        manifest.structure_hashes[chapter_id] = structure_hash
    if image_manifest_hash:
        manifest.image_manifest_hashes[chapter_id] = image_manifest_hash
    if parser_version:
        manifest.parser_versions[chapter_id] = parser_version
    if translation_version:
        manifest.translation_versions[chapter_id] = translation_version
    _save_manifest(self, novel_id, generation_id, manifest)
    return path


def stage_generation_image(
    self: Any,
    novel_id: str,
    generation_id: str,
    chapter_id: str,
    *,
    image_index: int,
    content: bytes,
    source_url: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    """Stage one chapter image asset into a generation snapshot.

    Asset layout inside the generation directory is::

        generations/<generation_id>/
            assets/
                images/
                    <encoded_chapter_stem>/
                        0000.jpg

    The asset directory uses the chapter's encoded physical stem — never the
    chapter bundle filename ``<stem>.json`` — so the directory tree stays
    independent of any ``.json`` suffix and remains Windows-safe for stable
    ids such as ``kakuyomu%3A<episode_id>``.

    The returned ``local_path`` is the logical, generation-agnostic form
    (``assets/images/<encoded_stem>/<filename>``); readers resolve it against
    the active generation via :func:`resolve_asset_path`.
    """
    # Late import: the chapter-identity codec is the canonical source of
    # physical stems and lives in core.security; storage imports are kept
    # minimal here.
    from novelai.core.security import encode_physical_stem, validate_storage_identifier

    suffix = self._guess_asset_suffix(source_url, content_type)
    filename = f"{image_index:04d}{suffix}"
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    encoded_stem = encode_physical_stem(safe_chapter_id)
    path = _stage_dir(self, novel_id, generation_id, "assets", "images", encoded_stem) / filename
    self._backend.save(self._rel(path), content)
    return {
        "local_path": f"assets/images/{encoded_stem}/{filename}",
        "content_type": content_type,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _physical_chapter_filename(self: Any, chapter_id: str) -> str:
    """Reuse the canonical chapter bundle filename mapping."""
    from novelai.storage.chapters import _chapter_filename

    return _chapter_filename(chapter_id)


def seed_generation_from_active(
    self: Any,
    novel_id: str,
    generation_id: str,
    chapter_ids: list[str],
) -> tuple[int, int]:
    """Copy existing chapter bundles and image assets into a staged generation.

    Used for chapters the planner reuses or that are unchanged: the stage
    must contain a complete snapshot, so existing raw + translation content
    is carried forward. Returns ``(copied_chapters, copied_assets)``.
    """
    copied_chapters = 0
    copied_assets = 0
    for chapter_id in chapter_ids:
        existing = self._load_chapter_bundle(novel_id, chapter_id)
        if existing is None:
            continue
        stage_generation_chapter(
            self,
            novel_id,
            generation_id,
            chapter_id,
            existing,
            source_hash=self._hash_text(str(existing.get("raw", {}).get("text", "")))
            if isinstance(existing.get("raw"), dict) and isinstance(existing.get("raw", {}).get("text"), str)
            else None,
        )
        copied_chapters += 1
        existing_images = existing.get("raw", {}).get("images")
        if isinstance(existing_images, list):
            for image in existing_images:
                local_path = image.get("local_path") if isinstance(image, dict) else None
                if not isinstance(local_path, str) or not local_path.strip():
                    continue
                copied_assets += self._copy_asset_to_generation(novel_id, generation_id, local_path)
    return copied_chapters, copied_assets


def _copy_asset_to_generation(self: Any, novel_id: str, generation_id: str, local_path: str) -> int:
    """Copy one stored asset (by ``local_path``) into a generation snapshot."""
    source_path = self.resolve_asset_path(novel_id, local_path)
    if source_path is None or not self._path_exists(source_path):
        return 0
    relative = Path(local_path).as_posix().removeprefix("assets/")
    target = _stage_file(self, novel_id, generation_id, "assets", relative)
    content = self._backend.load(self._rel(source_path))
    self._backend.save(self._rel(target), content)
    return 1


def record_staged_chapter(
    self: Any,
    novel_id: str,
    generation_id: str,
    chapter_id: str,
    version_id: str,
    source_hash: str | None = None,
) -> GenerationManifest:
    """Record a completed chapter in the staged generation manifest.

    Compatibility entry point for callers that only track chapter metadata
    without writing a bundle; prefer :func:`stage_generation_chapter`.
    """
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is None:
        manifest = create_generation_stage(self, novel_id, generation_id)
    if chapter_id not in manifest.chapter_ids:
        manifest.chapter_ids.append(chapter_id)
    manifest.translation_versions[chapter_id] = version_id
    if source_hash:
        manifest.source_hashes[chapter_id] = source_hash
    _save_manifest(self, novel_id, generation_id, manifest)
    return manifest


# ── commit / activation / rollback ───────────────────────────────────────


def commit_generation(
    self: Any,
    novel_id: str,
    generation_id: str,
    *,
    removed_episode_ids: list[str] | None = None,
    reused_chapters: int = 0,
    failed_chapters: int = 0,
) -> GenerationManifest:
    """Finalize a staged generation and atomically activate it.

    The manifest is written with its final counts and ``committed`` status
    *before* the ``active_generation.json`` pointer is swapped, so readers
    can never observe a partially recorded snapshot as active. The manifest
    keeps the ``committed`` status after activation; the pointer itself is
    the active marker.
    """
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is None:
        raise FileNotFoundError(f"Generation manifest for {novel_id}/{generation_id} not found.")

    if removed_episode_ids:
        manifest.removed_episode_ids = sorted(set(removed_episode_ids))
    manifest.reused_chapters = reused_chapters
    manifest.failed_chapters = failed_chapters
    manifest.status = "committed"
    manifest.committed_at = manifest.committed_at or _utc_now_iso()
    manifest.activated_at = manifest.activated_at or manifest.committed_at

    # Manifest-last write: content + manifest are durable before activation.
    _save_manifest(self, novel_id, generation_id, manifest)

    active_pointer_path = self._generations_dir(novel_id) / "active_generation.json"
    self._write_text_atomic(
        active_pointer_path,
        json.dumps(
            {
                "novel_id": novel_id,
                "active_generation_id": generation_id,
                "activated_at": manifest.activated_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    return manifest


def activate_generation(
    self: Any,
    novel_id: str,
    generation_id: str,
) -> GenerationManifest:
    """Atomically activate a staged generation (alias kept for compatibility)."""
    return commit_generation(self, novel_id, generation_id)


def rollback_generation(
    self: Any,
    novel_id: str,
    generation_id: str,
    *,
    reason: str = "crawl failed",
) -> None:
    """Discard a staged generation and preserve the previously active state.

    Marks the manifest as failed (when it exists), then removes the stage
    directory. The ``active_generation.json`` pointer is untouched, so the
    previous active generation (or the legacy layout) stays in effect.
    """
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is not None:
        manifest.status = "failed"
        manifest.rolled_back_at = _utc_now_iso()
        _save_manifest(self, novel_id, generation_id, manifest)
    g_dir = self._generation_dir(novel_id, generation_id)
    if self._path_exists(g_dir):
        self._rmtree(g_dir)
    logger.warning("Rolled back generation %s for %s (%s).", generation_id, novel_id, reason)

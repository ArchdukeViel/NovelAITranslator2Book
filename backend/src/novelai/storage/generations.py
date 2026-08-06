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
    unavailable_chapter_ids: list[str] = field(default_factory=list)
    unavailable_chapter_records: dict[str, dict[str, Any]] = field(default_factory=dict)
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
            unavailable_chapter_ids=list(data.get("unavailable_chapter_ids", [])),
            unavailable_chapter_records=dict(data.get("unavailable_chapter_records", {})),
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


def resolve_active_generation_id(self: Any, novel_id: str) -> str | None:
    """Return the raw active generation_id (no manifest lookup)."""
    active_pointer_path = self._generations_dir(novel_id) / "active_generation.json"
    if not self._path_exists(active_pointer_path):
        return None
    try:
        data = json.loads(self._read_text(active_pointer_path))
        gen_id = data.get("active_generation_id")
        return str(gen_id) if isinstance(gen_id, str) and gen_id.strip() else None
    except Exception as exc:
        logger.warning("Failed to read active_generation pointer for %s: %s", novel_id, exc)
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


def record_unavailable_chapter(
    self: Any,
    novel_id: str,
    generation_id: str,
    chapter_id: str,
    *,
    reason: str = "",
    error_category: str = "",
) -> GenerationManifest:
    """Record an explicit unavailable marker for a chapter in the stage.

    Section 3: a chapter that failed acquisition is not silently omitted.
    Section 4: the manifest holds an explicit list of unavailable chapters
    so the pre-activation validator can verify every index entry has either
    a bundle or an explicit unavailable record.
    """
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is None:
        manifest = create_generation_stage(self, novel_id, generation_id)
    if chapter_id not in manifest.unavailable_chapter_ids:
        manifest.unavailable_chapter_ids.append(chapter_id)
    manifest.unavailable_chapter_records[chapter_id] = {
        "chapter_id": chapter_id,
        "reason": reason,
        "error_category": error_category,
        "recorded_at": _utc_now_iso(),
    }
    _save_manifest(self, novel_id, generation_id, manifest)
    return manifest


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


@dataclass(frozen=True)
class _CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class GenerationValidationResult:
    is_valid: bool
    checks: list[_CheckResult]

    def failed_checks(self) -> list[_CheckResult]:
        return [check for check in self.checks if not check.passed]


def _check(name: str, passed: bool, detail: str = "") -> _CheckResult:
    return _CheckResult(name=name, passed=bool(passed), detail=detail)


def _read_json_or_none(self: Any, path: Path) -> Any | None:
    if not self._path_exists(path):
        return None
    try:
        return json.loads(self._read_text(path))
    except Exception:
        return None


def _chapter_filename_for(chapter_id: str) -> str:
    from novelai.storage.chapters import _chapter_filename

    return _chapter_filename(chapter_id)


def _index_entry_logical_id(entry: dict[str, Any]) -> str:
    """Normalize a chapter-index entry's id to the logical chapter_id.

    Mirrors ``novelai.utils.chapter_selection._chapter_logical_id``:
    adapters may emit ``"id"`` as a string or an integer, while every
    downstream storage call uses the stringified logical id. The index
    snapshot preserves the raw adapter spelling (``json.dumps`` keeps
    integers), so validation must normalize before comparing against
    physical bundle ids and ``manifest.chapter_ids``.
    """
    for key in ("id", "chapter_id"):
        raw = entry.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        if isinstance(raw, int):
            return str(raw)
    return ""


def validate_generation_activation(
    self: Any,
    novel_id: str,
    generation_id: str,
) -> GenerationValidationResult:
    """Run deterministic pre-activation validation (Section 4 contract).

    Returns a :class:`GenerationValidationResult` describing all checks
    performed. The default contract rolls the stage back when the result
    is invalid; callers may inspect the result to surface why in logs and
    tests.
    """
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is None:
        return GenerationValidationResult(
            is_valid=False,
            checks=[_check("manifest_exists", False, "Generation manifest not found.")],
        )
    checks: list[_CheckResult] = []
    checks.append(
        _check(
            "manifest_status_staging",
            manifest.status in {"staging", "committed"},
            f"manifest.status={manifest.status!r}",
        )
    )

    g_dir = self._generation_dir(novel_id, generation_id)
    metadata_path = g_dir / "metadata.json"
    index_path = g_dir / "chapter_index.json"
    source_state_path = g_dir / "source_state.json"

    metadata = _read_json_or_none(self, metadata_path)
    checks.append(_check("metadata_present", metadata is not None, f"{metadata_path} missing or empty"))
    if metadata is not None:
        expected_work_id = str(manifest.source_work_id or "")
        actual_work_id = str(metadata.get("source_novel_id") or "")
        # Section 4: when the manifest does not declare a source_work_id
        # (legacy callers that pre-date work-id propagation) the check
        # degrades to "metadata must declare a source_novel_id at all" so
        # we never silently accept an empty identity.
        if expected_work_id:
            checks.append(
                _check(
                    "metadata_identity_match",
                    actual_work_id == expected_work_id,
                    f"metadata.source_novel_id={actual_work_id!r} != manifest.source_work_id={expected_work_id!r}",
                )
            )
        else:
            checks.append(
                _check(
                    "metadata_declares_source_novel_id",
                    bool(actual_work_id),
                    f"metadata.source_novel_id={actual_work_id!r} is empty",
                )
            )

    chapter_index = _read_json_or_none(self, index_path) or []
    checks.append(_check("chapter_index_present", bool(chapter_index), f"{index_path} missing"))
    index_count = len(chapter_index) if isinstance(chapter_index, list) else 0

    source_state = _read_json_or_none(self, source_state_path)
    checks.append(
        _check(
            "source_state_present",
            source_state is not None,
            f"{source_state_path} missing or empty",
        )
    )

    chapter_dir = g_dir / "chapters"
    physical_chapter_ids: set[str] = set()
    if self._path_exists(chapter_dir):
        for physical_path in self._glob(chapter_dir, "*.json"):
            stem = physical_path.stem
            try:
                physical_chapter_ids.add(self.logical_id_from_stem(stem))
            except Exception:
                continue
    checks.append(
        _check(
            "expected_membership_matches_complete_index",
            manifest.expected_chapters <= index_count,
            f"expected_chapters={manifest.expected_chapters} must be <= complete chapter_index size={index_count}",
        )
    )

    missing_bundles: list[str] = []
    if isinstance(chapter_index, list):
        unavailable_ids = set(manifest.unavailable_chapter_ids or [])
        for entry in chapter_index:
            if not isinstance(entry, dict):
                continue
            cid = _index_entry_logical_id(entry)
            if not cid:
                continue
            if cid in physical_chapter_ids:
                continue
            if cid in unavailable_ids:
                continue
            missing_bundles.append(cid)
    checks.append(
        _check(
            "every_index_entry_resolved",
            not missing_bundles,
            f"Missing bundles for {len(missing_bundles)} indexed chapters",
        )
    )

    missing_assets: list[str] = []
    if isinstance(chapter_index, list):
        for entry in chapter_index:
            if not isinstance(entry, dict):
                continue
            cid = _index_entry_logical_id(entry)
            if not cid:
                continue
            chapter_path = chapter_dir / _chapter_filename_for(cid)
            if not self._path_exists(chapter_path):
                continue
            bundle = _read_json_or_none(self, chapter_path)
            if not isinstance(bundle, dict):
                continue
            raw_section = bundle.get("raw")
            raw: dict[str, Any] = raw_section if isinstance(raw_section, dict) else {}
            images_value = raw.get("images")
            images = images_value if isinstance(images_value, list) else []
            for image in images:
                if not isinstance(image, dict):
                    continue
                local_path = image.get("local_path")
                if not isinstance(local_path, str) or not local_path.strip():
                    continue
                # The ``local_path`` is already a generation-relative
                # logical key (``assets/images/<encoded_stem>/<file>``).
                # Resolve it relative to the stage root (``g_dir``), not
                # the nested ``assets/`` directory, so the validation
                # path matches the layout used during staging.
                if not (g_dir / local_path).exists():
                    missing_assets.append(local_path)
    checks.append(
        _check(
            "every_referenced_image_resolves_inside_stage",
            not missing_assets,
            f"{len(missing_assets)} referenced images do not resolve inside the stage",
        )
    )

    metadata_text = self._read_text(metadata_path) if self._path_exists(metadata_path) else ""
    chapter_index_text = self._read_text(index_path) if self._path_exists(index_path) else ""
    source_state_text = self._read_text(source_state_path) if self._path_exists(source_state_path) else ""
    checks.append(
        _check(
            "manifest_metadata_hash_matches_stage",
            bool(metadata_text)
            and bool(manifest.metadata_hash)
            and manifest.metadata_hash == _sha256_utf8(metadata_text),
            "manifest.metadata_hash is empty or does not match staged metadata.json",
        )
    )
    checks.append(
        _check(
            "manifest_index_hash_matches_stage",
            bool(chapter_index_text)
            and bool(manifest.chapter_index_hash)
            and manifest.chapter_index_hash == _sha256_utf8(chapter_index_text),
            "manifest.chapter_index_hash is empty or does not match staged chapter_index.json",
        )
    )
    checks.append(
        _check(
            "manifest_source_state_hash_matches_stage",
            bool(source_state_text)
            and bool(manifest.source_state_hash)
            and manifest.source_state_hash == _sha256_utf8(source_state_text),
            "manifest.source_state_hash is empty or does not match staged source_state.json",
        )
    )

    # Reconcile manifest.chapter_ids against the *physical* bundles only;
    # seeding the seen-set with the manifest ids made the old check a
    # tautology that could never fail.
    physical_ids_in_index: set[str] = set()
    if isinstance(chapter_index, list):
        for entry in chapter_index:
            if not isinstance(entry, dict):
                continue
            cid = _index_entry_logical_id(entry)
            if cid and cid in physical_chapter_ids:
                physical_ids_in_index.add(cid)
    checks.append(
        _check(
            "manifest_chapter_ids_reconcile_with_files",
            set(manifest.chapter_ids or []).issubset(physical_ids_in_index),
            "manifest.chapter_ids include chapters that have no physical bundle",
        )
    )

    is_valid = all(check.passed for check in checks)
    return GenerationValidationResult(is_valid=is_valid, checks=checks)


def commit_generation(
    self: Any,
    novel_id: str,
    generation_id: str,
    *,
    removed_episode_ids: list[str] | None = None,
    reused_chapters: int = 0,
    failed_chapters: int = 0,
    skip_validation: bool = False,
) -> GenerationManifest:
    """Finalize a staged generation and atomically activate it.

    The manifest is written with its final counts and ``committed`` status
    *before* the ``active_generation.json`` pointer is swapped, so readers
    can never observe a partially recorded snapshot as active. The manifest
    keeps the ``committed`` status after activation; the pointer itself is
    the active marker.

    Section 4: run :func:`validate_generation_activation` before swapping
    the active pointer so partial / corrupt / membership-incomplete
    generations never become visible. Tests can pass ``skip_validation=True``
    to inspect the failure surface without engaging the rollback path.
    """
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is None:
        raise FileNotFoundError(f"Generation manifest for {novel_id}/{generation_id} not found.")

    if removed_episode_ids:
        manifest.removed_episode_ids = sorted(set(removed_episode_ids))
    manifest.reused_chapters = reused_chapters
    manifest.failed_chapters = failed_chapters
    manifest.saved_chapters = max(
        int(getattr(manifest, "saved_chapters", 0) or 0),
        len(manifest.chapter_ids or []),
    )
    manifest.status = "staging"
    manifest.committed_at = manifest.committed_at or _utc_now_iso()

    if not skip_validation:
        result = validate_generation_activation(self, novel_id, generation_id)
        if not result.is_valid:
            failed_names = ", ".join(check.name for check in result.failed_checks())
            logger.error(
                "Generation %s for %s failed validation: %s",
                generation_id,
                novel_id,
                failed_names,
            )
            raise RuntimeError(
                f"Generation {generation_id} for {novel_id} failed pre-activation validation: {failed_names}"
            )

    manifest.status = "committed"
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

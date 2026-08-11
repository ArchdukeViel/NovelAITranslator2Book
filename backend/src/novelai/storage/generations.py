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

from novelai.core.security import safe_child_path

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_utf8(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json_hash(value: Any) -> str:
    """SHA256 of a JSON-stable serialization (canonical for structure/manifest hashes)."""
    return _sha256_utf8(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


def _bundle_raw_text(payload: dict[str, Any]) -> str:
    raw_section = payload.get("raw")
    raw = raw_section if isinstance(raw_section, dict) else {}
    text = raw.get("text")
    return text if isinstance(text, str) else ""


def _bundle_source_blocks(payload: dict[str, Any]) -> list[Any]:
    raw_section = payload.get("raw")
    raw = raw_section if isinstance(raw_section, dict) else {}
    blocks = raw.get("source_blocks")
    return blocks if isinstance(blocks, list) else []


def _bundle_images(payload: dict[str, Any]) -> list[Any]:
    raw_section = payload.get("raw")
    raw = raw_section if isinstance(raw_section, dict) else {}
    images = raw.get("images")
    return images if isinstance(images, list) else []


def _canonical_bundle_hashes(payload: dict[str, Any]) -> tuple[str, str, str]:
    """Canonical per-chapter hashes computed from a staged bundle.

    ``source_hash`` hashes the raw text, ``structure_hash`` the normalized
    ``source_blocks`` list, and ``image_manifest_hash`` the ``images`` list.
    All three are derived exclusively from the bundle itself so the
    pre-activation validator can recompute them deterministically for every
    physical bundle (seeded or freshly fetched) and reject an empty hash.
    """
    return (
        _sha256_utf8(_bundle_raw_text(payload)),
        _canonical_json_hash(_bundle_source_blocks(payload)),
        _canonical_json_hash(_bundle_images(payload)),
    )


# Canonical chapter-disposition names. Every current-index chapter must end
# the crawl with exactly one of these dispositions so the activation
# validator can derive aggregate counts and reconcile them against the
# physical staged state.
DISPOSITION_FETCHED_NEW = "fetched_new"
DISPOSITION_FETCHED_REPLACED = "fetched_replaced"
DISPOSITION_REUSED_PLANNER = "reused_planner"
DISPOSITION_CARRIED_UNSELECTED = "carried_unselected"
DISPOSITION_UNCHANGED_SELECTED = "unchanged_selected"
DISPOSITION_REFRESH_FAILED_RETAINED = "refresh_failed_retained"
DISPOSITION_UNAVAILABLE = "unavailable"

# The canonical set of every disposition a current-index chapter may end the
# crawl with. Validation rejects any other value; an empty map is rejected
# too, so reconciliation can never be silently disabled.
ALL_CHAPTER_DISPOSITIONS: frozenset[str] = frozenset(
    {
        DISPOSITION_FETCHED_NEW,
        DISPOSITION_FETCHED_REPLACED,
        DISPOSITION_REUSED_PLANNER,
        DISPOSITION_CARRIED_UNSELECTED,
        DISPOSITION_UNCHANGED_SELECTED,
        DISPOSITION_REFRESH_FAILED_RETAINED,
        DISPOSITION_UNAVAILABLE,
    }
)


def derive_counts_from_dispositions(
    chapter_dispositions: dict[str, str],
) -> dict[str, int]:
    """Derive canonical aggregate counts from per-chapter dispositions.

    ``expected_count`` is the total number of current-index chapters; removed
    chapters are *not* counted because they are no longer current-index
    membership. Available membership is the union of every disposition that
    has a physical bundle in the stage; unavailable membership is the
    explicit ``unavailable`` disposition.
    """
    counts = {
        "expected_count": len(chapter_dispositions),
        "fetched_count": 0,
        "reused_count": 0,
        "carried_unselected_count": 0,
        "unchanged_selected_count": 0,
        "refresh_failed_retained_count": 0,
        "unavailable_count": 0,
    }
    for disposition in chapter_dispositions.values():
        if disposition in (DISPOSITION_FETCHED_NEW, DISPOSITION_FETCHED_REPLACED):
            counts["fetched_count"] += 1
        elif disposition == DISPOSITION_REUSED_PLANNER:
            counts["reused_count"] += 1
        elif disposition == DISPOSITION_CARRIED_UNSELECTED:
            counts["carried_unselected_count"] += 1
        elif disposition == DISPOSITION_UNCHANGED_SELECTED:
            counts["unchanged_selected_count"] += 1
        elif disposition == DISPOSITION_REFRESH_FAILED_RETAINED:
            counts["refresh_failed_retained_count"] += 1
        elif disposition == DISPOSITION_UNAVAILABLE:
            counts["unavailable_count"] += 1
    # ``reused_count`` is the sum of planner-reuse + unchanged-selected
    # because both reuse an existing bundle rather than fetching a new one.
    counts["reused_count"] = counts["reused_count"] + counts["unchanged_selected_count"]
    return counts


def derive_failed_refresh_count(
    unavailable_chapter_records: dict[str, dict[str, Any]],
    refresh_failed_chapter_ids: list[str] | set[str],
) -> int:
    """Count real failed-refresh attempts from explicit records.

    ``failed_refresh_count = refresh_failed_retained_count +
    unavailable_due_to_fetch_failure_count``. A deliberate not-fetched scoped
    unavailable entry (``error_category == "not_fetched"``) is not an HTTP
    fetch failure and never counts here — the two failure kinds stay distinct
    instead of overloading one counter.
    """
    unavailable_fetch_failures = 0
    for record in (unavailable_chapter_records or {}).values():
        if not isinstance(record, dict):
            continue
        if str(record.get("error_category") or "") != "not_fetched":
            unavailable_fetch_failures += 1
    return len(set(refresh_failed_chapter_ids or ())) + unavailable_fetch_failures


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
    refresh_failed_chapter_ids: list[str] = field(default_factory=list)
    refresh_failed_chapter_records: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Canonical per-chapter dispositions: ``chapter_id -> disposition_name``.
    # Every current-index chapter must end the crawl with exactly one entry.
    # Aggregate counts are derived from this map at commit time so the
    # caller cannot pass summary counters that disagree with the stage.
    # ``None`` means the manifest predates the disposition contract (legacy
    # recovery manifests): validation then skips disposition reconciliation.
    # An explicit ``{}`` is NOT ``None``: it is a rejected empty map.
    chapter_dispositions: dict[str, str] | None = None
    # Carried unselected chapter count surfaced explicitly so scoped crawls
    # can describe the membership without recomputing from dispositions.
    carried_unselected_count: int = 0
    # Exact derived aggregate counts. Derived from ``chapter_dispositions``
    # (plus explicit unavailable records for ``failed_refresh_count``) at
    # commit time and reconciled by the pre-activation validator so caller
    # summaries can never disagree with the stage.
    unchanged_selected_count: int = 0
    refresh_failed_retained_count: int = 0
    unavailable_count: int = 0
    # Real failed-refresh attempts:
    # ``refresh_failed_retained_count + unavailable_due_to_fetch_failure_count``.
    # Deliberate not-fetched scoped unavailable entries (``error_category ==
    # "not_fetched"``) are NOT fetch failures and never count here.
    failed_refresh_count: int = 0
    removed_count: int = 0
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
            refresh_failed_chapter_ids=list(data.get("refresh_failed_chapter_ids", [])),
            refresh_failed_chapter_records=dict(data.get("refresh_failed_chapter_records", {})),
            # Preserve ``None`` when the manifest predates the disposition
            # contract; an explicitly stored empty map stays ``{}`` so
            # validation can reject it as a bypass attempt.
            chapter_dispositions=(
                dict(data["chapter_dispositions"]) if isinstance(data.get("chapter_dispositions"), dict) else None
            ),
            carried_unselected_count=int(data.get("carried_unselected_count", 0)),
            unchanged_selected_count=int(data.get("unchanged_selected_count", 0)),
            refresh_failed_retained_count=int(data.get("refresh_failed_retained_count", 0)),
            unavailable_count=int(data.get("unavailable_count", 0)),
            failed_refresh_count=int(data.get("failed_refresh_count", 0)),
            removed_count=int(data.get("removed_count", 0)),
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


def _active_generation_lock_path(self: Any, novel_id: str) -> Path:
    """Return the per-novel cross-process lock path guarding the active pointer.

    The lock lives in the same ``generations/`` directory the pointer lives
    in. It is used **only** for the filesystem backend: the pointer read,
    expected-generation verification, and atomic replacement all happen
    inside this lock so two processes can never both observe the same
    expected pointer and both succeed. Object-store backends rely on their
    own conditional CAS and never take this local lock (it is not
    distributed and is not the source of truth for remote backends).
    """
    return self._generations_dir(novel_id) / ".active_generation.lock"


class PointerState:
    MISSING = "missing"
    VALID = "valid"
    CORRUPT = "corrupt"


def _inspect_active_generation_pointer(raw: bytes | None) -> tuple[str, str | None]:
    """Inspect raw pointer bytes returning (PointerState, active_generation_id)."""
    if raw is None:
        return PointerState.MISSING, None
    if not raw:
        return PointerState.CORRUPT, None
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return PointerState.CORRUPT, None
    if not isinstance(data, dict):
        return PointerState.CORRUPT, None
    gen_id = data.get("active_generation_id")
    if isinstance(gen_id, str) and gen_id.strip():
        return PointerState.VALID, gen_id.strip()
    return PointerState.CORRUPT, None


def _parse_active_generation_id(raw: bytes | None) -> str | None:
    """Parse ``active_generation_id`` out of pointer bytes.

    Returns ``None`` for a missing or corrupt pointer so a corrupt pointer
    always conflicts with a non-empty captured contract.
    """
    state, gen_id = _inspect_active_generation_pointer(raw)
    return gen_id if state == PointerState.VALID else None


def _activate_generation_pointer(
    self: Any,
    novel_id: str,
    *,
    generation_id: str,
    starting_active_generation_id: str | None,
    pointer_payload: str,
) -> None:
    """Atomically verify the captured contract and replace the active pointer.

    The expected state comes from ``starting_active_generation_id`` captured
    by the caller at crawl start — never from whatever happens to be present
    after a race. The verification and the conditional replacement form a
    single transaction:

    - **Filesystem backend:** the pointer read, expected-generation
      verification, and atomic replacement all happen inside the same
      per-novel :class:`InterProcessFileLock`. There is no window between
      "verify expected generation" and "conditional replacement" outside the
      lock, so a stale writer that observed gen-1 can never replace a newer
      gen-2 pointer.
    - **S3 / object-store backend:** no local lock (it is not distributed
      across containers and is not the source of truth). The current object
      is read once as one observed version, verified against the captured
      contract, then replaced with a conditional PUT — ``If-Match`` on the
      observed ETag (or ``If-None-Match: *`` for first activation). A
      concurrent activation fails the conditional PUT.

    Raises :class:`GenerationConflictError` when the pointer no longer
    matches the captured contract or the conditional replacement loses.
    """
    backing = getattr(self._backend, "_BACKING", "filesystem")
    active_pointer_path = self._generations_dir(novel_id) / "active_generation.json"
    rel_pointer = self._rel(active_pointer_path)
    new_value = pointer_payload.encode("utf-8")

    def _verify_and_swap() -> bool:
        observed = self._backend.load(rel_pointer) if self._path_exists(active_pointer_path) else None
        state, observed_id = _inspect_active_generation_pointer(observed)
        if state == PointerState.CORRUPT:
            raise GenerationConflictError(
                f"Active generation pointer for {novel_id} is corrupt. "
                "Normal activation cannot overwrite corrupt storage pointer; use explicit recovery API."
            )
        if observed_id != starting_active_generation_id:
            raise GenerationConflictError(
                f"Active generation for {novel_id} changed during crawl: expected "
                f"{starting_active_generation_id!r}, found {observed_id!r}. "
                "Losing stage is not activated; roll it back explicitly."
            )
        return self._backend.compare_and_swap(rel_pointer, observed, new_value)

    if backing == "s3":
        swapped = _verify_and_swap()
    else:
        lock_path = _active_generation_lock_path(self, novel_id)
        from novelai.storage.file_lock import InterProcessFileLock

        with InterProcessFileLock(lock_path):
            swapped = _verify_and_swap()
    if not swapped:
        raise GenerationConflictError(
            f"Active pointer for {novel_id} changed during activation; {generation_id} was not activated."
        )


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
    """Return the active generation manifest for a novel.

    Read-only: never creates the ``generations/`` tree (a metadata read must
    not mutate the novel layout, e.g. by pre-creating the novel folder before
    folder naming runs).
    """
    active_pointer_path = self._novel_dir(novel_id) / "generations" / "active_generation.json"
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
    """Return the raw active generation_id (no manifest lookup).

    Read-only: never creates the ``generations/`` tree.
    """
    active_pointer_path = self._novel_dir(novel_id) / "generations" / "active_generation.json"
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
    # The staged snapshot is novel metadata and must satisfy the same schema
    # contract as the legacy root copy so generation-aware reads validate it
    # identically. The caller's dict is never mutated.
    staged = dict(meta)
    staged["schema_version"] = self.SCHEMA_VERSION
    content = json.dumps(staged, ensure_ascii=False, indent=2)
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
    # Section 4: the manifest records the canonical hashes computed from the
    # staged bundle itself — never caller-provided values — so the validator
    # can recompute and compare deterministically for seeded and fresh
    # bundles alike.
    canonical_source, canonical_structure, canonical_image = _canonical_bundle_hashes(payload)
    manifest.source_hashes[chapter_id] = canonical_source
    manifest.structure_hashes[chapter_id] = canonical_structure
    manifest.image_manifest_hashes[chapter_id] = canonical_image
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


def record_refresh_failed_chapter(
    self: Any,
    novel_id: str,
    generation_id: str,
    chapter_id: str,
    *,
    reason: str = "",
    error_category: str = "",
) -> GenerationManifest:
    """Record an explicit refresh-failed-retained marker for a chapter.

    Section 3 disposition A: the chapter's *previous* valid bundle was
    carried forward into the stage (``seed_generation_from_active``) and the
    fresh acquisition failed, so the prior bundle is retained. This is a
    distinct disposition from :func:`record_unavailable_chapter` (disposition
    B: no usable raw bundle exists for the current source episode).
    """
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is None:
        manifest = create_generation_stage(self, novel_id, generation_id)
    if chapter_id not in manifest.refresh_failed_chapter_ids:
        manifest.refresh_failed_chapter_ids.append(chapter_id)
    manifest.refresh_failed_chapter_records[chapter_id] = {
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

    The validation is exact:

    - only ``status == "staging"`` may activate through the normal path;
    - the normalized complete index id set must equal the physical bundle
      ids UNION the explicit unavailable ids, subject to the
      refresh-failed-retained disposition rules;
    - duplicate logical or decoded physical ids, unexpected physical
      bundles, unexpected manifest ids, missing ids, and conflicting
      unavailable/available states all fail;
    - every required manifest hash (metadata, chapter index, source state,
      per-chapter source/structure/image) must be present and match;
    - every referenced asset must resolve safely inside the stage and match
      its recorded size and sha256.
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
            manifest.status == "staging",
            f"manifest.status={manifest.status!r} (only 'staging' may activate)",
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

    source_state = _read_json_or_none(self, source_state_path)
    checks.append(
        _check(
            "source_state_present",
            source_state is not None,
            f"{source_state_path} missing or empty",
        )
    )

    # ── exact membership reconciliation ────────────────────────────────
    chapter_dir = g_dir / "chapters"
    physical_logical_ids: list[str] = []
    if self._path_exists(chapter_dir):
        for physical_path in self._glob(chapter_dir, "*.json"):
            try:
                physical_logical_ids.append(self.logical_id_from_stem(physical_path.stem))
            except Exception:
                continue
    checks.append(
        _check(
            "no_duplicate_decoded_physical_ids",
            len(physical_logical_ids) == len(set(physical_logical_ids)),
            f"duplicate decoded physical ids: {sorted({i for i in physical_logical_ids if physical_logical_ids.count(i) > 1})}",
        )
    )
    available_bundle_ids: set[str] = set(physical_logical_ids)

    index_logical_ids: list[str] = []
    if isinstance(chapter_index, list):
        for entry in chapter_index:
            if not isinstance(entry, dict):
                continue
            cid = _index_entry_logical_id(entry)
            if cid:
                index_logical_ids.append(cid)
    complete_index_ids: set[str] = set(index_logical_ids)
    checks.append(
        _check(
            "no_duplicate_index_ids",
            len(index_logical_ids) == len(complete_index_ids),
            f"duplicate index ids: {sorted({i for i in index_logical_ids if index_logical_ids.count(i) > 1})}",
        )
    )

    unexpected_physical = available_bundle_ids - complete_index_ids
    checks.append(
        _check(
            "no_unexpected_physical_bundles",
            not unexpected_physical,
            f"physical bundles not in the complete index: {sorted(unexpected_physical)}",
        )
    )
    checks.append(
        _check(
            "manifest_chapter_ids_match_available",
            set(manifest.chapter_ids or []) == available_bundle_ids,
            f"manifest.chapter_ids={sorted(set(manifest.chapter_ids or []))} != available bundles={sorted(available_bundle_ids)}",
        )
    )

    unavailable_ids = set(manifest.unavailable_chapter_ids or [])
    refresh_failed_ids = set(manifest.refresh_failed_chapter_ids or [])
    # refresh_failed_retained legitimately overlaps available (the carried
    # bundle is present); only unavailable combined with either disposition
    # is contradictory.
    conflicting = (unavailable_ids & refresh_failed_ids) | (available_bundle_ids & unavailable_ids)
    checks.append(
        _check(
            "no_conflicting_dispositions",
            not conflicting,
            f"chapters with conflicting available/unavailable states: {sorted(conflicting)}",
        )
    )
    missing_retained = refresh_failed_ids - available_bundle_ids
    checks.append(
        _check(
            "refresh_failed_retains_bundle",
            not missing_retained,
            f"refresh-failed-retained chapters with no carried bundle: {sorted(missing_retained)}",
        )
    )
    missing_bundles: list[str] = []
    if isinstance(chapter_index, list):
        for cid in index_logical_ids:
            if cid in available_bundle_ids or cid in unavailable_ids or cid in refresh_failed_ids:
                continue
            missing_bundles.append(cid)
    checks.append(
        _check(
            "every_index_entry_resolved",
            not missing_bundles,
            f"Missing bundles for {len(missing_bundles)} indexed chapters",
        )
    )

    checks.append(
        _check(
            "expected_chapters_match_index",
            manifest.expected_chapters == len(complete_index_ids),
            f"expected_chapters={manifest.expected_chapters} != complete chapter_index size={len(complete_index_ids)}",
        )
    )

    # ── disposition reconciliation ───────────────────────────────────────
    # A ``None`` map is the legacy pre-disposition contract (recovery
    # manifests) and skips reconciliation. An empty dict is NOT a bypass: it
    # fails explicitly so no caller can silently disable the checks below.
    if manifest.chapter_dispositions is not None:
        checks.append(
            _check(
                "dispositions_present",
                bool(manifest.chapter_dispositions),
                "chapter_dispositions is an empty map; every current-index chapter must carry exactly one canonical disposition",
            )
        )
        invalid_dispositions = sorted(
            {d for d in manifest.chapter_dispositions.values() if d not in ALL_CHAPTER_DISPOSITIONS}
        )
        checks.append(
            _check(
                "dispositions_use_canonical_names",
                not invalid_dispositions,
                f"non-canonical disposition values: {invalid_dispositions}",
            )
        )
        # Every current-index chapter must have exactly one disposition.
        disposition_chapter_ids = set(manifest.chapter_dispositions.keys())
        missing_disp = complete_index_ids - disposition_chapter_ids
        checks.append(
            _check(
                "disposition_for_every_index_entry",
                not missing_disp,
                f"Missing dispositions for {len(missing_disp)} index entries: {sorted(missing_disp)}",
            )
        )
        extra_disp = disposition_chapter_ids - complete_index_ids
        checks.append(
            _check(
                "no_extra_dispositions",
                not extra_disp,
                f"Dispositions for non-index chapters: {sorted(extra_disp)}",
            )
        )
        # Disposition map must agree with the explicit unavailable/refresh_failed lists.
        disp_unavailable = {cid for cid, d in manifest.chapter_dispositions.items() if d == DISPOSITION_UNAVAILABLE}
        disp_refresh_failed = {
            cid for cid, d in manifest.chapter_dispositions.items() if d == DISPOSITION_REFRESH_FAILED_RETAINED
        }
        checks.append(
            _check(
                "disposition_unavailable_matches_explicit",
                disp_unavailable == unavailable_ids,
                f"disposition unavailable={sorted(disp_unavailable)} != explicit unavailable_chapter_ids={sorted(unavailable_ids)}",
            )
        )
        checks.append(
            _check(
                "disposition_refresh_failed_matches_explicit",
                disp_refresh_failed == refresh_failed_ids,
                f"disposition refresh_failed_retained={sorted(disp_refresh_failed)} != explicit refresh_failed_chapter_ids={sorted(refresh_failed_ids)}",
            )
        )
        # Derived counts must match the manifest's aggregate counters.
        derived = derive_counts_from_dispositions(manifest.chapter_dispositions)
        checks.append(
            _check(
                "derived_fetched_count_matches_manifest",
                manifest.saved_chapters == derived["fetched_count"],
                f"saved_chapters={manifest.saved_chapters} != derived fetched_count={derived['fetched_count']}",
            )
        )
        checks.append(
            _check(
                "derived_reused_count_matches_manifest",
                manifest.reused_chapters == derived["reused_count"],
                f"reused_chapters={manifest.reused_chapters} != derived reused_count={derived['reused_count']}",
            )
        )
        checks.append(
            _check(
                "derived_unavailable_count_matches_manifest",
                manifest.failed_chapters == derived["unavailable_count"],
                f"failed_chapters={manifest.failed_chapters} != derived unavailable_count={derived['unavailable_count']}",
            )
        )
        checks.append(
            _check(
                "derived_carried_unselected_count_matches_manifest",
                manifest.carried_unselected_count == derived["carried_unselected_count"],
                f"carried_unselected_count={manifest.carried_unselected_count} != derived carried_unselected_count={derived['carried_unselected_count']}",
            )
        )
        checks.append(
            _check(
                "derived_unchanged_selected_count_matches_manifest",
                manifest.unchanged_selected_count == derived["unchanged_selected_count"],
                f"unchanged_selected_count={manifest.unchanged_selected_count} != derived unchanged_selected_count={derived['unchanged_selected_count']}",
            )
        )
        checks.append(
            _check(
                "derived_refresh_failed_retained_count_matches_manifest",
                manifest.refresh_failed_retained_count == derived["refresh_failed_retained_count"],
                f"refresh_failed_retained_count={manifest.refresh_failed_retained_count} != derived refresh_failed_retained_count={derived['refresh_failed_retained_count']}",
            )
        )
        checks.append(
            _check(
                "derived_unavailable_exact_count_matches_manifest",
                manifest.unavailable_count == derived["unavailable_count"],
                f"unavailable_count={manifest.unavailable_count} != derived unavailable_count={derived['unavailable_count']}",
            )
        )
        expected_failed_refresh = derive_failed_refresh_count(
            manifest.unavailable_chapter_records,
            set(manifest.refresh_failed_chapter_ids or []),
        )
        checks.append(
            _check(
                "derived_failed_refresh_count_matches_manifest",
                manifest.failed_refresh_count == expected_failed_refresh,
                f"failed_refresh_count={manifest.failed_refresh_count} != derived failed_refresh_count={expected_failed_refresh}",
            )
        )
        checks.append(
            _check(
                "derived_removed_count_matches_manifest",
                manifest.removed_count == len(manifest.removed_episode_ids),
                f"removed_count={manifest.removed_count} != removed_episode_ids count={len(manifest.removed_episode_ids)}",
            )
        )

    # ── snapshot hash integrity (empty required hash fails) ────────────
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

    # ── per-bundle integrity + required hashes ─────────────────────────
    missing_source_hashes: list[str] = []
    missing_structure_hashes: list[str] = []
    missing_image_hashes: list[str] = []
    hash_mismatch: list[str] = []
    bundle_identity_failures: list[str] = []
    missing_assets: list[str] = []
    asset_integrity_failures: list[str] = []
    for cid in sorted(available_bundle_ids):
        chapter_path = chapter_dir / _chapter_filename_for(cid)
        bundle = _read_json_or_none(self, chapter_path)
        if not isinstance(bundle, dict):
            bundle_identity_failures.append(f"{cid}: bundle unreadable")
            continue
        if str(bundle.get("id")) != cid:
            bundle_identity_failures.append(f"{cid}: bundle.id={bundle.get('id')!r} != logical id {cid!r}")
        canonical_source, canonical_structure, canonical_image = _canonical_bundle_hashes(bundle)
        rec_source = manifest.source_hashes.get(cid)
        rec_structure = manifest.structure_hashes.get(cid)
        rec_image = manifest.image_manifest_hashes.get(cid)
        if not rec_source:
            missing_source_hashes.append(cid)
        elif rec_source != canonical_source:
            hash_mismatch.append(f"{cid}: source")
        if not rec_structure:
            missing_structure_hashes.append(cid)
        elif rec_structure != canonical_structure:
            hash_mismatch.append(f"{cid}: structure")
        if not rec_image:
            missing_image_hashes.append(cid)
        elif rec_image != canonical_image:
            hash_mismatch.append(f"{cid}: image-manifest")
        raw_section = bundle.get("raw")
        raw = raw_section if isinstance(raw_section, dict) else {}
        images_value = raw.get("images")
        images = images_value if isinstance(images_value, list) else []
        for image in images:
            if not isinstance(image, dict):
                continue
            local_path = image.get("local_path")
            if not isinstance(local_path, str) or not local_path.strip():
                # An image whose download failed has no staged asset; it is
                # recorded with ``download_error`` and there is nothing to
                # validate.
                continue
            safe = safe_child_path(g_dir, local_path, unquote=False)
            if safe is None:
                missing_assets.append(f"{cid}: unsafe local_path {local_path!r}")
                continue
            try:
                safe.relative_to(g_dir)
            except ValueError:
                missing_assets.append(f"{cid}: local_path escapes stage {local_path!r}")
                continue
            if not self._path_exists(safe):
                missing_assets.append(f"{cid}: {local_path}")
                continue
            try:
                actual = self._backend.load(self._rel(safe))
            except Exception:
                actual = b""
            recorded_size = image.get("size_bytes")
            if isinstance(recorded_size, int) and len(actual) != recorded_size:
                asset_integrity_failures.append(f"{cid}: {local_path} size {len(actual)} != recorded {recorded_size}")
            recorded_sha = image.get("sha256")
            if isinstance(recorded_sha, str) and recorded_sha and hashlib.sha256(actual).hexdigest() != recorded_sha:
                asset_integrity_failures.append(f"{cid}: {local_path} sha256 mismatch")

    checks.append(_check("bundle_identity_valid", not bundle_identity_failures, "; ".join(bundle_identity_failures)))
    checks.append(
        _check("chapter_source_hashes_present", not missing_source_hashes, f"missing: {sorted(missing_source_hashes)}")
    )
    checks.append(
        _check(
            "chapter_structure_hashes_present",
            not missing_structure_hashes,
            f"missing: {sorted(missing_structure_hashes)}",
        )
    )
    checks.append(
        _check("chapter_image_hashes_present", not missing_image_hashes, f"missing: {sorted(missing_image_hashes)}")
    )
    checks.append(_check("chapter_hashes_match_bundles", not hash_mismatch, "; ".join(hash_mismatch)))
    checks.append(
        _check(
            "every_referenced_image_resolves_inside_stage",
            not missing_assets,
            f"{len(missing_assets)} referenced images do not resolve safely inside the stage",
        )
    )
    checks.append(
        _check(
            "referenced_image_integrity",
            not asset_integrity_failures,
            "; ".join(asset_integrity_failures),
        )
    )

    is_valid = all(check.passed for check in checks)
    return GenerationValidationResult(is_valid=is_valid, checks=checks)


class GenerationConflictError(RuntimeError):
    """A concurrent crawl activated a different generation before this commit."""


def commit_generation(
    self: Any,
    novel_id: str,
    generation_id: str,
    *,
    removed_episode_ids: list[str] | None = None,
    chapter_dispositions: dict[str, str] | None = None,
    # Legacy / diagnostic counters. When ``chapter_dispositions`` is supplied
    # the aggregate counts are derived from the dispositions and the explicit
    # ``saved_chapters`` / ``reused_chapters`` / ``failed_chapters`` arguments
    # are treated as advisory hints — they must match the derived counts or
    # validation rejects the commit.
    reused_chapters: int = 0,
    saved_chapters: int | None = None,
    failed_chapters: int = 0,
    starting_active_generation_id: str | None = None,
) -> GenerationManifest:
    """Finalize a staged generation and atomically activate it.

    The manifest is written with its final counts and ``committed`` status
    *before* the ``active_generation.json`` pointer is swapped, so readers
    can never observe a partially recorded snapshot as active. The manifest
    keeps the ``committed`` status after activation; the pointer itself is
    the active marker.

    Section 4: :func:`validate_generation_activation` always runs before the
    pointer swap; partial / corrupt / membership-incomplete generations never
    become visible through the normal path. Aggregate counts are derived
    from ``chapter_dispositions`` (the canonical source of truth) and
    reconciled against the physical staged state — caller-supplied summary
    counters cannot disagree with the dispositions. Modern normal commits
    must supply the canonical disposition map; missing or empty maps fail
    closed. There is no normal bypass flag. Explicit recovery uses
    :func:`commit_generation_recovery`.

    Section 5: activation is a compare-and-swap on the active pointer,
    wrapped in an inter-process file lock so two independent processes
    cannot both observe the same expected pointer and both succeed; the
    loser receives :class:`GenerationConflictError` and the winner cannot
    be overwritten by the loser. The caller captures
    ``starting_active_generation_id`` at crawl start; if the pointer no
    longer matches (another crawl activated meanwhile) the commit fails
    and the losing stage must be rolled back.
    """
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is None:
        raise FileNotFoundError(f"Generation manifest for {novel_id}/{generation_id} not found.")

    # Never re-activate an already-committed manifest through the normal
    # path. The guard is explicit because the staging state below is
    # persisted before validation (validation reloads the manifest from
    # disk and must observe the exact reconciliation it verifies).
    if manifest.status == "committed":
        raise RuntimeError(
            f"Generation {generation_id} for {novel_id} is already committed; "
            "it cannot be re-activated through the normal commit path (manifest_status_staging). "
            "Use commit_generation_recovery for explicit operator recovery."
        )

    if removed_episode_ids:
        manifest.removed_episode_ids = sorted(set(removed_episode_ids))

    if chapter_dispositions is not None:
        # An explicitly empty map is a bypass attempt: it would persist
        # ``{}`` and disable every disposition-reconciliation check. Reject
        # it here so the manifest can never be saved in that state.
        if not chapter_dispositions:
            raise RuntimeError(
                f"Generation {generation_id} for {novel_id} supplied an empty chapter_dispositions map; "
                "every current-index chapter must carry exactly one canonical disposition. "
                "Use commit_generation_recovery for explicit operator recovery."
            )
        # Canonical disposition map provided: derive all aggregate counts
        # from it and replace the manifest's existing map (the caller is
        # authoritative about what each current-index chapter became).
        manifest.chapter_dispositions = dict(chapter_dispositions)
        derived = derive_counts_from_dispositions(manifest.chapter_dispositions)
        manifest.saved_chapters = derived["fetched_count"]
        manifest.reused_chapters = derived["reused_count"]
        manifest.failed_chapters = derived["unavailable_count"]
        manifest.carried_unselected_count = derived["carried_unselected_count"]
        manifest.unchanged_selected_count = derived["unchanged_selected_count"]
        manifest.refresh_failed_retained_count = derived["refresh_failed_retained_count"]
        manifest.unavailable_count = derived["unavailable_count"]
        manifest.removed_count = len(manifest.removed_episode_ids)
        # ``failed_chapters`` is the legacy "no usable chapter" count
        # (unavailable entries). ``failed_refresh_count`` is the explicit
        # failed-refresh aggregate: retained-refresh failures plus
        # unavailable entries caused by real fetch failures. A deliberate
        # not-fetched scoped unavailable entry never counts as a fetch
        # failure.
        manifest.failed_refresh_count = derive_failed_refresh_count(
            manifest.unavailable_chapter_records,
            derived_refresh_failed_ids := {
                cid
                for cid, disp in manifest.chapter_dispositions.items()
                if disp == DISPOSITION_REFRESH_FAILED_RETAINED
            },
        )
        # Reconcile derived lists with the staged explicit records. The
        # disposition map is authoritative: any chapter marked
        # ``unavailable`` must appear in ``unavailable_chapter_ids`` and
        # every chapter in ``unavailable_chapter_ids`` /
        # ``refresh_failed_chapter_ids`` must appear with the matching
        # disposition.
        manifest.unavailable_chapter_ids = sorted(
            cid for cid, disp in manifest.chapter_dispositions.items() if disp == DISPOSITION_UNAVAILABLE
        )
        manifest.refresh_failed_chapter_ids = sorted(derived_refresh_failed_ids)
    else:
        # Legacy/recovery compatibility: normal commit requires canonical disposition map.
        raise RuntimeError(
            f"Generation {generation_id} for {novel_id} has no chapter_dispositions; "
            "normal commits must reconcile dispositions. Use "
            "commit_generation_recovery for the explicit recovery path."
        )
    manifest.status = "staging"
    manifest.committed_at = manifest.committed_at or _utc_now_iso()

    # Persist the derived staging state (disposition map, aggregate counts,
    # explicit id lists) BEFORE validation: the validator reloads the
    # manifest from disk, and an unpersisted derivation would be invisible
    # to it — silently skipping the disposition reconciliation checks.
    _save_manifest(self, novel_id, generation_id, manifest)

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

    # Section 5: activation is a single atomic transaction — the captured
    # ``starting_active_generation_id`` is verified against the current
    # pointer and the pointer is conditionally replaced under the same
    # per-novel inter-process lock (filesystem) or backend-native conditional
    # CAS (S3/R2). There is no window between verification and replacement
    # outside the lock, so a stale writer can never overwrite a winner.
    pointer_payload = json.dumps(
        {
            "novel_id": novel_id,
            "active_generation_id": generation_id,
            "activated_at": manifest.activated_at,
        },
        ensure_ascii=False,
        indent=2,
    )
    _activate_generation_pointer(
        self,
        novel_id,
        generation_id=generation_id,
        starting_active_generation_id=starting_active_generation_id,
        pointer_payload=pointer_payload,
    )
    return manifest


def commit_generation_recovery(
    self: Any,
    novel_id: str,
    generation_id: str,
    *,
    reason: str,
    evidence: str,
) -> GenerationManifest:
    """Recovery-only activation that bypasses strict pre-activation validation.

    Never on the normal commit path: requires explicit operator consent in
    the form of a non-empty ``reason`` and ``evidence`` describing what was
    inspected and why the strict gate is waived. The active pointer is
    swapped without compare-and-swap because recovery runs deliberately
    override the normal concurrent-activation contract.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("commit_generation_recovery requires a non-empty reason.")
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError("commit_generation_recovery requires non-empty evidence.")
    manifest = _load_manifest(self, novel_id, generation_id)
    if manifest is None:
        raise FileNotFoundError(f"Generation manifest for {novel_id}/{generation_id} not found.")
    manifest.status = "committed"
    manifest.activated_at = manifest.activated_at or _utc_now_iso()
    _save_manifest(self, novel_id, generation_id, manifest)
    active_pointer_path = self._generations_dir(novel_id) / "active_generation.json"
    self._write_text_atomic(
        active_pointer_path,
        json.dumps(
            {
                "novel_id": novel_id,
                "active_generation_id": generation_id,
                "activated_at": manifest.activated_at,
                "recovery_reason": reason,
                "recovery_evidence": evidence,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    logger.warning(
        "Recovery activation of %s for %s (reason=%s)",
        generation_id,
        novel_id,
        reason,
    )
    return manifest


def activate_generation(
    self: Any,
    novel_id: str,
    generation_id: str,
    *,
    chapter_dispositions: dict[str, str] | None = None,
    starting_active_generation_id: str | None = None,
) -> GenerationManifest:
    """Atomically activate a staged generation (alias kept for compatibility)."""
    return commit_generation(
        self,
        novel_id,
        generation_id,
        chapter_dispositions=chapter_dispositions,
        starting_active_generation_id=starting_active_generation_id,
    )


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

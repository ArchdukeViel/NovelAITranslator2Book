"""Staged generations with manifest-last atomic activation (DEBT-GEN-01)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class GenerationManifest:
    """Manifest tracking a staged generation run."""

    generation_id: str
    novel_id: str
    created_at: str = field(default_factory=_utc_now_iso)
    status: str = "staging"  # "staging", "active", "failed"
    chapter_ids: list[str] = field(default_factory=list)
    source_hashes: dict[str, str] = field(default_factory=dict)
    translation_versions: dict[str, str] = field(default_factory=dict)
    activated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenerationManifest:
        return cls(
            generation_id=str(data.get("generation_id", "")),
            novel_id=str(data.get("novel_id", "")),
            created_at=str(data.get("created_at", _utc_now_iso())),
            status=str(data.get("status", "staging")),
            chapter_ids=list(data.get("chapter_ids", [])),
            source_hashes=dict(data.get("source_hashes", {})),
            translation_versions=dict(data.get("translation_versions", {})),
            activated_at=data.get("activated_at"),
        )


def _generations_dir(self: Any, novel_id: str) -> Path:
    novel_dir = self._novel_dir(novel_id)
    g_dir = novel_dir / "generations"
    self._mkdirs(g_dir)
    return g_dir


def create_generation_stage(
    self: Any,
    novel_id: str,
    generation_id: str,
) -> GenerationManifest:
    """Create a new staged generation directory and initial manifest."""
    g_dir = self._generations_dir(novel_id) / generation_id
    self._mkdirs(g_dir)
    manifest = GenerationManifest(
        generation_id=generation_id,
        novel_id=novel_id,
        status="staging",
    )
    manifest_path = g_dir / "generation_manifest.json"
    self._write_text_atomic(manifest_path, json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
    return manifest


def record_staged_chapter(
    self: Any,
    novel_id: str,
    generation_id: str,
    chapter_id: str,
    version_id: str,
    source_hash: str | None = None,
) -> GenerationManifest:
    """Record a completed chapter in the staged generation manifest."""
    g_dir = self._generations_dir(novel_id) / generation_id
    manifest_path = g_dir / "generation_manifest.json"
    if not self._path_exists(manifest_path):
        manifest = create_generation_stage(self, novel_id, generation_id)
    else:
        manifest = GenerationManifest.from_dict(json.loads(self._read_text(manifest_path)))

    if chapter_id not in manifest.chapter_ids:
        manifest.chapter_ids.append(chapter_id)
    manifest.translation_versions[chapter_id] = version_id
    if source_hash:
        manifest.source_hashes[chapter_id] = source_hash

    self._write_text_atomic(manifest_path, json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
    return manifest


def activate_generation(
    self: Any,
    novel_id: str,
    generation_id: str,
) -> GenerationManifest:
    """Atomically activate a staged generation by setting status='active' manifest-last."""
    g_dir = self._generations_dir(novel_id) / generation_id
    manifest_path = g_dir / "generation_manifest.json"
    if not self._path_exists(manifest_path):
        raise FileNotFoundError(f"Generation manifest for {novel_id}/{generation_id} not found.")

    manifest = GenerationManifest.from_dict(json.loads(self._read_text(manifest_path)))
    manifest.status = "active"
    manifest.activated_at = _utc_now_iso()

    # Manifest-last atomic write
    self._write_text_atomic(manifest_path, json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))

    # Also update active_generation pointer in novel metadata or active_generation.json
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


def load_generation_manifest(
    self: Any,
    novel_id: str,
    generation_id: str,
) -> GenerationManifest | None:
    """Load a generation manifest if it exists."""
    g_dir = self._generations_dir(novel_id) / generation_id
    manifest_path = g_dir / "generation_manifest.json"
    if not self._path_exists(manifest_path):
        return None
    try:
        return GenerationManifest.from_dict(json.loads(self._read_text(manifest_path)))
    except Exception as exc:
        logger.warning("Failed to load generation manifest for %s/%s: %s", novel_id, generation_id, exc)
        return None


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

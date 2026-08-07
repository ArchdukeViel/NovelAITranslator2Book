"""Translation run manifests and hash-linked invalidation helpers (DEBT-CACHE-01, DEBT-LINK-01)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class TranslationRunManifest:
    """Run manifest tracking translation execution and exact input hashes matching Section 10 requirements."""

    translation_run_id: str
    novel_id: str
    raw_generation_id: str = ""
    created_at: str = field(default_factory=_utc_now_iso)
    committed_at: str | None = None
    status: str = "completed"
    prompt_version: str | None = None
    prompt_template_version: str | None = None
    qa_policy_version: str | None = None
    qa_policy_fingerprint: str | None = None
    glossary_hash: str | None = None
    glossary_revision: int | None = None
    provider_key: str | None = None
    provider_model: str | None = None
    source_language: str = "Japanese"
    target_language: str = "English"
    style_preset: str | None = None
    json_output: bool = False
    consistency_mode: bool = False
    requested_chapters: list[str] = field(default_factory=list)
    chapter_ids: list[str] = field(default_factory=list)
    expected_count: int = 0
    completed_count: int = 0
    skipped_count: int = 0
    review_count: int = 0
    failed_count: int = 0
    chapter_source_hashes: dict[str, str] = field(default_factory=dict)
    chunk_outputs: dict[str, str] = field(default_factory=dict)  # chunk_id -> output_hash

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranslationRunManifest:
        return cls(
            translation_run_id=str(data.get("translation_run_id", "")),
            novel_id=str(data.get("novel_id", "")),
            raw_generation_id=str(data.get("raw_generation_id", "")),
            created_at=str(data.get("created_at", _utc_now_iso())),
            committed_at=data.get("committed_at"),
            status=str(data.get("status", "completed")),
            prompt_version=data.get("prompt_version"),
            prompt_template_version=data.get("prompt_template_version") or data.get("prompt_version"),
            qa_policy_version=data.get("qa_policy_version"),
            qa_policy_fingerprint=data.get("qa_policy_fingerprint"),
            glossary_hash=data.get("glossary_hash"),
            glossary_revision=data.get("glossary_revision"),
            provider_key=data.get("provider_key"),
            provider_model=data.get("provider_model"),
            source_language=str(data.get("source_language", "Japanese")),
            target_language=str(data.get("target_language", "English")),
            style_preset=data.get("style_preset"),
            json_output=bool(data.get("json_output", False)),
            consistency_mode=bool(data.get("consistency_mode", False)),
            requested_chapters=list(data.get("requested_chapters", [])),
            chapter_ids=list(data.get("chapter_ids", [])),
            expected_count=int(data.get("expected_count", 0)),
            completed_count=int(data.get("completed_count", 0)),
            skipped_count=int(data.get("skipped_count", 0)),
            review_count=int(data.get("review_count", 0)),
            failed_count=int(data.get("failed_count", 0)),
            chapter_source_hashes=dict(data.get("chapter_source_hashes", {})),
            chunk_outputs=dict(data.get("chunk_outputs", {})),
        )


def is_translation_valid(
    *,
    source_text_hash: str,
    active_glossary_hash: str | None,
    prompt_version: str | None,
    provider_key: str | None,
    provider_model: str | None,
    record: dict[str, Any],
    # Section 8: complete effective translation contract. When supplied, the
    # record's stored lineage must match exactly.
    active_raw_generation_id: str | None = None,
    source_structure_hash: str | None = None,
    source_image_manifest_hash: str | None = None,
    qa_policy_fingerprint: str | None = None,
    output_hash: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
) -> bool:
    """Verify if a translation record is valid against current input hashes matching Section 10 requirements.

    Reads the keys actually written by the production overlay writer
    (``source_hash`` / ``source_content_hash`` / ``prompt_template_version``),
    falling back to the legacy spellings (``source_text_hash`` /
    ``prompt_version``) for entries persisted before the overlay layout.

    Section 8: when an active raw generation exists, the record must carry a
    matching ``raw_generation_id`` — a record with missing/incomplete lineage
    is ``stale``/``needs-backfill`` and never silently valid. Reorder alone
    never invalidates (reorder does not change any hash).
    """
    if not isinstance(record, dict):
        return False

    rec_source_hash = record.get("source_hash") or record.get("source_content_hash") or record.get("source_text_hash")
    if not rec_source_hash or rec_source_hash != source_text_hash:
        return False

    if active_glossary_hash:
        rec_glossary_hash = record.get("glossary_hash")
        if not rec_glossary_hash or rec_glossary_hash != active_glossary_hash:
            return False

    if prompt_version:
        rec_prompt_ver = record.get("prompt_template_version") or record.get("prompt_version")
        if not rec_prompt_ver or rec_prompt_ver != prompt_version:
            return False

    if provider_key:
        rec_provider_key = record.get("provider_key")
        if not rec_provider_key or rec_provider_key != provider_key:
            return False

    if provider_model:
        rec_provider_model = record.get("provider_model")
        if not rec_provider_model or rec_provider_model != provider_model:
            return False

    # Section 8 lineage contract.
    if active_raw_generation_id:
        rec_generation_id = record.get("raw_generation_id")
        if not rec_generation_id:
            # Missing lineage under an active generation: stale /
            # needs-backfill, never silently valid.
            return False
        if rec_generation_id != active_raw_generation_id:
            return False

    if source_structure_hash:
        rec_structure = record.get("source_structure_hash")
        if not rec_structure or rec_structure != source_structure_hash:
            return False

    if source_image_manifest_hash:
        rec_image = record.get("source_image_manifest_hash")
        if not rec_image or rec_image != source_image_manifest_hash:
            return False

    if qa_policy_fingerprint:
        rec_qa = record.get("qa_policy_fingerprint")
        if not rec_qa or rec_qa != qa_policy_fingerprint:
            return False

    if output_hash:
        rec_output = record.get("output_hash")
        if not rec_output or rec_output != output_hash:
            return False

    if source_language:
        rec_source_lang = record.get("source_language")
        if rec_source_lang and rec_source_lang != source_language:
            return False

    if target_language:
        rec_target_lang = record.get("target_language")
        if rec_target_lang and rec_target_lang != target_language:
            return False

    return True

"""Translation run manifests and hash-linked invalidation helpers (DEBT-CACHE-01, DEBT-LINK-01)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class TranslationRunManifest:
    """Run manifest tracking translation execution and exact input hashes."""

    translation_run_id: str
    novel_id: str
    created_at: str = field(default_factory=_utc_now_iso)
    status: str = "completed"
    prompt_version: str | None = None
    glossary_hash: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None
    style_preset: str | None = None
    json_output: bool = False
    consistency_mode: bool = False
    chapter_ids: list[str] = field(default_factory=list)
    chunk_outputs: dict[str, str] = field(default_factory=dict)  # chunk_id -> output_hash

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranslationRunManifest:
        return cls(
            translation_run_id=str(data.get("translation_run_id", "")),
            novel_id=str(data.get("novel_id", "")),
            created_at=str(data.get("created_at", _utc_now_iso())),
            status=str(data.get("status", "completed")),
            prompt_version=data.get("prompt_version"),
            glossary_hash=data.get("glossary_hash"),
            provider_key=data.get("provider_key"),
            provider_model=data.get("provider_model"),
            style_preset=data.get("style_preset"),
            json_output=bool(data.get("json_output", False)),
            consistency_mode=bool(data.get("consistency_mode", False)),
            chapter_ids=list(data.get("chapter_ids", [])),
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
) -> bool:
    """Verify if a translation record is valid against current input hashes.

    Returns False if any input hash (source text, glossary, prompt, provider)
    has diverged from the recorded values.
    """
    if not isinstance(record, dict):
        return False

    rec_source_hash = record.get("source_text_hash")
    if rec_source_hash and rec_source_hash != source_text_hash:
        return False

    rec_glossary_hash = record.get("glossary_hash")
    if active_glossary_hash and rec_glossary_hash and rec_glossary_hash != active_glossary_hash:
        return False

    rec_prompt_ver = record.get("prompt_version")
    if prompt_version and rec_prompt_ver and rec_prompt_ver != prompt_version:
        return False

    rec_provider_key = record.get("provider_key")
    if provider_key and rec_provider_key and rec_provider_key != provider_key:
        return False

    rec_provider_model = record.get("provider_model")
    return not (provider_model and rec_provider_model and rec_provider_model != provider_model)

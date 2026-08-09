"""PR-41 final correctness pass regression tests.

Covers the last audit findings that shipped in this pass:

- translation validity: ``raw_generation_id`` is provenance (never equality),
  stored languages fail closed, output-shaping settings (``style_preset`` /
  ``consistency_mode`` / ``json_output`` / ``honorific_policy``) participate
  in the validity contract;
- CAS activation: the filesystem pointer read + expected-id verification +
  replacement happen inside the per-novel inter-process lock (two
  independent storage instances cannot both activate from the same captured
  pointer), and the S3 backend compares object **bytes** (never an ETag
  alone) plus a conditional ``If-Match`` PUT;
- disposition accounting: scoped ``not_fetched`` unavailable entries keep the
  disposition map consistent and never count as failed refreshes; aggregate
  counters are derived from the disposition map; a missing or empty map
  cannot silently bypass reconciliation;
- catalog stable identity: ``save_raw_chapter`` derives metadata ordering and
  the native (unprefixed) source episode id for new rows, never writes a
  zero when metadata exists, and translation saves never alter source
  ordering.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from novelai.services.catalog_service import CatalogService
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.sources import SourceAdapter
from novelai.storage.backends.s3 import S3Backend
from novelai.storage.generations import GenerationConflictError
from novelai.storage.service import StorageService
from novelai.translation.run_manifest import is_translation_valid

_TMP = Path(__file__).resolve().parent / ".tmp" / "pr41_final"


def _fresh_storage() -> StorageService:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return StorageService(d)


# ---------------------------------------------------------------------------
# Translation validity contract (is_translation_valid)
# ---------------------------------------------------------------------------


def _lineage_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "source_hash": "src-hash",
        "source_content_hash": "src-hash",
        "source_structure_hash": "struct-hash",
        "source_image_manifest_hash": "img-hash",
        "glossary_hash": "gloss-1",
        "prompt_template_version": "prompt-v9",
        "qa_policy_fingerprint": "qa-fp-v1",
        "provider_key": "p",
        "provider_model": "m",
        "translation_run_id": "run-1",
        "raw_generation_id": "gen-1",
        "source_episode_id": "ep-1",
        "source_language": "ja",
        "target_language": "en",
        "style_preset": "literary",
        "consistency_mode": True,
        "json_output": False,
        "honorific_policy": "default_honorifics",
        "output_hash": "out-hash",
        "text": "translated",
    }
    record.update(overrides)
    return record


def _valid(record: dict[str, Any], **overrides: Any) -> bool:
    args: dict[str, Any] = {
        "source_text_hash": "src-hash",
        "active_glossary_hash": "gloss-1",
        "prompt_version": "prompt-v9",
        "provider_key": "p",
        "provider_model": "m",
        "record": record,
        "active_raw_generation_id": "gen-2",
        "source_structure_hash": "struct-hash",
        "source_image_manifest_hash": "img-hash",
        "qa_policy_fingerprint": "qa-fp-v1",
        "source_language": "ja",
        "target_language": "en",
        "style_preset": "literary",
        "consistency_mode": True,
        "json_output": False,
        "honorific_policy": "default_honorifics",
    }
    args.update(overrides)
    return is_translation_valid(**args)


def test_reuse_valid_across_generation_activation() -> None:
    """Stored raw_generation_id (gen-1) vs active pointer (gen-2): valid.

    The generation id is provenance, not a validity gate: content-identical
    output stays reusable across activations and only content/policy changes
    force retranslation.
    """
    assert _valid(_lineage_record())


def test_missing_stored_language_fails_closed() -> None:
    assert not _valid(_lineage_record(source_language=None))
    assert not _valid(_lineage_record(target_language=None))
    # A supplied-but-different language is also invalid.
    assert not _valid(_lineage_record(source_language="zh"))


def test_style_preset_change_retranslates() -> None:
    assert not _valid(_lineage_record(style_preset="casual"))
    # Default to literary or literary to default retranslates symmetrically.
    assert not _valid(_lineage_record(style_preset=None))


def test_effective_output_policy_symmetry() -> None:
    """Default-to-non-default and non-default-to-default transitions retranslate."""
    # literary -> default (None)
    assert not is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        record=_lineage_record(style_preset="literary"),
        style_preset=None,
    )
    # default (None) -> literary
    assert not is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        record=_lineage_record(style_preset=None),
        style_preset="literary",
    )
    # retain -> default (None) honorific
    assert not is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        record=_lineage_record(honorific_policy="retain"),
        honorific_policy=None,
    )


def test_consistency_mode_change_retranslates() -> None:
    assert not _valid(_lineage_record(consistency_mode=False))
    # Missing or non-boolean stored value fails closed.
    assert not _valid(_lineage_record(consistency_mode=None))
    assert not _valid(_lineage_record(consistency_mode="true"))


def test_json_output_change_retranslates() -> None:
    assert not _valid(_lineage_record(json_output=True))
    assert not _valid(_lineage_record(json_output=None))


def test_honorific_policy_change_retranslates() -> None:
    assert not _valid(_lineage_record(honorific_policy="none"))
    # Missing stored value fails closed.
    assert not _valid(_lineage_record(honorific_policy=None))


def test_honorific_policy_compares_normalized_identity() -> None:
    """Spelling variation (case / whitespace) is not a policy change."""
    assert _valid(_lineage_record(honorific_policy="  Default_Honorifics "))


def test_contract_without_output_shaping_dims_skips_them() -> None:
    """None on the current contract means the dimension is not required."""
    record = _lineage_record()
    for key in ("style_preset", "consistency_mode", "json_output", "honorific_policy"):
        record.pop(key)
    assert is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        record=record,
    )


# ---------------------------------------------------------------------------
# Effective output-policy resolution — symmetric UNSET vs DEFAULT semantics
# ---------------------------------------------------------------------------


def _resolve_policy(**overrides: Any) -> tuple[Any, ...]:
    from novelai.services.orchestration.translation import _resolve_effective_output_policy

    args: dict[str, Any] = {
        "style_preset": None,
        "consistency_mode": None,
        "json_output": None,
        "honorific_policy": None,
        "workflow_defaults": {},
    }
    args.update(overrides)
    return _resolve_effective_output_policy(**args)


def test_explicit_consistency_false_not_overridden_by_workflow_default() -> None:
    """An explicit ``consistency_mode=False`` from the caller is the effective
    identity even when the workflow default is ``True``: only an omitted value
    (None) falls back to the default."""
    style, consistency, _, _ = _resolve_policy(
        consistency_mode=False,
        workflow_defaults={"consistency_mode": True, "style_preset": "literary"},
    )
    assert consistency is False
    assert style == "literary"


def test_explicit_consistency_true_overrides_workflow_default_false() -> None:
    _, consistency, _, _ = _resolve_policy(
        consistency_mode=True,
        workflow_defaults={"consistency_mode": False},
    )
    assert consistency is True


def test_omitted_consistency_falls_back_to_workflow_default() -> None:
    _, consistency, _, _ = _resolve_policy(workflow_defaults={"consistency_mode": True})
    assert consistency is True


def test_explicit_json_output_preserved_and_omitted_is_false() -> None:
    """json_output has no workflow default: an explicit value passes through
    and an omitted value resolves to False (no default can override)."""
    _, _, json_out, _ = _resolve_policy(json_output=True)
    assert json_out is True
    _, _, json_out, _ = _resolve_policy(json_output=False)
    assert json_out is False
    _, _, json_out, _ = _resolve_policy()
    assert json_out is False


def test_explicit_style_preset_and_honorific_override_workflow_defaults() -> None:
    style, _, _, honorific = _resolve_policy(
        style_preset="casual",
        honorific_policy="none",
        workflow_defaults={"style_preset": "literary", "honorific_policy": "default_honorifics"},
    )
    assert style == "casual"
    assert honorific == "none"


def test_omitted_style_and_honorific_fall_back_to_workflow_defaults() -> None:
    style, _, _, honorific = _resolve_policy(
        workflow_defaults={"style_preset": "literary", "honorific_policy": "default_honorifics"}
    )
    assert style == "literary"
    assert honorific == "default_honorifics"


# ---------------------------------------------------------------------------
# Source-episode lineage — native episode id survives the storage round trip
# ---------------------------------------------------------------------------


def _lineage_kwargs(
    storage: StorageService,
    *,
    chapter_id: str,
    source_episode_id: str | None = None,
) -> dict[str, Any]:
    from novelai.services.orchestration.translation import _translation_lineage_kwargs

    return _translation_lineage_kwargs(
        storage,
        "novel-1",
        chapter_id,
        raw_text="raw text",
        translated="translated",
        translation_run_id="run-1",
        raw_generation_id="gen-1",
        source_language="ja",
        target_language="en",
        style_preset="literary",
        consistency_mode=True,
        json_output=False,
        qa_policy_fingerprint="qa-fp-v1",
        auto_activate=True,
        honorific_policy="default_honorifics",
        source_episode_id=source_episode_id,
    )


def test_lineage_uses_native_episode_id_not_logical_prefix() -> None:
    """A Kakuyomu chapter keeps its native episode id (``16818093075570329555``)
    in the stored translation lineage instead of the logical
    ``kakuyomu:16818093075570329555`` prefix: ``load_chapter`` never exposes
    the field, so the caller-threaded native id must win."""
    storage = _fresh_storage()
    kwargs = _lineage_kwargs(
        storage,
        chapter_id="kakuyomu:16818093075570329555",
        source_episode_id="16818093075570329555",
    )
    assert kwargs["source_episode_id"] == "16818093075570329555"


def test_stored_overlay_version_contains_glossary_and_prompt_version() -> None:
    storage = _fresh_storage()
    storage.save_metadata("novel-overlay", {"glossary_hash": "gloss-abc"})
    storage.save_translated_chapter(
        "novel-overlay",
        "1",
        "translated text",
        provider_key="provider-x",
        provider_model="model-y",
        glossary_hash="gloss-abc",
        prompt_template_version="prompt-v123",
        source_hash="src-hash-1",
        source_language="ja",
        target_language="en",
    )
    loaded = storage.load_translated_chapter("novel-overlay", "1")
    assert loaded is not None
    assert loaded.get("glossary_hash") == "gloss-abc"
    assert loaded.get("prompt_template_version") == "prompt-v123"


def test_corrupt_active_generation_pointer_fails_closed() -> None:
    from novelai.storage.generations import (
        PointerState,
        _inspect_active_generation_pointer,
        _parse_active_generation_id,
    )

    assert _inspect_active_generation_pointer(None) == (PointerState.MISSING, None)
    assert _inspect_active_generation_pointer(b"")[0] == PointerState.CORRUPT
    assert _inspect_active_generation_pointer(b"invalid json")[0] == PointerState.CORRUPT
    assert _inspect_active_generation_pointer(b'{"active_generation_id": ""}')[0] == PointerState.CORRUPT
    assert _parse_active_generation_id(b"invalid json") is None


def test_commit_generation_strictly_requires_dispositions() -> None:
    storage = _fresh_storage()
    novel_id = "novel-no-disp"
    generation_id = "gen-123"
    storage.stage_generation_metadata(novel_id, generation_id, {"title": "T", "source_novel_id": novel_id})
    storage.stage_generation_source_state(novel_id, generation_id, {"chapters": []})
    storage.stage_generation_chapter_index(novel_id, generation_id, [{"id": "1"}])
    storage.stage_generation_chapter(novel_id, generation_id, "1", {"id": "1", "raw": {"text": "raw"}})
    # chapter_dispositions=None must be rejected by the normal path (no bypass).
    with pytest.raises(RuntimeError, match="has no chapter_dispositions"):
        storage.commit_generation(novel_id, generation_id, chapter_dispositions=None)


def test_lineage_numeric_episode_id_regression() -> None:
    """A Syosetu-style numeric episode id round-trips as a plain string even
    when the resolved logical id is identical; no prefix is invented."""
    storage = _fresh_storage()
    kwargs = _lineage_kwargs(storage, chapter_id="42", source_episode_id="42")
    assert kwargs["source_episode_id"] == "42"


def test_lineage_without_native_id_falls_back_to_logical_id() -> None:
    """Imported documents have no source-native episode identity: the logical
    chapter id is the honest lineage value."""
    storage = _fresh_storage()
    kwargs = _lineage_kwargs(storage, chapter_id="kakuyomu:16818093075570329555")
    assert kwargs["source_episode_id"] == "kakuyomu:16818093075570329555"


def test_resolve_chapter_selection_exposes_native_episode_id() -> None:
    """``ResolvedChapterSelection.source_episode_id`` is the source-native
    identifier, independent of the logical chapter id the storage uses."""
    from novelai.utils.chapter_selection import resolve_chapter_selection

    resolved = resolve_chapter_selection(
        {
            "chapters": [
                {"id": "kakuyomu:16818093075570329555", "source_episode_id": "16818093075570329555", "title": "C1"},
                {"id": "42", "num": 42, "title": "C2"},
            ]
        },
        "all",
    )
    assert [record.source_episode_id for record in resolved] == ["16818093075570329555", "42"]
    assert [record.chapter_id for record in resolved] == ["kakuyomu:16818093075570329555", "42"]


# ---------------------------------------------------------------------------
# CAS activation — filesystem lock barrier across independent instances
# ---------------------------------------------------------------------------


def _stage_cas_generation(storage: StorageService, novel_id: str, generation_id: str, chapter_id: str) -> None:
    storage.create_generation_stage(
        novel_id,
        generation_id,
        source_key="test_source",
        source_work_id=novel_id,
        mode="full",
        expected_chapters=1,
    )
    storage.stage_generation_metadata(novel_id, generation_id, {"title": "T", "source_novel_id": novel_id})
    storage.stage_generation_source_state(novel_id, generation_id, {"chapters": []})
    storage.stage_generation_chapter_index(
        novel_id, generation_id, [{"id": chapter_id, "chapter_id": chapter_id, "title": "C", "url": "u"}]
    )
    storage.stage_generation_chapter(
        novel_id, generation_id, chapter_id, {"id": chapter_id, "raw": {"text": f"raw {chapter_id}"}}
    )


def test_cas_stale_capture_from_other_instance_never_overwrites() -> None:
    """Two independent StorageService instances over the same base directory.

    B activates first (captured ``starting=None``). A — a separate instance,
    equivalent to a separate process — captured the same ``None`` before B
    activated and must lose the race inside the per-novel inter-process
    lock: the pointer re-read under the lock disagrees with A's capture, so
    A raises and the winner's pointer survives.
    """
    base = _TMP / uuid4().hex[:8]
    base.mkdir(parents=True, exist_ok=True)
    novel_id = "novel-cas-two-instance"

    instance_b = StorageService(base)
    _stage_cas_generation(instance_b, novel_id, "gen-B", "2")
    instance_b.commit_generation(novel_id, "gen-B", chapter_dispositions={"2": "fetched_new"})
    assert instance_b.resolve_active_generation_id(novel_id) == "gen-B"

    instance_a = StorageService(base)
    _stage_cas_generation(instance_a, novel_id, "gen-A", "1")
    # A captured the pointer before B activated (starting=None) and must
    # fail against the now-active gen-B — even though A is a different
    # instance/process than the one that wrote the winner.
    with pytest.raises(GenerationConflictError):
        instance_a.commit_generation(
            novel_id, "gen-A", chapter_dispositions={"1": "fetched_new"}, starting_active_generation_id=None
        )

    observer = StorageService(base)
    assert observer.resolve_active_generation_id(novel_id) == "gen-B"
    active = observer.get_active_generation(novel_id)
    assert active is not None
    assert active.generation_id == "gen-B"


# ---------------------------------------------------------------------------
# S3 CAS — body-verified compare-and-swap
# ---------------------------------------------------------------------------


class _FakeS3Client:
    """Deterministic stand-in for the boto3 S3 client used by CAS tests."""

    def __init__(
        self,
        stored: dict[str, bytes] | None = None,
        *,
        etag: str = '"etag-1"',
        put_failure_status: int | None = None,
    ) -> None:
        self.stored: dict[str, bytes] = dict(stored or {})
        self.etags: dict[str, str] = {key: etag for key in self.stored}
        self.etag = etag
        self.put_failure_status = put_failure_status
        self.put_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.get_calls.append(kwargs)
        key = kwargs["Key"]
        if key not in self.stored:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                "GetObject",
            )

        class _Body:
            def __init__(self, data: bytes) -> None:
                self._data = data

            def read(self) -> bytes:
                return self._data

        return {"Body": _Body(self.stored[key]), "ETag": self.etags[key]}

    def put_object(self, **kwargs: Any) -> None:
        self.put_calls.append(kwargs)
        key = kwargs["Key"]
        # Emulate S3 conditional-write preconditions.
        if kwargs.get("IfNoneMatch") == "*" and key in self.stored:
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}},
                "PutObject",
            )
        if "IfMatch" in kwargs and self.etags.get(key) != kwargs["IfMatch"]:
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}},
                "PutObject",
            )
        if self.put_failure_status == 412:
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}},
                "PutObject",
            )
        if self.put_failure_status is not None:
            raise ClientError(
                {"Error": {"Code": "InternalError"}, "ResponseMetadata": {"HTTPStatusCode": self.put_failure_status}},
                "PutObject",
            )
        self.stored[key] = kwargs["Body"]
        self.etags[key] = self.etag


def _s3_backend(client: _FakeS3Client) -> S3Backend:
    backend = object.__new__(S3Backend)
    backend._BACKING = "s3"  # type: ignore[attr-defined]
    backend._bucket = "test-bucket"  # type: ignore[attr-defined]
    backend._key_prefix = ""  # type: ignore[attr-defined]
    backend._client = client  # type: ignore[attr-defined]
    return backend


def test_s3_cas_body_mismatch_refuses_swap() -> None:
    """An ETag alone is never the comparison: differing bytes must refuse."""
    client = _FakeS3Client(stored={"active.json": b"older-bytes"})
    backend = _s3_backend(client)
    assert backend.compare_and_swap("active.json", b"expected-bytes", b"new") is False
    assert client.put_calls == []


def test_s3_cas_missing_object_refuses_swap() -> None:
    client = _FakeS3Client(stored={})
    backend = _s3_backend(client)
    assert backend.compare_and_swap("active.json", b"expected-bytes", b"new") is False
    assert client.put_calls == []


def test_s3_cas_body_match_puts_conditionally() -> None:
    client = _FakeS3Client(stored={"active.json": b"expected-bytes"})
    backend = _s3_backend(client)
    assert backend.compare_and_swap("active.json", b"expected-bytes", b"new-bytes") is True
    assert len(client.put_calls) == 1
    call = client.put_calls[0]
    assert call["Key"] == "active.json"
    assert call["Body"] == b"new-bytes"
    # The conditional PUT is pinned to the exact observed ETag.
    assert call["IfMatch"] == '"etag-1"'
    assert "IfNoneMatch" not in call


def test_s3_cas_expected_none_uses_conditional_create() -> None:
    client = _FakeS3Client(stored={})
    backend = _s3_backend(client)
    assert backend.compare_and_swap("active.json", None, b"first-writer") is True
    assert len(client.put_calls) == 1
    assert client.put_calls[0]["IfNoneMatch"] == "*"
    # A second writer with expected=None must lose (object now exists).
    assert backend.compare_and_swap("active.json", None, b"second-writer") is False


def test_s3_cas_precondition_failed_returns_false() -> None:
    client = _FakeS3Client(stored={"active.json": b"expected-bytes"}, put_failure_status=412)
    backend = _s3_backend(client)
    assert backend.compare_and_swap("active.json", b"expected-bytes", b"new") is False


def test_s3_cas_other_client_error_re_raised() -> None:
    client = _FakeS3Client(stored={"active.json": b"expected-bytes"}, put_failure_status=500)
    backend = _s3_backend(client)
    with pytest.raises(ClientError):
        backend.compare_and_swap("active.json", b"expected-bytes", b"new")


# ---------------------------------------------------------------------------
# Disposition accounting — storage-level contract exercised by the crawler
# ---------------------------------------------------------------------------


def _stage_generation(
    storage: StorageService,
    novel_id: str,
    generation_id: str,
    *,
    index_ids: list[str],
    bundles: list[str],
    unavailable: dict[str, str] | None = None,
    refresh_failed: dict[str, str] | None = None,
) -> None:
    storage.create_generation_stage(
        novel_id,
        generation_id,
        source_key="test_source",
        source_work_id=novel_id,
        mode="update",
        expected_chapters=len(index_ids),
    )
    storage.stage_generation_metadata(novel_id, generation_id, {"title": "T", "source_novel_id": novel_id})
    storage.stage_generation_source_state(novel_id, generation_id, {"chapters": []})
    storage.stage_generation_chapter_index(
        novel_id,
        generation_id,
        [{"id": cid, "chapter_id": cid, "title": f"C{cid}", "url": f"http://example.test/{cid}"} for cid in index_ids],
    )
    for cid in bundles:
        storage.stage_generation_chapter(novel_id, generation_id, cid, {"id": cid, "raw": {"text": f"raw {cid}"}})
    for cid, category in (unavailable or {}).items():
        storage.record_unavailable_chapter(
            novel_id,
            generation_id,
            cid,
            reason="current index entry has no usable raw bundle after a scoped crawl",
            error_category=category,
        )
    for cid, category in (refresh_failed or {}).items():
        storage.record_refresh_failed_chapter(
            novel_id,
            generation_id,
            cid,
            reason="fetch failed: connection reset",
            error_category=category,
        )


def test_scoped_unavailable_keeps_disposition_and_counts() -> None:
    """The crawler marks an index chapter without a bundle as unavailable in
    BOTH the explicit record and the disposition map; activation succeeds and
    ``failed_refresh_count`` stays 0 because ``not_fetched`` is not an HTTP
    fetch failure."""
    storage = _fresh_storage()
    novel_id = "novel-scoped-unavailable"
    _stage_generation(
        storage,
        novel_id,
        "gen-1",
        index_ids=["1", "2"],
        bundles=["1"],
        unavailable={"2": "not_fetched"},
    )
    manifest = storage.commit_generation(
        novel_id,
        "gen-1",
        chapter_dispositions={"1": "fetched_new", "2": "unavailable"},
    )
    assert manifest.unavailable_chapter_ids == ["2"]
    assert manifest.chapter_dispositions is not None
    assert manifest.chapter_dispositions["2"] == "unavailable"
    assert manifest.chapter_dispositions["1"] == "fetched_new"
    # Legacy failed_chapters == unavailable entries; the explicit
    # failed-refresh counter excludes deliberate not-fetched entries.
    assert manifest.failed_chapters == 1
    assert manifest.unavailable_count == 1
    assert manifest.failed_refresh_count == 0
    assert manifest.saved_chapters == 1
    assert storage.resolve_active_generation_id(novel_id) == "gen-1"


def test_failed_refresh_count_aggregates_real_failures() -> None:
    """A refresh failure with a carried bundle counts as failed refresh."""
    storage = _fresh_storage()
    novel_id = "novel-refresh-failed"
    _stage_generation(
        storage,
        novel_id,
        "gen-1",
        index_ids=["1", "2"],
        bundles=["1", "2"],
        refresh_failed={"2": "server_error"},
    )
    manifest = storage.commit_generation(
        novel_id,
        "gen-1",
        chapter_dispositions={"1": "fetched_new", "2": "refresh_failed_retained"},
    )
    assert manifest.refresh_failed_chapter_ids == ["2"]
    assert manifest.refresh_failed_retained_count == 1
    assert manifest.failed_refresh_count == 1
    assert manifest.unavailable_count == 0
    assert storage.resolve_active_generation_id(novel_id) == "gen-1"


def test_commit_without_disposition_map_raises() -> None:
    """Modern normal commits must reconcile a canonical disposition map."""
    storage = _fresh_storage()
    novel_id = "novel-no-map"
    _stage_generation(storage, novel_id, "gen-1", index_ids=["1"], bundles=["1"])
    with pytest.raises(RuntimeError, match="no chapter_dispositions"):
        storage.commit_generation(novel_id, "gen-1")


def test_empty_disposition_map_fails_on_the_map_itself() -> None:
    """An explicitly empty disposition map is rejected on the map itself,
    even when every indexed chapter has a complete staged bundle: it must
    never silently disable disposition reconciliation."""
    storage = _fresh_storage()
    novel_id = "novel-empty-map"
    _stage_generation(storage, novel_id, "gen-1", index_ids=["1", "2"], bundles=["1", "2"])
    with pytest.raises(RuntimeError, match="empty chapter_dispositions map"):
        storage.commit_generation(novel_id, "gen-1", chapter_dispositions={})
    # The bypass never becomes active.
    assert storage.resolve_active_generation_id(novel_id) is None


def test_non_canonical_disposition_value_fails() -> None:
    """A disposition value outside the canonical set cannot pass validation:
    ``derive_counts_from_dispositions`` would silently ignore it, so the
    validator rejects it explicitly."""
    storage = _fresh_storage()
    novel_id = "novel-bad-disposition"
    _stage_generation(storage, novel_id, "gen-1", index_ids=["1", "2"], bundles=["1", "2"])
    with pytest.raises(RuntimeError, match="dispositions_use_canonical_names"):
        storage.commit_generation(
            novel_id,
            "gen-1",
            chapter_dispositions={"1": "banana", "2": "banana"},
        )
    assert storage.resolve_active_generation_id(novel_id) is None


def test_missing_disposition_key_fails() -> None:
    """Every current-index chapter must appear exactly once in the map."""
    storage = _fresh_storage()
    novel_id = "novel-missing-disp"
    _stage_generation(storage, novel_id, "gen-1", index_ids=["1", "2"], bundles=["1", "2"])
    with pytest.raises(RuntimeError, match="disposition_for_every_index_entry"):
        storage.commit_generation(novel_id, "gen-1", chapter_dispositions={"1": "fetched_new"})
    assert storage.resolve_active_generation_id(novel_id) is None


def test_extra_disposition_key_fails() -> None:
    """A disposition for a chapter outside the current index is rejected."""
    storage = _fresh_storage()
    novel_id = "novel-extra-disp"
    _stage_generation(storage, novel_id, "gen-1", index_ids=["1", "2"], bundles=["1", "2"])
    with pytest.raises(RuntimeError, match="no_extra_dispositions"):
        storage.commit_generation(
            novel_id,
            "gen-1",
            chapter_dispositions={"1": "fetched_new", "2": "fetched_new", "9": "fetched_new"},
        )
    assert storage.resolve_active_generation_id(novel_id) is None


def test_tampered_aggregate_count_fails_validation() -> None:
    """Aggregate counters must reconcile with the disposition map: a manifest
    whose ``saved_chapters`` disagrees with the derived fetched count fails
    pre-activation validation."""
    from novelai.storage.generations import _load_manifest, _save_manifest

    storage = _fresh_storage()
    novel_id = "novel-tampered-count"
    _stage_generation(storage, novel_id, "gen-1", index_ids=["1", "2"], bundles=["1", "2"])
    manifest = _load_manifest(storage, novel_id, "gen-1")
    assert manifest is not None
    manifest.chapter_dispositions = {"1": "fetched_new", "2": "fetched_new"}
    manifest.saved_chapters = 5  # disagrees with derived fetched_count == 2
    _save_manifest(storage, novel_id, "gen-1", manifest)

    result = storage.validate_generation_activation(novel_id, "gen-1")
    assert not result.is_valid
    assert "derived_fetched_count_matches_manifest" in [check.name for check in result.failed_checks()]


def test_mismatched_disposition_against_explicit_unavailable_fails() -> None:
    """A recorded-unavailable chapter labeled with an available disposition
    erases its own unavailable record and must fail validation.

    The crawler fix keeps the disposition map in lockstep with the explicit
    record (``record_unavailable_chapter`` + ``DISPOSITION_UNAVAILABLE``
    together); a disagreeing map can never silently wipe the record, because
    the derived unavailable list then leaves the chapter unresolvable and
    the commit is rejected before activation.
    """
    storage = _fresh_storage()
    novel_id = "novel-disp-mismatch"
    _stage_generation(storage, novel_id, "gen-1", index_ids=["1", "2"], bundles=["1"], unavailable={"2": "not_fetched"})
    # Baseline: the explicit unavailable record alone satisfies membership.
    result = storage.validate_generation_activation(novel_id, "gen-1")
    assert result.is_valid

    # A map that disagrees (carried_unselected instead of unavailable)
    # removes "2" from the derived unavailable list -> unresolvable index
    # entry -> commit rejected.
    with pytest.raises(RuntimeError, match="every_index_entry_resolved"):
        storage.commit_generation(
            novel_id,
            "gen-1",
            chapter_dispositions={"1": "fetched_new", "2": "carried_unselected"},
        )
    # The loser is never activated.
    assert storage.resolve_active_generation_id(novel_id) is None


# ---------------------------------------------------------------------------
# Crawler dispositions — fetched_new vs fetched_replaced
# ---------------------------------------------------------------------------


class _CrawlSource(SourceAdapter):
    def __init__(self, *, chapter_count: int = 4, payloads: dict[str, dict[str, Any]] | None = None) -> None:
        self.source_key = "test_source"
        self._chapter_count = chapter_count
        self._payloads = payloads or {}
        self.fetch_count = 0

    def can_handle(self, identifier_or_url: str) -> bool:
        return False

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        return {
            "novel_id": url,
            "title": f"Novel {url}",
            "source_key": self.source_key,
            "source_novel_id": url,
            "source_url": f"https://example.test/{url}",
            "chapters": [
                {
                    "id": str(i),
                    "num": i,
                    "sequence_number": i,
                    "title": f"Chapter {i}",
                    "url": f"http://example.test/{url}/{i}",
                }
                for i in range(1, self._chapter_count + 1)
            ],
        }

    async def fetch_chapter(self, url: str) -> str:
        return "Content for " + url

    async def fetch_chapter_payload(self, url: str, *, on_retry: Any = None) -> Mapping[str, Any]:
        self.fetch_count += 1
        payload = self._payloads.get(url)
        if payload is not None:
            return payload
        return {"text": f"Content for {url}", "images": []}

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> Mapping[str, Any]:
        return {"url": url, "content": b"", "content_type": "image/png"}


class _NoopTranslationService:
    async def translate_chapters(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"status": "noop"}


def _make_orchestrator(storage: StorageService, source: _CrawlSource) -> Any:
    from novelai.services.novel_orchestration_service import NovelOrchestrationService

    return NovelOrchestrationService(
        storage=storage,
        translation=_NoopTranslationService(),  # type: ignore[arg-type]
        source_factory=lambda _key: source,
        settings_service=PreferencesService(),
        translation_cache=TranslationCache(storage.base_dir),
        usage_service=UsageService(storage.base_dir),
    )


@pytest.fixture(autouse=True)
def _stub_catalog_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    from novelai.services import catalog_service
    from novelai.services.orchestration import crawler as crawler_module

    def _noop(novel_id: str, storage: Any, *, context: str, **kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(catalog_service, "safely_refresh_catalog_projection_after_storage_write", _noop)
    monkeypatch.setattr(crawler_module, "safely_refresh_catalog_projection_after_storage_write", _noop)


async def _full_crawl(storage: StorageService, source: _CrawlSource, novel_id: str) -> str:
    storage.save_metadata(
        novel_id,
        {
            "novel_id": novel_id,
            "title": f"Seeded {novel_id}",
            "author": "Seed Author",
            "source_key": "test_source",
            "chapters": [
                {
                    "id": str(i),
                    "num": i,
                    "sequence_number": i,
                    "title": f"Chapter {i}",
                    "url": f"http://example.test/{novel_id}/{i}",
                }
                for i in range(1, source._chapter_count + 1)
            ],
        },
    )
    result = await _make_orchestrator(storage, source).scrape_chapters("test_source", novel_id, "all", mode="full")
    assert result["succeeded"] == source._chapter_count
    return result["generation_id"]


@pytest.mark.asyncio
async def test_full_crawl_labels_every_chapter_fetched_new() -> None:
    storage = _fresh_storage()
    source = _CrawlSource(chapter_count=3)
    novel_id = "novel-fetched-new"
    gen_id = await _full_crawl(storage, source, novel_id)
    manifest = storage.load_generation_manifest(novel_id, gen_id)
    assert manifest is not None
    assert manifest.chapter_dispositions == {"1": "fetched_new", "2": "fetched_new", "3": "fetched_new"}
    assert manifest.saved_chapters == 3
    assert manifest.unchanged_selected_count == 0
    assert manifest.unavailable_count == 0
    assert manifest.failed_refresh_count == 0


@pytest.mark.asyncio
async def test_update_crawl_distinguishes_replaced_and_unchanged() -> None:
    storage = _fresh_storage()
    source = _CrawlSource(chapter_count=3)
    novel_id = "novel-fetched-replaced"
    await _full_crawl(storage, source, novel_id)

    changed = _CrawlSource(
        chapter_count=3,
        payloads={"http://example.test/novel-fetched-replaced/1": {"text": "CHANGED content for chapter 1"}},
    )
    result = await _make_orchestrator(storage, changed).scrape_chapters("test_source", novel_id, "all", mode="update")
    assert result["succeeded"] == 1
    assert result["skipped"] == 2
    assert result["failed"] == 0

    manifest = storage.load_generation_manifest(novel_id, result["generation_id"])
    assert manifest is not None
    assert manifest.chapter_dispositions == {
        "1": "fetched_replaced",
        "2": "unchanged_selected",
        "3": "unchanged_selected",
    }
    assert manifest.saved_chapters == 1
    assert manifest.unchanged_selected_count == 2
    assert manifest.reused_chapters == 2
    assert manifest.unavailable_count == 0
    assert manifest.failed_chapters == 0
    assert manifest.failed_refresh_count == 0
    assert manifest.removed_count == 0


# ---------------------------------------------------------------------------
# Catalog DB — stable identity derivation and non-mutation
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from novelai.db.base import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def storage(tmp_path):
    return StorageService(tmp_path)


@pytest.fixture()
def catalog(storage, db_session):
    return CatalogService(storage=storage, session=db_session)


def _seed_catalog_novel(
    catalog: CatalogService,
    storage: StorageService,
    db_session: Any,
    slug: str,
    chapters: list[dict[str, Any]],
) -> None:
    meta = {
        "novel_id": slug,
        "title": f"Novel {slug}",
        "source_key": "kakuyomu",
        "chapters": chapters,
    }
    storage.save_metadata(slug, meta)
    catalog.get_or_create_novel(slug, meta)
    db_session.commit()


def test_save_raw_chapter_derives_metadata_ordering_and_native_episode(
    catalog: CatalogService, db_session: Any, storage: StorageService
) -> None:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    slug = "kakuyomu-novel"
    _seed_catalog_novel(
        catalog,
        storage,
        db_session,
        slug,
        [
            {
                "id": "kakuyomu:ep-42",
                "num": 3,
                "sequence_number": 3,
                "source_episode_id": "ep-42",
                "title": "Ep 42",
                "url": "https://kakuyomu.jp/works/x/episodes/42",
            }
        ],
    )

    # Omitted ordering must be derived from metadata, never defaulted to 0.
    catalog.save_raw_chapter(slug, "kakuyomu:ep-42", "content", title="Ep 42")
    db_session.commit()

    novel = db_session.query(Novel).filter_by(slug=slug).one()
    row = db_session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id="kakuyomu:ep-42").one()
    assert row.chapter_number == 3
    assert row.sequence_number == 3
    # Native episode id is persisted unprefixed; the logical id carries the
    # kakuyomu: prefix, the source_episode_id never does.
    assert row.source_episode_id == "ep-42"


def test_save_raw_chapter_omission_never_zeroes_existing_ordering(
    catalog: CatalogService, db_session: Any, storage: StorageService
) -> None:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    slug = "ordering-novel"
    _seed_catalog_novel(catalog, storage, db_session, slug, [{"id": "1", "num": 1}])

    catalog.save_raw_chapter(slug, "1", "first", title="C1", chapter_number=2, sequence_number=2)
    db_session.commit()
    novel = db_session.query(Novel).filter_by(slug=slug).one()
    row = db_session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id="1").one()
    assert row.chapter_number == 2
    assert row.sequence_number == 2

    # Re-save with omitted ordering: must preserve, not zero.
    catalog.save_raw_chapter(slug, "1", "second content", title="C1")
    db_session.commit()
    rows = db_session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id="1").all()
    assert len(rows) == 1  # still the same stable row
    assert rows[0].chapter_number == 2
    assert rows[0].sequence_number == 2


def test_save_raw_chapter_reorder_updates_sequence_in_place(
    catalog: CatalogService, db_session: Any, storage: StorageService
) -> None:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    slug = "reorder-novel"
    _seed_catalog_novel(catalog, storage, db_session, slug, [{"id": "1", "num": 1}])

    catalog.save_raw_chapter(slug, "1", "content", title="C1", sequence_number=1)
    db_session.commit()
    novel = db_session.query(Novel).filter_by(slug=slug).one()
    first = db_session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id="1").one()
    first_id = first.id

    catalog.save_raw_chapter(slug, "1", "content", title="C1", sequence_number=5)
    db_session.commit()
    rows = db_session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id="1").all()
    assert len(rows) == 1
    assert rows[0].id == first_id  # same row, reordered in place
    assert rows[0].sequence_number == 5


def test_translation_save_never_alters_source_ordering(
    catalog: CatalogService, db_session: Any, storage: StorageService
) -> None:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    slug = "translation-novel"
    _seed_catalog_novel(catalog, storage, db_session, slug, [{"id": "1", "num": 3, "sequence_number": 3}])

    catalog.save_raw_chapter(slug, "1", "raw content", title="C1")
    db_session.commit()
    catalog.save_translated_chapter(slug, "1", "translated content")
    db_session.commit()

    novel = db_session.query(Novel).filter_by(slug=slug).one()
    row = db_session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id="1").one()
    # Translation save carries no ordering input: source ordering untouched.
    assert row.chapter_number == 3
    assert row.sequence_number == 3

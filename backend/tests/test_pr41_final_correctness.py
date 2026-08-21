"""PR-41 final correctness pass regression tests.

Covers the last audit findings that shipped in this pass:

- translation validity: ``raw_generation_id`` is provenance (never equality),
  stored languages fail closed, output-shaping settings (``style_preset`` /
  ``consistency_mode`` / ``json_output`` / ``honorific_policy``) participate
  in the validity contract;
- R2 generation activation remains explicit and PostgreSQL-backed; legacy
  filesystem pointer/CAS coverage is replaced by the R2 catalog tests;
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

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from novelai.services.catalog_service import CatalogService
from novelai.storage.service import StorageService
from novelai.translation.run_manifest import _output_hash, is_translation_valid

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
    # Section 10: a valid record's output_hash is the hash of its stored text.
    # Overrides may intentionally break the pairing to exercise corruption.
    record["output_hash"] = _output_hash(str(record["text"]))
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


def test_qa_policy_fingerprint_change_retranslates() -> None:
    """A changed QA policy fingerprint invalidates the stored version."""
    assert not _valid(_lineage_record(qa_policy_fingerprint="qa-fp-v2"))
    # Missing stored fingerprint fails closed.
    assert not _valid(_lineage_record(qa_policy_fingerprint=None))


def test_source_structure_hash_change_retranslates() -> None:
    """A changed source structure hash invalidates the stored version."""
    assert not _valid(_lineage_record(source_structure_hash="struct-v2"))
    # Missing stored structure hash fails closed.
    assert not _valid(_lineage_record(source_structure_hash=None))


def test_source_image_manifest_hash_change_retranslates() -> None:
    """A changed source image manifest hash invalidates the stored version."""
    assert not _valid(_lineage_record(source_image_manifest_hash="img-v2"))
    # Missing stored image manifest hash fails closed.
    assert not _valid(_lineage_record(source_image_manifest_hash=None))


def test_output_hash_self_consistency_enforced() -> None:
    """Section 10: a stored output_hash must equal the hash of the stored text.

    The check runs even when the current contract does not supply an
    ``output_hash``: a mutated text with a stale hash is corrupted lineage and
    never reusable.
    """
    record = _lineage_record()
    assert _valid(record)
    corrupt = _lineage_record(text="mutated without re-hash")
    assert corrupt["output_hash"] != _output_hash(corrupt["text"])
    assert not _valid(corrupt)


def test_output_hash_legacy_record_without_hash_stays_valid() -> None:
    """Legacy policy: a version persisted before output hashing existed (no
    stored output_hash) is valid when the current contract does not require
    the dimension."""
    record = _lineage_record(output_hash=None)
    assert record.get("output_hash") is None
    assert _valid(record)


def test_output_hash_required_when_contract_supplies_it() -> None:
    """When the current contract supplies an output_hash the stored version
    must carry the same value; missing stored lineage fails closed."""
    record = _lineage_record(output_hash=None)
    assert not is_translation_valid(
        source_text_hash="src-hash",
        active_glossary_hash="gloss-1",
        prompt_version="prompt-v9",
        provider_key="p",
        provider_model="m",
        record=record,
        output_hash=_output_hash("translated"),
    )
    assert _valid(_lineage_record(), output_hash=_output_hash("translated"))


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

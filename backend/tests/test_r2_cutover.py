from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.services.r2_activation_service import GenerationConflictError, R2GenerationActivationService
from novelai.storage.artifacts import R2ArtifactRepository
from novelai.storage.backends.r2 import R2Storage
from novelai.storage.r2_backup import R2IncrementalBackupTarget
from novelai.storage.r2_cutover import RESET_CONFIRMATION, R2CutoverService, R2GarbageCollector
from novelai.storage.service import StorageService

boto3 = pytest.importorskip("boto3")
pytest.importorskip("moto")


@pytest.fixture()
def r2_clients():
    from moto import mock_aws

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="dokushodo")
        client.create_bucket(Bucket="dokushodo-backup")
        yield client


def _stores(client):
    return (
        R2Storage(bucket="dokushodo", endpoint_url=None, client=client),
        R2Storage(bucket="dokushodo-backup", endpoint_url=None, client=client),
    )


def test_cutover_inventory_and_reset_require_all_gates(r2_clients) -> None:
    application, backup = _stores(r2_clients)
    application.save("novels/n1/chapters/ch1/hash.json.gz", b"raw")
    backup.save("snapshots/old/manifest.json", b"{}")
    service = R2CutoverService(application=application, backup=backup)

    app_inventory, backup_inventory = service.inventory()
    assert app_inventory.object_count == 1
    assert backup_inventory.object_count == 1
    dry_run = service.reset(
        writers_frozen=False,
        identities_verified=False,
        confirmation=None,
        dry_run=True,
    )
    assert dry_run.dry_run is True
    assert application.exists("novels/n1/chapters/ch1/hash.json.gz")

    with pytest.raises(PermissionError):
        service.reset(
            writers_frozen=False,
            identities_verified=True,
            confirmation=RESET_CONFIRMATION,
            dry_run=False,
        )

    result = service.reset(
        writers_frozen=True,
        identities_verified=True,
        confirmation=RESET_CONFIRMATION,
        dry_run=False,
    )
    assert result.deleted_application_objects == 1
    assert result.deleted_backup_objects == 1
    assert application.list_keys("", recursive=True) == []
    assert backup.list_keys("", recursive=True) == []


def test_gc_honors_references_protection_and_grace_period(r2_clients) -> None:
    application, _ = _stores(r2_clients)
    application.save("novels/n1/chapters/keep.json.gz", b"keep")
    application.save("novels/n1/chapters/delete.json.gz", b"delete")
    now = datetime.now(UTC) + timedelta(days=8)
    collector = R2GarbageCollector(application)

    preview = collector.collect(
        referenced_keys={"novels/n1/chapters/keep.json.gz"},
        protected_keys=set(),
        now=now,
        grace_period=timedelta(days=7),
        dry_run=True,
    )
    assert preview.candidates == ("novels/n1/chapters/delete.json.gz",)
    assert application.exists("novels/n1/chapters/delete.json.gz")

    deleted = collector.collect(
        referenced_keys={"novels/n1/chapters/keep.json.gz"},
        protected_keys=set(),
        now=now,
        grace_period=timedelta(days=7),
        dry_run=False,
    )
    assert deleted.deleted == preview.candidates
    assert application.exists("novels/n1/chapters/keep.json.gz")
    assert not application.exists("novels/n1/chapters/delete.json.gz")


def test_incremental_backup_reuses_content_addressed_objects(r2_clients) -> None:
    source, target = _stores(r2_clients)
    source.save("novels/n1/chapters/ch1/hash.json.gz", b"immutable")
    source.save("runtime/cache.json", b"disposable")
    backup = R2IncrementalBackupTarget(
        source_bucket="dokushodo",
        target_bucket="dokushodo-backup",
        endpoint_url=None,
        region="us-east-1",
        source_access_key_id=None,
        source_secret_access_key=None,
        target_access_key_id=None,
        target_secret_access_key=None,
        source_client=r2_clients,
        target_client=r2_clients,
    )

    first = backup.create_snapshot()
    second = backup.create_snapshot()
    assert first.files_count == 1
    assert second.files_count == 1
    manifest = backup._load_manifest(second.snapshot_id)
    assert manifest["objects"][0]["reused"] is True
    assert target.list_keys("objects", recursive=True) == ["objects/novels/n1/chapters/ch1/hash.json.gz"]
    assert backup.verify_snapshot(second.snapshot_id).verified is True


def test_incremental_backup_retention_preserves_references_and_collects_orphans(r2_clients) -> None:
    source, target = _stores(r2_clients)
    source.save("novels/n1/chapters/keep.json.gz", b"keep")
    source.save("novels/n1/chapters/old.json.gz", b"old")
    backup = R2IncrementalBackupTarget(
        source_bucket="dokushodo",
        target_bucket="dokushodo-backup",
        endpoint_url=None,
        region="us-east-1",
        source_access_key_id=None,
        source_secret_access_key=None,
        target_access_key_id=None,
        target_secret_access_key=None,
        source_client=r2_clients,
        target_client=r2_clients,
    )

    first = backup.create_snapshot()
    r2_clients.delete_object(Bucket="dokushodo", Key="novels/n1/chapters/old.json.gz")
    second = backup.create_snapshot()
    first_manifest = backup._load_manifest(first.snapshot_id)
    first_manifest["created_at"] = "2020-01-01T00:00:00Z"
    r2_clients.put_object(
        Bucket="dokushodo-backup",
        Key=f"snapshots/{first.snapshot_id}/manifest.json",
        Body=json.dumps(first_manifest).encode("utf-8"),
    )

    deleted = backup.apply_retention(
        keep_count=1,
        min_successful=1,
        max_age_days=1,
        safety_grace_days=0,
    )

    assert deleted >= 2
    latest = backup.latest_snapshot()
    assert latest is not None
    assert latest.snapshot_id == second.snapshot_id
    assert target.exists("objects/novels/n1/chapters/keep.json.gz")
    assert not target.exists("objects/novels/n1/chapters/old.json.gz")


def test_generation_activation_verifies_objects_and_detects_conflicts(r2_clients) -> None:
    application, _ = _stores(r2_clients)
    storage = StorageService(backend=application)
    repository = R2ArtifactRepository(application)
    raw = repository.put_json(
        novel_id="n1",
        kind="chapters",
        identity="ch1",
        payload={"raw": {"text": "source"}},
    )
    translated = repository.put_json(
        novel_id="n1",
        kind="translations",
        identity="ch1",
        payload={"text": "translation", "version_id": "v1"},
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        novel = Novel(slug="n1", title="Novel", is_published=True, language="ja", publication_status="published")
        session.add(novel)
        session.flush()
        session.add(Chapter(novel_id=novel.id, logical_chapter_id="ch1", chapter_number=1))
        session.commit()
        manifest = {
            "schema_version": 1,
            "novel_id": "n1",
            "generation_id": "g1",
            "chapters": [
                {
                    "chapter_id": "ch1",
                    "raw_storage_key": raw.key,
                    "raw_content_hash": raw.logical_sha256,
                    "translated_storage_key": translated.key,
                    "translated_content_hash": translated.logical_sha256,
                }
            ],
        }
        result = R2GenerationActivationService(storage=storage, db_session=session).activate(
            novel_id="n1",
            generation_id="g1",
            manifest=manifest,
            expected_generation_id=None,
        )
        session.commit()
        assert result.manifest_key == "novels/n1/generations/g1.json.gz"
        assert session.query(Novel).one().active_generation_id == "g1"

        with pytest.raises(GenerationConflictError):
            R2GenerationActivationService(storage=storage, db_session=session).activate(
                novel_id="n1",
                generation_id="g2",
                manifest={**manifest, "generation_id": "g2"},
                expected_generation_id=None,
            )
    finally:
        session.close()
        Base.metadata.drop_all(engine)

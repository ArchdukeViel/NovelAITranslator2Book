"""Measure disposable checkpoint duplication without hosted storage access."""

from __future__ import annotations

import hashlib
import json
import zlib
from datetime import UTC, datetime
from typing import Any

from novelai.core.chapter_state import ChapterState
from novelai.storage.service import StorageService


def _json_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def test_checkpoint_footprint_is_measured_and_reference_envelope_is_body_free(
    tmp_path,
    capsys,
) -> None:
    storage = StorageService(tmp_path / "runtime")
    raw_text = "raw fixture paragraph " * 256
    translated_text = "translated fixture paragraph " * 256
    storage.save_chapter("novel-fixture", "chapter-1", raw_text, source_url="https://fixture.invalid/chapter-1")
    storage.save_translated_chapter(
        "novel-fixture",
        "chapter-1",
        translated_text,
        provider_key="fixture-provider",
        provider_model="fixture-model",
    )
    storage.update_chapter_state("novel-fixture", "chapter-1", ChapterState.TRANSLATED)

    checkpoint_path = storage.create_checkpoint("novel-fixture", "chapter-1", "footprint")
    serialized = checkpoint_path.read_bytes()
    checkpoint = json.loads(serialized)
    reference_envelope = {
        "envelope_version": "reference-v2",
        "novel_id": "novel-fixture",
        "chapter_id": "chapter-1",
        "checkpoint_id": "footprint",
        "state": "translated",
        "source_text_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
        "translation_text_hash": hashlib.sha256(translated_text.encode()).hexdigest(),
        "raw_artifact_key": "novel-fixture/chapter-1/raw/hash",
        "translation_artifact_key": "novel-fixture/chapter-1/translation/hash",
        "active_generation_id": "generation-fixture",
        "stage": "translated",
        "attempt": 1,
    }
    recovery_read_bytes = len(checkpoint_path.read_bytes())
    restored = storage.restore_from_checkpoint("novel-fixture", "chapter-1", "footprint")

    timestamp = datetime.fromisoformat(checkpoint["timestamp"].replace("Z", "+00:00"))
    report = {
        "serialized_bytes": len(serialized),
        "compressed_bytes": len(zlib.compress(serialized)),
        "raw_copy_bytes": _json_bytes(checkpoint["raw_chapter"]),
        "translated_copy_bytes": _json_bytes(checkpoint["translated_chapter"]),
        "state_copy_bytes": _json_bytes(checkpoint["chapter_state"]),
        "reference_bytes": _json_bytes(reference_envelope),
        "write_count": 1,
        "rewrite_count": 0,
        "recovery_reads": 1,
        "recovery_read_bytes": recovery_read_bytes,
        "retention_age_seconds": round((datetime.now(UTC) - timestamp).total_seconds(), 3),
        "envelope_version": "legacy-copy-v1",
        "candidate_envelope_version": reference_envelope["envelope_version"],
        "restore_success": restored,
        "reference_contains_raw_or_translated_body": any(
            value in json.dumps(reference_envelope) for value in (raw_text, translated_text)
        ),
        "canonical_external_writes": 0,
    }
    print("CHECKPOINT_FOOTPRINT " + json.dumps(report, sort_keys=True))

    captured = capsys.readouterr().out
    print(captured, end="")
    assert "CHECKPOINT_FOOTPRINT" in captured
    assert report["restore_success"] is True
    assert report["serialized_bytes"] == len(serialized)
    assert report["compressed_bytes"] < report["serialized_bytes"]
    assert report["raw_copy_bytes"] > 0
    assert report["translated_copy_bytes"] > 0
    assert report["state_copy_bytes"] > 0
    assert report["reference_bytes"] < report["raw_copy_bytes"] + report["translated_copy_bytes"]
    assert report["reference_contains_raw_or_translated_body"] is False
    assert report["canonical_external_writes"] == 0

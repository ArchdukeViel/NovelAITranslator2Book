from __future__ import annotations

from pathlib import Path

SEEDER = Path(__file__).parents[1] / "src" / "novelai" / "scripts" / "seed_reader_capacity_fixture.py"


def test_reader_fixture_seeder_is_non_production_and_explicitly_bound() -> None:
    source = SEEDER.read_text(encoding="utf-8")

    assert 'FIXTURE_SLUG = "test-novel"' in source
    assert "FIXTURE_NOVEL_ID = 123" in source
    assert '(456, 1, "Chapter 1")' in source
    assert '(457, 2, "Chapter 2")' in source
    assert 'TARGET_GUARD_VALUE = "non-production"' in source
    assert 'settings.ENV.strip().lower() not in {"test", "staging"}' in source
    assert 'bucket in {"dokushodo", "dokushodo-backup"}' in source
    assert "save_raw_chapter_artifact" in source
    assert "save_translation_artifact" in source
    assert "JOB_WORKER_ENABLED" not in source

from __future__ import annotations

from novelai.config.settings import settings
from novelai.services.analytics_writer import AnalyticsWriter


def test_writer_sanitizes_metadata_and_drops_when_queue_is_full(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    writer = AnalyticsWriter(maxsize=1, start_worker=False)

    assert writer.enqueue(
        "search.performed",
        metadata={"scope": "catalog", "query": "private", "prompt": "secret"},
    )
    assert not writer.enqueue("search.performed", metadata={"scope": "catalog"})

    job = writer._queue.get_nowait()
    writer._queue.task_done()
    assert job is not None
    assert job.metadata_json == '{"scope": "catalog"}'
    assert "private" not in job.metadata_json
    assert "secret" not in job.metadata_json
    stats = writer.stats()
    assert stats.accepted == 1
    assert stats.dropped == 1
    writer.shutdown()

"""Regression coverage for bounded pipeline timing evidence."""

import asyncio
from typing import Any

import pytest

from novelai.services.runtime_telemetry import (
    REQUIRED_TELEMETRY_OPERATIONS,
    BoundedRuntimeTelemetry,
    RuntimeObservation,
    TelemetryOperation,
    TelemetryStage,
    TelemetryUnavailableReason,
)
from novelai.translation.pipeline.context import PipelineState
from novelai.translation.pipeline.pipeline import TranslationPipeline
from novelai.translation.pipeline.stages.segment import SmartSegmentStage
from novelai.translation.pipeline.stages.translate import _record_pipeline_provider_usage


@pytest.mark.asyncio
async def test_pipeline_stage_event_contains_bounded_timing_fields() -> None:
    context = PipelineState(
        chapter_url="https://example.invalid/chapter/1",
        job_id="job-1",
        activity_id="activity-1",
        novel_id="novel-1",
        chapter_id="chapter-1",
        source_key="test-source",
    )
    context.normalized_text = "Alpha\n\nBeta"

    result = await TranslationPipeline([SmartSegmentStage()]).run(context)

    completed = result.pipeline_events[-1]
    assert completed["stage_name"] == "SmartSegmentStage"
    assert completed["job_id"] == "job-1"
    assert completed["activity_id"] == "activity-1"
    assert completed["novel_id"] == "novel-1"
    assert completed["chapter_id"] == "chapter-1"
    assert completed["operation"] == "pipeline_stage"
    assert completed["duration_ms"] >= 0
    assert completed["input_bytes"] == len(context.normalized_text.encode("utf-8"))
    assert completed["output_bytes"] > 0
    assert "concurrency" not in completed
    assert result.metadata["pipeline_timing_schema_version"] == 1
    assert result.metadata["pipeline_timing_unavailable"] == {
        "novel_metadata_load": "orchestration metadata timing is not attached to pipeline stage events",
        "glossary_load": "orchestration glossary timing is not attached to pipeline stage events",
        "provider_wait": "provider wait timing is available only in process-level provider metrics",
        "postgres_commit": "database transaction timing is not correlated to pipeline stage events",
        "activity_state_update": "activity state timing is exposed by the activity database metrics",
        "r2_transfer": "R2 operation counters are not attached to this pipeline context",
    }
    assert "chapter_url" not in completed


def test_pipeline_provider_usage_accepts_only_numeric_token_fields() -> None:
    context = PipelineState(chapter_url="test")

    _record_pipeline_provider_usage(
        context,
        {"input_tokens": 7, "output_tokens": 5, "total_tokens": 12, "api_key": "secret-value"},
    )
    _record_pipeline_provider_usage(context, {"input_tokens": -1, "output_tokens": 2.5, "response": "private"})

    timing = context.metadata["pipeline_timing"]
    assert isinstance(timing, dict)
    assert timing["provider_usage"] == {"input_tokens": 7, "output_tokens": 5}
    assert "api_key" not in str(timing)
    assert "response" not in str(timing)


def test_pipeline_timing_fields_drop_invalid_numeric_values() -> None:
    context = PipelineState(chapter_url="test")
    event: dict[str, Any] = context.trace_event(
        stage_name="TranslateStage",
        duration_ms=-1,
        input_bytes=-2,
        output_bytes=True,  # type: ignore[arg-type]
        input_tokens=3,
        retry_count=-4,
    )

    assert event["duration_ms"] == 0.0
    assert event["input_bytes"] == 0
    assert "output_bytes" not in event
    assert event["input_tokens"] == 3
    assert event["retry_count"] == 0


def test_runtime_telemetry_is_bounded_and_contains_only_fixed_fields() -> None:
    telemetry = BoundedRuntimeTelemetry(max_observations=3, sample_interval_seconds=0.01)

    for _ in range(10):
        telemetry.record(
            RuntimeObservation(
                stage=TelemetryStage.PROVIDER_WAIT,
                operation=TelemetryOperation.PROVIDER_WAIT,
                queue_wait_ms=4.5,
                input_tokens=7,
                unavailable_reasons=(TelemetryUnavailableReason.NETWORK_BYTES_UNAVAILABLE,),
            )
        )

    observations = telemetry.snapshot()
    assert len(observations) == 3
    record = observations[-1].to_dict()
    assert record["schema_version"] == 1
    assert record["stage"] == "provider_wait"
    assert record["operation"] == "provider_wait"
    assert "prompt" not in str(record).lower()
    assert "private-response-value" not in str(record)
    assert "secret-value" not in str(record)


def test_runtime_telemetry_rejects_unbounded_labels_and_unnamed_unavailability() -> None:
    with pytest.raises(ValueError, match="unsupported telemetry stage"):
        RuntimeObservation(stage="arbitrary-user-label", operation=TelemetryOperation.STAGE)

    with pytest.raises(ValueError, match="named reason"):
        RuntimeObservation(
            stage=TelemetryStage.PROCESS,
            operation=TelemetryOperation.PROCESS_RESOURCES,
            outcome="unavailable",
        )


@pytest.mark.asyncio
async def test_runtime_telemetry_event_loop_sampler_is_bounded_and_stoppable() -> None:
    telemetry = BoundedRuntimeTelemetry(max_observations=4, sample_interval_seconds=0.01)

    await telemetry.start()
    assert telemetry.sampler_running()
    await asyncio.sleep(0.04)
    await telemetry.stop()

    assert not telemetry.sampler_running()
    samples = [
        observation
        for observation in telemetry.snapshot()
        if observation.operation == TelemetryOperation.EVENT_LOOP_LAG.value
    ]
    assert samples
    assert all((sample.event_loop_lag_ms or 0.0) >= 0.0 for sample in samples)


def test_runtime_telemetry_process_sample_names_unavailable_resources() -> None:
    telemetry = BoundedRuntimeTelemetry(max_observations=4, sample_interval_seconds=0.01)

    sample = telemetry.sample_process_resources()

    assert sample.stage == TelemetryStage.PROCESS.value
    assert sample.operation == TelemetryOperation.PROCESS_RESOURCES.value
    assert sample.cpu_ms is not None and sample.cpu_ms >= 0.0
    assert TelemetryUnavailableReason.NETWORK_BYTES_UNAVAILABLE.value in sample.unavailable_reasons
    assert set(sample.unavailable_reasons).issubset({reason.value for reason in TelemetryUnavailableReason})


def test_runtime_telemetry_inventory_uses_fixed_stage_and_operation_pairs() -> None:
    assert len(REQUIRED_TELEMETRY_OPERATIONS) >= 15
    assert len({stage for stage, _operation in REQUIRED_TELEMETRY_OPERATIONS}) == len(REQUIRED_TELEMETRY_OPERATIONS)
    assert (TelemetryStage.POSTGRES_COMMIT, TelemetryOperation.DB_COMMIT) in REQUIRED_TELEMETRY_OPERATIONS

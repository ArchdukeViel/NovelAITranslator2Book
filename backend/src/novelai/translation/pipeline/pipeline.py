from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from novelai.config.settings import settings
from novelai.services.timing_contract import PIPELINE_TIMING_STAGES, TimingSpan
from novelai.translation.pipeline.context import PipelineState
from novelai.translation.pipeline.stages.base import PipelineStage


class PipelineStageError(RuntimeError):
    """Exception raised when a pipeline stage fails.

    Carries the pipeline context, events, and failed stage name so callers
    can inspect what happened without re-running the pipeline.
    """

    def __init__(
        self,
        original: BaseException,
        *,
        pipeline_context: PipelineState,
        pipeline_events: list[dict[str, Any]],
        failed_stage_name: str,
    ) -> None:
        super().__init__(str(original))
        self.original = original
        self.pipeline_context = pipeline_context
        self.pipeline_events = pipeline_events
        self.failed_stage_name = failed_stage_name


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _stage_status_after(stage_name: str) -> str:
    mapping = {
        "FetchStage": "fetched",
        "ParseStage": "parsed",
        "SmartSegmentStage": "segmented",
        "TranslateStage": "translated",
        "TranslationQAStage": "translated",
        "PostProcessStage": "translated",
    }
    return mapping.get(stage_name, "completed")


def _event_code_from_exception(exc: BaseException) -> str:
    provider_code = getattr(exc, "provider_error_code", None)
    if provider_code is not None:
        return str(getattr(provider_code, "value", provider_code))
    error_code = getattr(exc, "error_code", None)
    if error_code is not None:
        return str(getattr(error_code, "value", error_code))
    return exc.__class__.__name__


def _append_event(context: PipelineState, event: dict[str, Any]) -> None:
    event.setdefault("timestamp", _utc_now_iso())
    context.pipeline_events.append(event)
    context.metadata["pipeline_events"] = context.pipeline_events


_PIPELINE_TIMING_UNAVAILABLE = {
    "novel_metadata_load": "orchestration metadata timing is not attached to pipeline stage events",
    "glossary_load": "orchestration glossary timing is not attached to pipeline stage events",
    "provider_wait": "provider wait timing is available only in process-level provider metrics",
    "postgres_commit": "database transaction timing is not correlated to pipeline stage events",
    "activity_state_update": "activity state timing is exposed by the activity database metrics",
    "r2_transfer": "R2 operation counters are not attached to this pipeline context",
}

_PIPELINE_STAGE_BY_CLASS = {
    "FetchStage": "source_fetch",
    "ParseStage": "parsing",
    "SmartSegmentStage": "parsing",
    "TranslateStage": "translation",
    "TranslationQAStage": "qa",
    "CacheFlushStage": "qa",
    "PostProcessStage": "translation",
}


def _text_bytes(value: str | None) -> int:
    return len(value.encode("utf-8")) if isinstance(value, str) else 0


def _safe_counter(value: Any) -> int:
    return max(0, int(value)) if isinstance(value, int) and not isinstance(value, bool) else 0


def _timing_snapshot(context: PipelineState) -> dict[str, int]:
    timing = context.metadata.get("pipeline_timing")
    timing_map = timing if isinstance(timing, dict) else {}
    usage = timing_map.get("provider_usage")
    usage_map = usage if isinstance(usage, dict) else {}
    return {
        "raw_bytes": _text_bytes(context.raw_text),
        "normalized_bytes": _text_bytes(context.normalized_text),
        "chunk_input_bytes": sum(_text_bytes(chunk.source_text) for chunk in context.translation_chunks),
        "translated_bytes": sum(_text_bytes(text) for text in context.translations),
        "final_bytes": _text_bytes(context.final_text),
        "input_tokens": _safe_counter(usage_map.get("input_tokens")),
        "output_tokens": _safe_counter(usage_map.get("output_tokens")),
        "retry_count": _safe_counter(timing_map.get("provider_retry_count")),
        "db_rows": _safe_counter(timing_map.get("db_rows")),
        "r2_operation_count": _safe_counter(timing_map.get("r2_operation_count")),
        "compressed_bytes": _safe_counter(timing_map.get("compressed_bytes")),
        "concurrency": _safe_counter(timing_map.get("concurrency")),
    }


def _stage_io_bytes(stage_name: str, before: dict[str, int], after: dict[str, int]) -> tuple[int | None, int | None]:
    mapping = {
        "FetchStage": (None, after["raw_bytes"]),
        "ParseStage": (before["raw_bytes"], after["normalized_bytes"]),
        "SmartSegmentStage": (before["normalized_bytes"], after["chunk_input_bytes"]),
        "TranslateStage": (before["chunk_input_bytes"], after["translated_bytes"]),
        "TranslationQAStage": (before["translated_bytes"], after["translated_bytes"]),
        "CacheFlushStage": (before["translated_bytes"], after["translated_bytes"]),
        "PostProcessStage": (before["translated_bytes"], after["final_bytes"]),
    }
    return mapping.get(stage_name, (None, None))


def _append_pipeline_timing_span(
    context: PipelineState,
    *,
    stage_name: str,
    pipeline_started_ns: int,
    stage_started_ns: int,
    stage_finished_ns: int,
) -> None:
    fixed_stage = _PIPELINE_STAGE_BY_CLASS.get(stage_name)
    if fixed_stage not in PIPELINE_TIMING_STAGES:
        return
    span = TimingSpan(
        name=fixed_stage,
        source="pipeline",
        start_offset_ms=round((stage_started_ns - pipeline_started_ns) / 1_000_000, 3),
        duration_ms=round((stage_finished_ns - stage_started_ns) / 1_000_000, 3),
        sample_count=1,
        critical_path=True,
    )
    spans = context.metadata.setdefault("pipeline_timing_spans", [])
    if isinstance(spans, list):
        spans.append(span.to_dict())


def _timing_fields(
    context: PipelineState,
    *,
    stage_name: str,
    before: dict[str, int],
    duration_ms: float,
) -> dict[str, Any]:
    after = _timing_snapshot(context)
    input_bytes, output_bytes = _stage_io_bytes(stage_name, before, after)
    fields: dict[str, Any] = {
        "operation": "pipeline_stage",
        "duration_ms": duration_ms,
        "input_bytes": input_bytes,
        "output_bytes": output_bytes,
        "compressed_bytes": after["compressed_bytes"] - before["compressed_bytes"] or None,
        "input_tokens": after["input_tokens"] - before["input_tokens"] or None,
        "output_tokens": after["output_tokens"] - before["output_tokens"] or None,
        "retry_count": after["retry_count"] - before["retry_count"] or None,
        "concurrency": after["concurrency"] or None,
        "db_rows": after["db_rows"] - before["db_rows"] or None,
        "r2_operation_count": after["r2_operation_count"] - before["r2_operation_count"] or None,
    }
    if stage_name not in {"FetchStage", "ParseStage", "SmartSegmentStage", "TranslateStage", "TranslationQAStage"}:
        fields["unavailable_reason"] = "stage-specific external timing is not correlated"
    return fields


class TranslationPipeline:
    """Orchestrates a series of transformation stages."""

    def __init__(self, stages: Iterable[PipelineStage]) -> None:
        self.stages = list(stages)

    async def run(self, initial_context: dict[str, object] | PipelineState) -> PipelineState:
        """Run the pipeline through all stages.

        The context is converted to a typed PipelineState instance and passed through
        each stage. This helps make stage inputs/outputs explicit and reduces bugs.
        """
        context = (
            initial_context if isinstance(initial_context, PipelineState) else PipelineState.from_dict(initial_context)
        )
        context.metadata.setdefault("pipeline_timing_schema_version", 1)
        context.metadata.setdefault("pipeline_timing_unavailable", dict(_PIPELINE_TIMING_UNAVAILABLE))
        pipeline_started_ns = time.perf_counter_ns()

        for stage in self.stages:
            stage_name = stage.__class__.__name__
            status_before = context.current_stage
            context.current_stage = stage_name
            timing_before = _timing_snapshot(context)
            stage_started_ns = time.perf_counter_ns()
            _append_event(
                context,
                context.trace_event(
                    stage_name=stage_name,
                    status_before=status_before,
                    status_after="running",
                    message=f"{stage_name} started.",
                ),
            )
            try:
                context = await stage.run(context)
                if stage_name == "TranslationQAStage" and settings.LLM_QA_POLICY == "blocking_retry":
                    translate_stage = next((s for s in self.stages if s.__class__.__name__ == "TranslateStage"), None)
                    retry_loop_count = 0
                    while retry_loop_count < settings.LLM_QA_MAX_RETRY_ATTEMPTS and any(
                        s.get("status") == "needs_retry" for s in context.chunk_states.values()
                    ):
                        retry_loop_count += 1
                        if translate_stage is not None:
                            context = await translate_stage.run(context)
                        context = await stage.run(context)
            except Exception as exc:
                stage_finished_ns = time.perf_counter_ns()
                _append_pipeline_timing_span(
                    context,
                    stage_name=stage_name,
                    pipeline_started_ns=pipeline_started_ns,
                    stage_started_ns=stage_started_ns,
                    stage_finished_ns=stage_finished_ns,
                )
                error = {
                    "stage_name": stage_name,
                    "error_code": _event_code_from_exception(exc),
                    "message": str(exc),
                    "timestamp": _utc_now_iso(),
                }
                context.errors.append(error)
                context.metadata["errors"] = context.errors
                _append_event(
                    context,
                    context.trace_event(
                        stage_name=stage_name,
                        status_before="running",
                        status_after="failed",
                        error_code=str(error["error_code"]),
                        message=str(exc),
                        **_timing_fields(
                            context,
                            stage_name=stage_name,
                            before=timing_before,
                            duration_ms=(stage_finished_ns - stage_started_ns) / 1_000_000,
                        ),
                    ),
                )
                raise PipelineStageError(
                    exc,
                    pipeline_context=context,
                    pipeline_events=list(context.pipeline_events),
                    failed_stage_name=stage_name,
                ) from exc
            stage_finished_ns = time.perf_counter_ns()
            _append_pipeline_timing_span(
                context,
                stage_name=stage_name,
                pipeline_started_ns=pipeline_started_ns,
                stage_started_ns=stage_started_ns,
                stage_finished_ns=stage_finished_ns,
            )
            context.current_stage = stage_name
            _append_event(
                context,
                context.trace_event(
                    stage_name=stage_name,
                    status_before="running",
                    status_after=_stage_status_after(stage_name),
                    message=f"{stage_name} completed.",
                    **_timing_fields(
                        context,
                        stage_name=stage_name,
                        before=timing_before,
                        duration_ms=(stage_finished_ns - stage_started_ns) / 1_000_000,
                    ),
                ),
            )

        return context

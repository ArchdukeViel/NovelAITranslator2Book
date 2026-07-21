from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

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
        "SegmentStage": "segmented",
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
            initial_context
            if isinstance(initial_context, PipelineState)
            else PipelineState.from_dict(initial_context)
        )

        for stage in self.stages:
            stage_name = stage.__class__.__name__
            status_before = context.current_stage
            context.current_stage = stage_name
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
            except Exception as exc:
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
                    ),
                )
                raise PipelineStageError(
                    exc,
                    pipeline_context=context,
                    pipeline_events=list(context.pipeline_events),
                    failed_stage_name=stage_name,
                ) from exc
            context.current_stage = stage_name
            _append_event(
                context,
                context.trace_event(
                    stage_name=stage_name,
                    status_before="running",
                    status_after=_stage_status_after(stage_name),
                    message=f"{stage_name} completed.",
                ),
            )

        return context

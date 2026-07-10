"""Pipeline logging context — per-chapter structured logging support.

Note: This module defines ``StageLogContext`` for logging. The canonical
``PipelineContext`` dataclass lives in ``novelai.shared.pipeline``.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any


class StageLogContext:
    """Per-chapter logging context for pipeline stage execution.

    Usage:
        ctx = StageLogContext(novel_id="n1", chapter_id="c1", request_id="uuid")
        with ctx.stage("FetchStage"):
            ...
    """

    def __init__(
        self,
        novel_id: str,
        chapter_id: str,
        request_id: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.novel_id = novel_id
        self.chapter_id = chapter_id
        self.request_id = request_id or datetime.now(UTC).isoformat()
        self.logger = logger or logging.getLogger(__name__)

    def stage_enter(self, stage_name: str) -> dict[str, Any]:
        self.logger.info(
            "Stage started",
            extra={
                "novel_id": self.novel_id,
                "chapter_id": self.chapter_id,
                "request_id": self.request_id,
                "stage": stage_name,
                "event": "stage_enter",
            },
        )
        return {"stage": stage_name, "start": time.monotonic()}

    def stage_exit(self, marker: dict[str, Any]) -> None:
        duration_ms = (time.monotonic() - marker["start"]) * 1000
        self.logger.info(
            "Stage completed",
            extra={
                "novel_id": self.novel_id,
                "chapter_id": self.chapter_id,
                "request_id": self.request_id,
                "stage": marker["stage"],
                "event": "stage_exit",
                "duration_ms": round(duration_ms, 1),
            },
        )

    def stage_error(self, marker: dict[str, Any], error_code: str, stack_trace: str | None = None) -> None:
        duration_ms = (time.monotonic() - marker["start"]) * 1000
        truncated = (stack_trace or "")[:1000]
        self.logger.error(
            "Stage failed",
            extra={
                "novel_id": self.novel_id,
                "chapter_id": self.chapter_id,
                "request_id": self.request_id,
                "stage": marker["stage"],
                "event": "stage_error",
                "duration_ms": round(duration_ms, 1),
                "error_code": error_code,
                "stack_trace": truncated,
            },
        )

    @contextmanager
    def stage(self, stage_name: str):
        marker = self.stage_enter(stage_name)
        try:
            yield
        except Exception:
            import traceback
            self.stage_error(marker, error_code="pipeline.stage_error", stack_trace=traceback.format_exc())
            raise
        else:
            self.stage_exit(marker)


def get_pipeline_logger(
    novel_id: str,
    chapter_id: str,
    request_id: str | None = None,
) -> tuple[logging.Logger, StageLogContext]:
    """Create a logger and StageLogContext for a chapter translation.

    Returns (logger, context).
    """
    logger = logging.getLogger("novelai.pipeline")
    ctx = StageLogContext(
        novel_id=novel_id,
        chapter_id=chapter_id,
        request_id=request_id,
        logger=logger,
    )
    return logger, ctx

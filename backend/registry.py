"""
Runtime registry for active pipelines.

Maintains an in-memory dictionary of pipeline_id → PipelineRuntime.
Each runtime holds the asyncio.Task, state reference, and checkpoint synchronization.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from pipeline.models import CheckpointDecision, CheckpointResult, PipelineState

_log = logging.getLogger("backend.registry")

STAGE_ORDER = [
    "requirements", "solution", "code_gen", "test_gen", "review", "delivery",
]


class PipelineRuntime:
    """Per-pipeline runtime state for API mode."""

    def __init__(self, pipeline_id: str, input_text: str) -> None:
        self.pipeline_id = pipeline_id
        self.input_text = input_text
        self.created_at = datetime.now().isoformat()

        # asyncio.Task running engine.run()
        self.task: asyncio.Task | None = None

        # Reference to engine's PipelineState (updated in-place by engine)
        self.pipeline_state: PipelineState | None = None

        # Checkpoint synchronization
        self.checkpoint_event: asyncio.Event = asyncio.Event()
        self.checkpoint_result: dict = {}  # populated by API handler

        # Status tracking
        self.status: str = "pending"  # pending | running | paused | completed | terminated
        self.current_stage: str | None = None

        # Cumulative metrics (populated by engine via callback)
        self.total_time_ms: float = 0.0
        self.total_tokens: int = 0

    def stage_statuses(self) -> list[dict]:
        """Build stage status list from pipeline_state."""
        ps = self.pipeline_state
        statuses = []
        for name in STAGE_ORDER:
            content = getattr(ps, name, None) if ps else None
            if ps:
                if name == "requirements" and ps.requirements:
                    s = "completed"
                elif name == "solution" and ps.solution:
                    s = "completed"
                elif name == "code_gen" and ps.code_diff:
                    s = "completed"
                elif name == "test_gen" and ps.test_code:
                    s = "completed"
                elif name == "review" and ps.review_report:
                    s = "completed"
                elif name == "delivery" and ps.final_output:
                    s = "completed"
                elif self.current_stage == name:
                    s = self.status if self.status == "paused" else "running"
                elif self.status == "paused":
                    s = "pending"
                else:
                    s = "pending"
            else:
                s = "pending"
            statuses.append({
                "name": name,
                "status": s,
                "output_preview": (content[:200] if content else None),
            })
        return statuses

    def to_detail(self) -> dict:
        """Return PipelineDetail-compatible dict."""
        return {
            "id": self.pipeline_id,
            "input": self.input_text,
            "status": self.status,
            "current_stage": self.current_stage,
            "created_at": self.created_at,
            "paused_at": (self.pipeline_state.paused_at if self.pipeline_state else None),
            "pause_reason": (self.pipeline_state.pause_reason if self.pipeline_state else None),
            "stages": self.stage_statuses(),
            "total_time_ms": self.total_time_ms,
            "total_tokens": self.total_tokens,
        }

    def to_info(self) -> dict:
        """Return PipelineInfo-compatible dict."""
        return {
            "id": self.pipeline_id,
            "input": self.input_text,
            "status": self.status,
            "current_stage": self.current_stage,
            "created_at": self.created_at,
            "paused_at": (self.pipeline_state.paused_at if self.pipeline_state else None),
            "pause_reason": (self.pipeline_state.pause_reason if self.pipeline_state else None),
        }

    # --- Checkpoint helpers ---

    def prepare_checkpoint(self) -> None:
        """Reset the checkpoint event before entering a checkpoint wait."""
        self.checkpoint_event.clear()
        self.checkpoint_result = {}
        self.status = "waiting_approval"

    def approve(self) -> CheckpointResult:
        """Called by API handler to approve the checkpoint."""
        self.status = "running"
        ret = CheckpointResult(decision=CheckpointDecision.APPROVE)
        self.checkpoint_result["result"] = ret
        self.checkpoint_event.set()
        return ret

    def reject(self, reason: str) -> CheckpointResult:
        """Called by API handler to reject the checkpoint."""
        self.status = "running"
        ret = CheckpointResult(decision=CheckpointDecision.REJECT, reason=reason)
        self.checkpoint_result["result"] = ret
        self.checkpoint_event.set()
        return ret


# Global registry
_registry: dict[str, PipelineRuntime] = {}


def register(runtime: PipelineRuntime) -> None:
    _registry[runtime.pipeline_id] = runtime


def get(pipeline_id: str) -> PipelineRuntime | None:
    return _registry.get(pipeline_id)


def remove(pipeline_id: str) -> PipelineRuntime | None:
    return _registry.pop(pipeline_id, None)


def list_all() -> list[dict]:
    return [rt.to_info() for rt in _registry.values()]


def find_stage_runtime(pipeline_id: str, stage_name: str) -> PipelineRuntime | None:
    """Find runtime that has the given stage as current and is waiting_approval."""
    rt = _registry.get(pipeline_id)
    if rt and rt.status == "waiting_approval" and rt.current_stage == stage_name:
        return rt
    return None

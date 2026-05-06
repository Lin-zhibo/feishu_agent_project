"""
Pydantic request/response models for the DevFlow API.
"""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class PipelineCreate(BaseModel):
    input: str
    skip_checkpoints: bool = False
    workspace: str | None = None


class StageStatus(BaseModel):
    name: str
    status: str  # pending | running | completed
    output_preview: str | None = None


class PipelineInfo(BaseModel):
    id: str
    input: str
    status: str  # running | paused | completed | terminated
    current_stage: str | None = None
    created_at: str | None = None
    paused_at: str | None = None
    pause_reason: str | None = None


class PipelineDetail(PipelineInfo):
    stages: list[StageStatus] = []
    total_time_ms: float | None = None
    total_tokens: int | None = None


class PipelineList(BaseModel):
    pipelines: list[PipelineInfo]


# ---------------------------------------------------------------------------
# Stage / Checkpoint
# ---------------------------------------------------------------------------

class StageInfo(BaseModel):
    stage_name: str
    status: str
    content: str | None = None


class CheckpointAction(BaseModel):
    reason: str | None = None


class CheckpointResponse(BaseModel):
    stage_id: str
    decision: str  # approved | rejected


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class ConfigResponse(BaseModel):
    workspace: str
    log_dir: str
    skip_checkpoints: bool
    max_total_time_ms: int
    max_total_tokens: int
    max_retry: int
    temperature: float
    max_tool_iterations: int
    preserve_session: bool
    verbose: bool


class ConfigUpdate(BaseModel):
    workspace: str | None = None
    log_dir: str | None = None
    skip_checkpoints: bool | None = None
    max_total_time_ms: int | None = None
    max_total_tokens: int | None = None
    max_retry: int | None = None
    temperature: float | None = None
    max_tool_iterations: int | None = None
    preserve_session: bool | None = None
    verbose: bool | None = None


# ---------------------------------------------------------------------------
# SSE Event
# ---------------------------------------------------------------------------

class PipelineEvent(BaseModel):
    pipeline_id: str
    event: str  # stage_start | stage_end | checkpoint | paused | completed | terminated
    stage_name: str | None = None
    status: str | None = None
    message: str | None = None
    timestamp: str

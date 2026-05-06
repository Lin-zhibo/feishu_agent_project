"""
Stage query and checkpoint action endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.models import CheckpointAction, CheckpointResponse, StageInfo
from backend.registry import get as reg_get, find_stage_runtime

_log = logging.getLogger("backend.api.stages")

router = APIRouter(prefix="/api/v1", tags=["stages"])


@router.get("/pipelines/{pipeline_id}/stages")
async def list_stages(pipeline_id: str):
    rt = reg_get(pipeline_id)
    if not rt:
        raise HTTPException(404, f"Pipeline not found: {pipeline_id}")
    return {"pipeline_id": pipeline_id, "stages": rt.stage_statuses()}


@router.get("/stages/{stage_id}/output")
async def get_stage_output(stage_id: str):
    # stage_id format: "{pipeline_id}:{stage_name}"
    if ":" not in stage_id:
        raise HTTPException(400, "stage_id must be '{pipeline_id}:{stage_name}'")
    pid, name = stage_id.split(":", 1)
    rt = reg_get(pid)
    if not rt:
        raise HTTPException(404, f"Pipeline not found: {pid}")

    if not rt.pipeline_state:
        raise HTTPException(404, "No state available")

    field_map = {
        "requirements": rt.pipeline_state.requirements,
        "solution": rt.pipeline_state.solution,
        "code_gen": rt.pipeline_state.code_diff,
        "test_gen": rt.pipeline_state.test_code,
        "review": rt.pipeline_state.review_report,
        "delivery": rt.pipeline_state.final_output,
    }
    content = field_map.get(name)
    return StageInfo(stage_name=name, status="completed" if content else "pending", content=content)


@router.post("/stages/{stage_id}/approve", response_model=CheckpointResponse)
async def approve_stage(stage_id: str):
    if ":" not in stage_id:
        raise HTTPException(400, "stage_id must be '{pipeline_id}:{stage_name}'")
    pid, name = stage_id.split(":", 1)
    rt = find_stage_runtime(pid, name)
    if not rt:
        raise HTTPException(404, f"Stage not waiting for approval: {stage_id}")
    rt.approve()
    return CheckpointResponse(stage_id=stage_id, decision="approved")


@router.post("/stages/{stage_id}/reject", response_model=CheckpointResponse)
async def reject_stage(stage_id: str, body: CheckpointAction):
    if ":" not in stage_id:
        raise HTTPException(400, "stage_id must be '{pipeline_id}:{stage_name}'")
    pid, name = stage_id.split(":", 1)
    rt = find_stage_runtime(pid, name)
    if not rt:
        raise HTTPException(404, f"Stage not waiting for approval: {stage_id}")
    rt.reject(body.reason or "No reason provided")
    return CheckpointResponse(stage_id=stage_id, decision="rejected")

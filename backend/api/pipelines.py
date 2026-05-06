"""
Pipeline CRUD and lifecycle endpoints.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from backend.engine_bridge import load_config
from backend.models import PipelineCreate, PipelineDetail, PipelineInfo, PipelineList
from backend.registry import PipelineRuntime, get as reg_get, list_all, register

_log = logging.getLogger("backend.api.pipelines")

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])


@router.post("", status_code=201, response_model=PipelineInfo)
async def create_pipeline(body: PipelineCreate):
    config = load_config()
    if body.workspace:
        config.workspace = body.workspace
    if body.skip_checkpoints:
        config.skip_checkpoints = True

    from pipeline.engine import run as engine_run

    pipeline_id = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    runtime = PipelineRuntime(pipeline_id, body.input)

    async def _wrapper():
        runtime.status = "running"
        try:
            await engine_run(body.input, config, runtime=runtime)
        except Exception as e:
            _log.exception("Pipeline %s failed: %s", pipeline_id, e)
            runtime.status = "terminated"
            return

    runtime.task = asyncio.create_task(_wrapper())
    register(runtime)

    return runtime.to_info()


@router.get("", response_model=PipelineList)
async def list_pipelines():
    return PipelineList(pipelines=list_all())


@router.get("/{pipeline_id}", response_model=PipelineDetail)
async def get_pipeline(pipeline_id: str):
    rt = reg_get(pipeline_id)
    if not rt:
        raise HTTPException(404, f"Pipeline not found: {pipeline_id}")
    return PipelineDetail(**rt.to_detail())


@router.delete("/{pipeline_id}", response_model=PipelineInfo)
async def terminate_pipeline(pipeline_id: str):
    rt = reg_get(pipeline_id)
    if not rt:
        raise HTTPException(404, f"Pipeline not found: {pipeline_id}")
    if rt.task and not rt.task.done():
        rt.task.cancel()
    rt.status = "terminated"
    return rt.to_info()


@router.post("/{pipeline_id}/pause", response_model=PipelineInfo)
async def pause_pipeline(pipeline_id: str):
    rt = reg_get(pipeline_id)
    if not rt:
        raise HTTPException(404, f"Pipeline not found: {pipeline_id}")
    # Pause by setting status — engine's _try_pause handles disk save
    # For manual pause, we set the state directly
    if rt.pipeline_state:
        rt.pipeline_state.paused_at = __import__("datetime").datetime.now().isoformat()
        rt.pipeline_state.pause_reason = "Manually paused via API"
    rt.status = "paused"
    # Save state to disk
    from pipeline.engine import _save_paused_state
    config = load_config()
    idx = __import__("pipeline.engine", fromlist=["STAGE_ORDER"]).STAGE_ORDER.index(rt.current_stage) if rt.current_stage else 0
    _save_paused_state(rt.pipeline_state, config.log_dir, idx, "Manually paused via API")
    return rt.to_info()


@router.post("/{pipeline_id}/resume", response_model=PipelineInfo)
async def resume_pipeline(pipeline_id: str):
    from pipeline.engine import resume as engine_resume
    rt = reg_get(pipeline_id)
    if not rt:
        raise HTTPException(404, f"Pipeline not found: {pipeline_id}")
    if rt.status != "paused":
        raise HTTPException(400, f"Pipeline {pipeline_id} is not paused (status={rt.status})")

    config = load_config()
    rt.status = "running"

    async def _wrapper():
        try:
            state = await engine_resume(pipeline_id, config)
            if rt.pipeline_state:
                rt.pipeline_state = state
        except Exception as e:
            _log.exception("Pipeline %s resume failed: %s", pipeline_id, e)
            rt.status = "terminated"
            return

    rt.task = asyncio.create_task(_wrapper())
    return rt.to_info()

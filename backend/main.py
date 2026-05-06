"""
FastAPI application entry point for the DevFlow Engine API.

Start with:
    cd backend && uvicorn main:app --reload --port 8080

Swagger UI: http://localhost:8080/docs
ReDoc:      http://localhost:8080/redoc
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from backend.api.config_routes import router as config_router
from backend.api.pipelines import router as pipelines_router
from backend.api.stages import router as stages_router
from backend.registry import get as reg_get

_log = logging.getLogger("backend.main")

app = FastAPI(
    title="DevFlow Engine API",
    version="0.1.0",
    description="AI 驱动的研发全流程交付引擎",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipelines_router)
app.include_router(stages_router)
app.include_router(config_router)


@app.get("/api/v1/pipelines/{pipeline_id}/stream")
async def stream_pipeline(pipeline_id: str, request: Request):
    rt = reg_get(pipeline_id)
    if not rt:
        return JSONResponse({"error": "Pipeline not found"}, status_code=404)

    async def event_generator():
        import datetime
        while True:
            if await request.is_disconnected():
                break
            try:
                event = {
                    "pipeline_id": pipeline_id,
                    "event": "status_update",
                    "stage_name": rt.current_stage,
                    "status": rt.status,
                    "message": None,
                    "timestamp": datetime.datetime.now().isoformat(),
                }
                yield {"data": json.dumps(event, ensure_ascii=False)}
                if rt.status in ("completed", "terminated", "paused"):
                    break
            except Exception:
                break
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@app.get("/docs/openapi.json")
async def openapi_json():
    return app.openapi()


@app.get("/")
async def root():
    return {"service": "DevFlow Engine API", "version": "0.1.0", "docs": "/docs"}

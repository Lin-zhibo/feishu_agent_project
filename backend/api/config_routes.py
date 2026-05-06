"""
Configuration read/update endpoints.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.engine_bridge import load_config
from backend.models import ConfigResponse, ConfigUpdate

_log = logging.getLogger("backend.api.config")

router = APIRouter(prefix="/api/v1/config", tags=["config"])

CONFIG_PATH = Path("config/settings.json")


@router.get("", response_model=ConfigResponse)
async def get_config():
    config = load_config()
    return ConfigResponse(
        workspace=config.workspace,
        log_dir=config.log_dir,
        skip_checkpoints=config.skip_checkpoints,
        max_total_time_ms=config.max_total_time_ms,
        max_total_tokens=config.max_total_tokens,
        max_retry=config.max_retry,
        temperature=config.temperature,
        max_tool_iterations=config.max_tool_iterations,
        preserve_session=config.preserve_session,
        verbose=config.verbose,
    )


@router.put("", response_model=ConfigResponse)
async def update_config(body: ConfigUpdate):
    if not CONFIG_PATH.exists():
        raise HTTPException(404, "config/settings.json not found")

    current = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    for field in body.model_fields_set:
        if hasattr(body, field):
            val = getattr(body, field)
            if val is not None:
                current[field] = val

    CONFIG_PATH.write_text(json.dumps(current, indent=4, ensure_ascii=False), encoding="utf-8")

    config = load_config()
    return ConfigResponse(
        workspace=config.workspace,
        log_dir=config.log_dir,
        skip_checkpoints=config.skip_checkpoints,
        max_total_time_ms=config.max_total_time_ms,
        max_total_tokens=config.max_total_tokens,
        max_retry=config.max_retry,
        temperature=config.temperature,
        max_tool_iterations=config.max_tool_iterations,
        preserve_session=config.preserve_session,
        verbose=config.verbose,
    )

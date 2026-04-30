"""
Top-level entry point for the DevFlow Engine pipeline.

Called by cli.py; can also be imported by other Python code.
"""

from __future__ import annotations

from pipeline.engine import (
    list_paused,
    run as engine_run,
    resume as engine_resume,
    terminate_all_paused,
    _delete_paused_state,
)
from pipeline.models import PipelineConfig, PipelineState


async def run_pipeline(input_text: str, config: PipelineConfig) -> PipelineState:
    """
    Run the DevFlow Engine pipeline.

    Args:
        input_text: The user's raw requirement string.
        config: Global pipeline configuration.

    Returns:
        PipelineState with all stage outputs filled in.
    """
    return await engine_run(input_text, config)


async def resume_pipeline(pipeline_id: str, config: PipelineConfig) -> PipelineState:
    """
    Resume a previously paused pipeline.

    Args:
        pipeline_id: The pipeline ID to resume.
        config: Global pipeline configuration.

    Returns:
        PipelineState after completion.
    """
    return await engine_resume(pipeline_id, config)


def list_paused_pipelines(output_dir: str) -> list[dict]:
    """List all paused pipelines in the output directory."""
    return list_paused(output_dir)


def terminate_pipeline(output_dir: str, pipeline_id: str) -> bool:
    """Delete a paused pipeline file. Returns True if deleted."""
    return _delete_paused_state(output_dir, pipeline_id)


def terminate_all(output_dir: str) -> int:
    """Delete all paused pipeline files. Returns count."""
    return terminate_all_paused(output_dir)

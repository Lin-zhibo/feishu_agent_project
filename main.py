"""
Top-level entry point for the DevFlow Engine pipeline.

Called by cli.py; can also be imported by other Python code.
"""

from __future__ import annotations

from pipeline.engine import run as engine_run
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

"""
Pipeline engine for the DevFlow Engine.

Sequentially executes the 6 stages, passing state between them.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from pipeline.models import PipelineConfig, PipelineState, StageInput, StageOutput

_log = logging.getLogger("pipeline.engine")

STAGE_ORDER = [
    "requirements",
    "solution",
    "code_gen",
    "test_gen",
    "review",
    "delivery",
]


async def run(input_text: str, config: PipelineConfig) -> PipelineState:
    """
    Run the full pipeline.

    Args:
        input_text: The user's raw requirement string.
        config: Global pipeline configuration.

    Returns:
        PipelineState with all stage outputs filled in.
    """
    _log.info("Pipeline started: input='%s'", input_text)

    state = PipelineState(original_input=input_text)
    previous_output: dict | None = None

    for stage_name in STAGE_ORDER:
        if not config.stage_enabled.get(stage_name, True):
            _log.info("Stage '%s' skipped (disabled)", stage_name)
            continue

        agent = _get_agent(stage_name)
        if agent is None:
            _log.warning("No agent found for stage '%s'", stage_name)
            continue

        current_input = _get_current_input(stage_name, input_text, state)
        _log.info("Stage '%s' starting, input length=%d", stage_name, len(current_input))

        inp = StageInput(
            stage_name=stage_name,
            previous_output=previous_output,
            current_input=current_input,
            config=config,
        )

        output = await agent(inp)
        _update_state(state, stage_name, output)
        _log.info(
            "Stage '%s' completed, output length=%d",
            stage_name,
            len(output.content),
        )

        previous_output = {
            "requirements": state.requirements or "",
            "solution": state.solution or "",
            "code_diff": state.code_diff or "",
            "test_code": state.test_code or "",
            "review_report": state.review_report or "",
        }

        await _write_output(config.output_dir, stage_name, output)
        _log.info("Stage '%s' artifacts written to '%s/'", stage_name, config.output_dir)

    _log.info("Pipeline finished")
    return state


def _get_agent(stage_name: str):
    """Get the agent function for a stage."""
    from agents import (
        requirements_agent,
        solution_agent,
        code_gen_agent,
        test_gen_agent,
        review_agent,
        delivery_agent,
    )

    agents = {
        "requirements": requirements_agent,
        "solution": solution_agent,
        "code_gen": code_gen_agent,
        "test_gen": test_gen_agent,
        "review": review_agent,
        "delivery": delivery_agent,
    }
    return agents.get(stage_name)


def _get_current_input(stage_name: str, original_input: str, state: PipelineState) -> str:
    """Determine the current_input for a stage."""
    if stage_name == "requirements":
        return original_input
    if stage_name == "solution":
        return state.requirements or ""
    if stage_name in ("code_gen", "test_gen", "review"):
        return getattr(state, "solution", "") or ""
    if stage_name == "delivery":
        return ""
    return original_input


def _update_state(state: PipelineState, stage_name: str, output: StageOutput) -> None:
    """Update PipelineState with the output of a stage."""
    if stage_name == "requirements":
        state.requirements = output.content
    elif stage_name == "solution":
        state.solution = output.content
    elif stage_name == "code_gen":
        state.code_diff = output.content
    elif stage_name == "test_gen":
        state.test_code = output.content
    elif stage_name == "review":
        state.review_report = output.content
    elif stage_name == "delivery":
        state.final_output = output.content


async def _write_output(output_dir: str, stage_name: str, output: StageOutput) -> None:
    """Write stage output to a file in the output directory."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    content_path = out_path / f"{stage_name}.md"
    content_path.write_text(output.content, encoding="utf-8")

    if output.artifacts:
        import json

        artifacts_path = out_path / f"{stage_name}_artifacts.json"
        artifacts_path.write_text(json.dumps(output.artifacts, indent=2, ensure_ascii=False), encoding="utf-8")

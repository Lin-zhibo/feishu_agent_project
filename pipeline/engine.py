"""
Pipeline engine for the DevFlow Engine.

Sequentially executes the 6 stages using LangChain RunnableSequence,
with Human-in-the-Loop checkpoints at solution and review stages.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pipeline.callbacks import PipelineCallbackHandler
from pipeline.checkpoint import confirm_checkpoint
from pipeline.models import (
    CheckpointDecision,
    PipelineConfig,
    PipelineState,
    StageInput,
    StageOutput,
)
from agents import (
    run_requirements,
    run_solution,
    run_code_gen,
    run_test_gen,
    run_review,
    run_delivery,
)

_log = logging.getLogger("pipeline.engine")

STAGE_ORDER = [
    "requirements",
    "solution",
    "code_gen",
    "test_gen",
    "review",
    "delivery",
]

MAX_RETRY = 10


async def run(input_text: str, config: PipelineConfig) -> PipelineState:
    """
    Run the full pipeline with checkpoint approvals.

    Args:
        input_text: The user's raw requirement string.
        config: Global pipeline configuration.

    Returns:
        PipelineState with all stage outputs filled in.
    """
    _log.info("Pipeline started: input='%s'", input_text)

    state = PipelineState(original_input=input_text)
    previous_output: dict | None = None

    handler = PipelineCallbackHandler()
    PipelineCallbackHandler.reset_totals()

    stage_idx = 0
    retry_counts: dict[str, int] = {"solution": 0, "review": 0}

    while stage_idx < len(STAGE_ORDER):
        stage_name = STAGE_ORDER[stage_idx]

        if not config.stage_enabled.get(stage_name, True):
            _log.info("Stage '%s' skipped (disabled)", stage_name)
            stage_idx += 1
            continue

        agent = _get_agent(stage_name)
        if agent is None:
            _log.warning("No agent found for stage '%s'", stage_name)
            stage_idx += 1
            continue

        current_input = _get_current_input(stage_name, input_text, state)
        _log.info("Stage '%s' starting, input length=%d", stage_name, len(current_input))

        inp = StageInput(
            stage_name=stage_name,
            previous_output=previous_output,
            current_input=current_input,
            config=config,
        )

        handler.stage_name = stage_name
        output = await agent(inp, callbacks=[handler], stream=True)
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

        # Print full stage output to console
        _print_stage_output(stage_name, output, config.output_dir)

        # Checkpoint after "solution"
        if stage_name == "solution":
            decision = confirm_checkpoint("solution", state.solution or "", config.skip_checkpoints, config.output_dir)
            if decision.decision == CheckpointDecision.REJECT:
                if retry_counts["solution"] >= MAX_RETRY:
                    raise RuntimeError(f"Max retry ({MAX_RETRY}) reached for 'solution'. Pipeline terminated.")
                retry_counts["solution"] += 1
                _log.warning("Solution rejected (attempt %d). Retrying with requirements.", retry_counts["solution"])
                state.solution = None
                state.code_diff = None
                state.test_code = None
                state.review_report = None
                state.final_output = None
                # Jump back to solution
                stage_idx = STAGE_ORDER.index("solution")
                continue

        # Checkpoint after "review"
        if stage_name == "review":
            # Log AI review decision
            if state.review_decision:
                _log.info(
                    "AI Review Decision: %s | Reason: %s | Critical Issues: %s",
                    "PASS" if state.review_decision.passed else "FAIL",
                    state.review_decision.reason,
                    state.review_decision.severity_issues or [],
                )

            decision = confirm_checkpoint(
                "review",
                state.review_report or "",
                config.skip_checkpoints,
                config.output_dir,
                review_decision=state.review_decision,
            )

            # State machine for review checkpoint
            ai_passed = state.review_decision.passed if state.review_decision else True

            if decision.decision == CheckpointDecision.APPROVE:
                if ai_passed:
                    # AI PASS + Human Approve → delivery
                    _log.info("Review: AI PASS + Human Approve → delivery")
                else:
                    # AI FAIL + Human Override (allow_human_override) → delivery
                    if config.allow_human_override_on_ai_fail:
                        _log.info("Review: AI FAIL + Human Override → delivery (recorded)")
                    else:
                        # Should not happen if config is correct, but guard anyway
                        _log.warning("Review: AI FAIL but Human Approve without override flag - treating as override")
            else:
                # Human Rejected
                if ai_passed:
                    # AI PASS + Human Reject → retry review with human feedback
                    if retry_counts["review"] >= MAX_RETRY:
                        raise RuntimeError(f"Max retry ({MAX_RETRY}) reached for 'review'. Pipeline terminated.")
                    retry_counts["review"] += 1
                    _log.warning("Review rejected by human (attempt %d). Retrying review with feedback.", retry_counts["review"])
                    state.review_report = None
                    # Jump back to review
                    stage_idx = STAGE_ORDER.index("review")
                    continue
                else:
                    # AI FAIL + Human Reject → code_gen
                    if retry_counts["review"] >= MAX_RETRY:
                        raise RuntimeError(f"Max retry ({MAX_RETRY}) reached for 'review'. Pipeline terminated.")
                    retry_counts["review"] += 1
                    _log.warning("Review AI FAIL + human reject (attempt %d). Retrying code_gen.", retry_counts["review"])
                    state.code_diff = None
                    state.test_code = None
                    state.review_report = None
                    state.final_output = None
                    # Jump back to code_gen
                    stage_idx = STAGE_ORDER.index("code_gen")
                    continue

        stage_idx += 1

    _log.info(
        "\n═══════════════════════════════════════════════════════\n"
        " Pipeline Summary\n"
        "   Total Time:   %s ms\n"
        "   Total Tokens: prompt=%s | completion=%s | total=%s\n"
        "═══════════════════════════════════════════════════════",
        handler.total_time_ms,
        handler.total_prompt_tokens,
        handler.total_completion_tokens,
        handler.total_tokens,
    )
    _log.info("Pipeline finished")
    return state


def _get_agent(stage_name: str):
    """Get the agent async function for a stage."""
    agents = {
        "requirements": run_requirements,
        "solution": run_solution,
        "code_gen": run_code_gen,
        "test_gen": run_test_gen,
        "review": run_review,
        "delivery": run_delivery,
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
        state.review_decision = output.review_decision
    elif stage_name == "delivery":
        state.final_output = output.content


async def _write_output(output_dir: str, stage_name: str, output: StageOutput) -> None:
    """Write stage output to a file in the output directory."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    content_path = out_path / f"{stage_name}.md"
    content_path.write_text(output.content, encoding="utf-8")

    if output.artifacts:
        artifacts_path = out_path / f"{stage_name}_artifacts.json"
        artifacts_path.write_text(
            json.dumps(output.artifacts, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _print_stage_output(stage_name: str, output: StageOutput, output_dir: str) -> None:
    """
    Print full stage output to console for visibility.

    Reads content from the output file (may be more complete than output.content
    when tools were used during the stage).
    """
    print(f"\n{'='*70}")
    print(f"  STAGE OUTPUT: {stage_name.upper()}")
    print(f"{'='*70}")

    # Try to read from file for complete content
    content_file = Path(output_dir) / f"{stage_name}.md"
    if content_file.exists():
        file_content = content_file.read_text(encoding="utf-8")
        if file_content.strip():
            print(file_content)
        else:
            print(output.content or "(empty)")
    else:
        print(output.content or "(empty)")

    print(f"{'='*70}\n")

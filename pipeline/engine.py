"""
Pipeline engine for the DevFlow Engine.

Sequentially executes the 6 stages with Human-in-the-Loop checkpoints
at solution and review stages. Supports pause/resume via disk checkpointing.
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import asdict
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


# ---------------------------------------------------------------------------
# Pause / Resume — state serialization
# ---------------------------------------------------------------------------

def _pause_file(log_dir: str, pipeline_id: str) -> Path:
    """Return the path to the pause file for a given pipeline ID."""
    return Path(log_dir) / pipeline_id / f"pipeline_{pipeline_id}.json"


def _save_paused_state(
    state: PipelineState,
    log_dir: str,
    stage_idx: int,
    reason: str,
) -> None:
    """Serialize PipelineState to disk for later resume."""
    log_path = Path(log_dir) / state.pipeline_id
    log_path.mkdir(parents=True, exist_ok=True)
    pause_path = _pause_file(log_dir, state.pipeline_id)
    data = {
        "pipeline_id": state.pipeline_id,
        "original_input": state.original_input,
        "current_stage_idx": stage_idx,
        "paused_at": datetime.datetime.now().isoformat(),
        "pause_reason": reason,
        "state": {
            "requirements": state.requirements,
            "solution": state.solution,
            "code_diff": state.code_diff,
            "test_code": state.test_code,
            "review_report": state.review_report,
            "review_decision": asdict(state.review_decision) if state.review_decision else None,
            "final_output": state.final_output,
            "human_feedback": state.human_feedback,
        },
    }
    pause_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _log.info("Pipeline state saved to %s", pause_path)


def _load_paused_state(log_dir: str, pipeline_id: str) -> tuple[PipelineState, int]:
    """Load a paused PipelineState from disk. Returns (state, stage_idx)."""
    pause_path = _pause_file(log_dir, pipeline_id)
    if not pause_path.exists():
        raise FileNotFoundError(f"Paused pipeline not found: {pause_path}")
    data = json.loads(pause_path.read_text(encoding="utf-8"))
    s = data["state"]
    stage_idx = data["current_stage_idx"]

    from pipeline.models import ReviewDecision
    rd = None
    if s.get("review_decision"):
        rd = ReviewDecision(
            passed=s["review_decision"]["passed"],
            reason=s["review_decision"]["reason"],
            severity_issues=s["review_decision"].get("severity_issues", []),
        )

    state = PipelineState(
        original_input=data["original_input"],
        pipeline_id=data["pipeline_id"],
        requirements=s.get("requirements"),
        solution=s.get("solution"),
        code_diff=s.get("code_diff"),
        test_code=s.get("test_code"),
        review_report=s.get("review_report"),
        review_decision=rd,
        final_output=s.get("final_output"),
        human_feedback=s.get("human_feedback"),
    )
    return state, stage_idx


def _delete_paused_state(log_dir: str, pipeline_id: str) -> bool:
    """Delete a paused pipeline file. Returns True if deleted."""
    pause_path = _pause_file(log_dir, pipeline_id)
    if pause_path.exists():
        pause_path.unlink()
        return True
    return False


def _cleanup_paused_state(state: PipelineState, log_dir: str) -> None:
    """Remove pause file after successful pipeline completion."""
    _delete_paused_state(log_dir, state.pipeline_id)


def list_paused(log_dir: str) -> list[dict]:
    """List all paused pipelines in the log directory."""
    log_root = Path(log_dir)
    if not log_root.exists():
        return []
    results = []
    for subdir in sorted(log_root.iterdir()):
        if not subdir.is_dir():
            continue
        for f in sorted(subdir.glob("pipeline_*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append({
                    "pipeline_id": data["pipeline_id"],
                    "original_input": data["original_input"][:80],
                    "paused_at": data.get("paused_at", ""),
                    "pause_reason": data.get("pause_reason", ""),
                })
            except Exception:
                pass
    return results


def terminate_all_paused(log_dir: str) -> int:
    """Delete all paused pipeline files. Returns count of deleted files."""
    log_root = Path(log_dir)
    if not log_root.exists():
        return 0
    count = 0
    for subdir in log_root.iterdir():
        if not subdir.is_dir():
            continue
        for f in subdir.glob("pipeline_*.json"):
            f.unlink()
            count += 1
    return count


# ---------------------------------------------------------------------------
# Budget check — pauses instead of crashing
# ---------------------------------------------------------------------------

def _try_pause(
    handler: PipelineCallbackHandler,
    config: PipelineConfig,
    state: PipelineState,
    stage_idx: int,
) -> bool:
    """
    Check time/token budgets. If exceeded, save state and return True.

    Args:
        handler: Callback handler with cumulative totals.
        config: Pipeline configuration with budget thresholds.
        state: Current PipelineState to save.
        stage_idx: Current stage index (where to resume).

    Returns:
        True if pipeline was paused (caller should exit gracefully).
        False if budgets are OK.
    """
    if handler.total_time_ms >= config.max_total_time_ms:
        reason = (
            f"Time budget exceeded: {handler.total_time_ms:,.0f}ms >= {config.max_total_time_ms:,}ms"
        )
        _save_paused_state(state, config.log_dir, stage_idx, reason)
        print(f"\n{'='*60}")
        print("  PIPELINE PAUSED")
        print(f"{'='*60}")
        print(f"  {reason}")
        print(f"  Resume:  python cli.py --resume {state.pipeline_id}")
        print("  List:    python cli.py --list")
        print(f"  Terminate: python cli.py --terminate {state.pipeline_id}")
        print(f"{'='*60}\n")
        return True

    if handler.total_tokens >= config.max_total_tokens:
        reason = (
            f"Token budget exceeded: {handler.total_tokens:,} >= {config.max_total_tokens:,}"
        )
        _save_paused_state(state, config.log_dir, stage_idx, reason)
        print(f"\n{'='*60}")
        print("  PIPELINE PAUSED")
        print(f"{'='*60}")
        print(f"  {reason}")
        print(f"  Resume:  python cli.py --resume {state.pipeline_id}")
        print("  List:    python cli.py --list")
        print(f"  Terminate: python cli.py --terminate {state.pipeline_id}")
        print(f"{'='*60}\n")
        return True

    return False


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

async def run(input_text: str, config: PipelineConfig) -> PipelineState:
    """
    Run the full pipeline with checkpoint approvals.

    Args:
        input_text: The user's raw requirement string.
        config: Global pipeline configuration.

    Returns:
        PipelineState with all stage outputs filled in.
    """
    pipeline_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_dir = str(Path(config.workspace).resolve() / pipeline_id)
    log_dir = str(Path(config.log_dir).resolve() / pipeline_id)
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    state = PipelineState(original_input=input_text, pipeline_id=pipeline_id)
    previous_output: dict | None = None

    handler = PipelineCallbackHandler()
    PipelineCallbackHandler.reset_totals()

    stage_idx = 0

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

        current_input = _get_current_input(stage_name, input_text, state, workspace_dir)
        _log.info("Stage '%s' starting, input length=%d", stage_name, len(current_input))

        inp = StageInput(
            stage_name=stage_name,
            previous_output=previous_output,
            current_input=current_input,
            config=config,
            workspace=workspace_dir,
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

        await _write_output(log_dir, stage_name, output)
        _log.info("Stage '%s' artifacts written to '%s/'", stage_name, log_dir)

        # Print full stage output to console
        _print_stage_output(stage_name, output, log_dir)

        # Checkpoint after "solution"
        if stage_name == "solution":
            decision = confirm_checkpoint("solution", state.solution or "", config.skip_checkpoints, log_dir)
            if decision.decision == CheckpointDecision.REJECT:
                if _try_pause(handler, config, state, stage_idx):
                    _log.info("Pipeline paused after solution checkpoint rejection")
                    state.current_stage_idx = stage_idx
                    return state
                _log.warning("Solution rejected. Retrying with human feedback.")
                state.solution = None
                state.code_diff = None
                state.test_code = None
                state.review_report = None
                state.final_output = None
                state.human_feedback = decision.reason or "No reason provided"
                stage_idx = STAGE_ORDER.index("solution")
                continue
            else:
                state.human_feedback = None

        # Checkpoint after "review"
        if stage_name == "review":
            rd = state.review_decision

            if rd and not rd.passed:
                if _try_pause(handler, config, state, stage_idx):
                    _log.info("Pipeline paused after AI FAIL auto-retry")
                    state.current_stage_idx = stage_idx
                    return state
                _log.warning(
                    "Review: AI FAIL → auto retry code_gen. Reason: %s | Issues: %s",
                    rd.reason,
                    rd.severity_issues or [],
                )
                feedback_parts = [f"AI 评审发现代码问题，拒绝通过。\n拒绝理由：{rd.reason}"]
                if rd.severity_issues:
                    feedback_parts.append(f"严重问题：{', '.join(rd.severity_issues)}")
                state.human_feedback = "\n".join(feedback_parts)
                state.code_diff = None
                state.test_code = None
                state.review_report = None
                state.final_output = None
                stage_idx = STAGE_ORDER.index("code_gen")
                continue

            decision = confirm_checkpoint(
                "review",
                state.review_report or "",
                config.skip_checkpoints,
                log_dir,
                review_decision=rd,
            )

            if decision.decision == CheckpointDecision.REJECT:
                if _try_pause(handler, config, state, stage_idx):
                    _log.info("Pipeline paused after review human rejection")
                    state.current_stage_idx = stage_idx
                    return state
                _log.warning("Review: AI PASS but human rejected. Retrying with stricter criteria.")
                reason_text = f" 拒绝理由：{decision.reason}" if decision.reason else ""
                state.human_feedback = (
                    f"人类审核员拒绝通过。{reason_text}"
                    " 请重新严格审查代码，必须输出 FAIL 裁决，"
                    "针对每个发现的问题给出具体的代码级修复方案。"
                )
                state.review_report = None
                stage_idx = STAGE_ORDER.index("review")
                continue
            else:
                state.human_feedback = None
                # → delivery

        stage_idx += 1

    if not config.preserve_session:
        _cleanup_paused_state(state, config.log_dir)
    else:
        _log.info("preserve_session=true, keeping pause file")

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


async def resume(pipeline_id: str, config: PipelineConfig) -> PipelineState:
    """
    Resume a previously paused pipeline.

    Args:
        pipeline_id: The pipeline ID to resume (matches pause filename).
        config: Global pipeline configuration (re-read from settings.json).

    Returns:
        PipelineState after completion.

    Raises:
        FileNotFoundError: If paused pipeline file does not exist.
    """
    state, stage_idx = _load_paused_state(config.log_dir, pipeline_id)
    _log.info("Resuming pipeline '%s' from stage %d (%s)", pipeline_id, stage_idx, STAGE_ORDER[stage_idx])

    workspace_dir = str(Path(config.workspace).resolve() / pipeline_id)
    log_dir = str(Path(config.log_dir).resolve() / pipeline_id)
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  RESUMING PIPELINE: {pipeline_id}")
    print(f"  Original: {state.original_input}")
    print(f"  Stage:    {STAGE_ORDER[stage_idx]}")
    print(f"  Paused:   {state.paused_at}")
    print(f"  Reason:   {state.pause_reason}")
    print(f"{'='*60}\n")

    previous_output = {
        "requirements": state.requirements or "",
        "solution": state.solution or "",
        "code_diff": state.code_diff or "",
        "test_code": state.test_code or "",
        "review_report": state.review_report or "",
    }

    handler = PipelineCallbackHandler()
    # Note: cumulative totals are reset on resume — budget is per-run
    PipelineCallbackHandler.reset_totals()

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

        current_input = _get_current_input(stage_name, state.original_input, state, workspace_dir)

        inp = StageInput(
            stage_name=stage_name,
            previous_output=previous_output,
            current_input=current_input,
            config=config,
            workspace=workspace_dir,
        )

        handler.stage_name = stage_name
        output = await agent(inp, callbacks=[handler], stream=True)
        _update_state(state, stage_name, output)

        previous_output = {
            "requirements": state.requirements or "",
            "solution": state.solution or "",
            "code_diff": state.code_diff or "",
            "test_code": state.test_code or "",
            "review_report": state.review_report or "",
        }

        await _write_output(log_dir, stage_name, output)
        _print_stage_output(stage_name, output, log_dir)

        # Checkpoint after "solution"
        if stage_name == "solution":
            decision = confirm_checkpoint("solution", state.solution or "", config.skip_checkpoints, log_dir)
            if decision.decision == CheckpointDecision.REJECT:
                if _try_pause(handler, config, state, stage_idx):
                    _log.info("Pipeline paused after solution checkpoint rejection (resume)")
                    state.current_stage_idx = stage_idx
                    return state
                state.solution = None
                state.code_diff = None
                state.test_code = None
                state.review_report = None
                state.final_output = None
                state.human_feedback = decision.reason or "No reason provided"
                stage_idx = STAGE_ORDER.index("solution")
                continue
            else:
                state.human_feedback = None

        # Checkpoint after "review"
        if stage_name == "review":
            rd = state.review_decision

            if rd and not rd.passed:
                if _try_pause(handler, config, state, stage_idx):
                    _log.info("Pipeline paused after AI FAIL auto-retry (resume)")
                    state.current_stage_idx = stage_idx
                    return state
                feedback_parts = [f"AI 评审发现代码问题，拒绝通过。\n拒绝理由：{rd.reason}"]
                if rd.severity_issues:
                    feedback_parts.append(f"严重问题：{', '.join(rd.severity_issues)}")
                state.human_feedback = "\n".join(feedback_parts)
                state.code_diff = None
                state.test_code = None
                state.review_report = None
                state.final_output = None
                stage_idx = STAGE_ORDER.index("code_gen")
                continue

            decision = confirm_checkpoint(
                "review", state.review_report or "", config.skip_checkpoints,
                log_dir, review_decision=rd,
            )

            if decision.decision == CheckpointDecision.REJECT:
                if _try_pause(handler, config, state, stage_idx):
                    _log.info("Pipeline paused after review human rejection (resume)")
                    state.current_stage_idx = stage_idx
                    return state
                reason_text = f" 拒绝理由：{decision.reason}" if decision.reason else ""
                state.human_feedback = (
                    f"人类审核员拒绝通过。{reason_text}"
                    " 请重新严格审查代码，必须输出 FAIL 裁决，"
                    "针对每个发现的问题给出具体的代码级修复方案。"
                )
                state.review_report = None
                stage_idx = STAGE_ORDER.index("review")
                continue
            else:
                state.human_feedback = None

        stage_idx += 1

    if not config.preserve_session:
        _cleanup_paused_state(state, config.log_dir)
    else:
        _log.info("preserve_session=true, keeping pause file")
    _log.info("Pipeline resumed and finished")
    return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _get_current_input(stage_name: str, original_input: str, state: PipelineState, workspace_dir: str = "") -> str:
    """Determine the current_input for a stage. Embeds workspace context where relevant."""
    if stage_name == "requirements":
        return original_input
    if stage_name == "solution":
        base = state.requirements or ""
        if state.human_feedback:
            return (
                base
                + "\n\n---\n## 人类反馈（上一版被拒绝）\n"
                + f"拒绝理由：{state.human_feedback}\n"
                + "请基于以上反馈重新设计方案，解决指出的问题。"
            )
        return base

    if stage_name == "code_gen":
        base = (
            "## Working Directory\n" + workspace_dir
            + "\n\n## Solution Design\n" + (state.solution or "")
        )
        if state.human_feedback:
            return base + "\n\n---\n## 反馈\n" + state.human_feedback
        return base

    if stage_name == "test_gen":
        base = (
            "## Working Directory\n" + workspace_dir
            + "\n\n## Solution Design\n" + (state.solution or "")
            + "\n\n## Code Changes\n" + (state.code_diff or "")
        )
        if state.human_feedback:
            return base + "\n\n---\n## 反馈\n" + state.human_feedback
        return base

    if stage_name == "review":
        base = (
            "## Working Directory\n" + workspace_dir
            + "\n\n## Solution Design\n" + (state.solution or "")
            + "\n\n## Code Diff\n" + (state.code_diff or "")
            + "\n\n## Test Code\n" + (state.test_code or "")
        )
        if state.human_feedback:
            return base + "\n\n---\n## 反馈\n" + state.human_feedback
        return base

    if stage_name == "delivery":
        return "## Working Directory\n" + workspace_dir + "\n\nFiles are in the workspace above."
    return original_input
    if stage_name == "solution":
        base = state.requirements or ""
        if state.human_feedback:
            return (
                base
                + "\n\n---\n## 人类反馈（上一版被拒绝）\n"
                + f"拒绝理由：{state.human_feedback}\n"
                + "请基于以上反馈重新设计方案，解决指出的问题。"
            )
        return base
    if stage_name == "code_gen":
        base = state.solution or ""
        if state.human_feedback:
            return base + "\n\n---\n## 反馈\n" + state.human_feedback
        return base

    if stage_name == "test_gen":
        base = (
            "## Solution Design\n" + (state.solution or "")
            + "\n\n## Code Changes\n" + (state.code_diff or "")
        )
        if state.human_feedback:
            return base + "\n\n---\n## 反馈\n" + state.human_feedback
        return base

    if stage_name == "review":
        base = (
            "## Solution Design\n" + (state.solution or "")
            + "\n\n## Code Diff\n" + (state.code_diff or "")
            + "\n\n## Test Code\n" + (state.test_code or "")
        )
        if state.human_feedback:
            return base + "\n\n---\n## 反馈\n" + state.human_feedback
        return base
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

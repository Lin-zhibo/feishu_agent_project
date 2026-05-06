"""
Checkpoint confirmation for Human-in-the-Loop approval.

Supports two modes:
- CLI: interactive input()
- API: asyncio.Event-based waiting
"""

from __future__ import annotations

import logging
from pathlib import Path

from pipeline.models import CheckpointDecision, CheckpointResult, ReviewDecision

_log = logging.getLogger("pipeline.checkpoint")


def confirm_checkpoint(
    stage_name: str,
    content: str,
    skip: bool = False,
    output_dir: str = "out",
    review_decision: ReviewDecision | None = None,
) -> CheckpointResult:
    """
    Display a checkpoint for human review and await Y/n confirmation.

    Args:
        stage_name: Name of the current stage (e.g., "solution", "review").
        content: Stage output content to display (may be empty if tools were used).
        skip: If True, auto-approve without prompting.
        output_dir: Directory where stage outputs are written.
        review_decision: AI review decision (for review stage checkpoints).

    Returns:
        CheckpointResult with APPROVE or REJECT decision.
    """
    if skip:
        return CheckpointResult(decision=CheckpointDecision.APPROVE)

    # Try to read content from the output file (may be more complete than content param)
    content_file = Path(output_dir) / f"{stage_name}.md"
    if content_file.exists():
        file_content = content_file.read_text(encoding="utf-8")
        if file_content.strip():
            content = file_content

    print(f"\n{'='*60}")
    print(f"  CHECKPOINT: {stage_name.upper()}")
    print(f"{'='*60}")

    # Show AI review decision for review stage (only AI PASS reaches this point)
    if stage_name == "review" and review_decision is not None:
        print("\n  [AI REVIEW DECISION: PASS]")
        print(f"  Reason: {review_decision.reason}")
        if review_decision.severity_issues:
            print("  Potential Issues:")
            for issue in review_decision.severity_issues:
                print(f"    - {issue}")
        print()

    print(content or "(empty)")
    print(f"{'='*60}")

    if stage_name == "solution":
        print("  Y = Approve")
        print("  n = Reject (will retry solution with your feedback)")
    else:
        print("  Y = Approve / Continue")
        print("  n = Reject (review will re-run with stricter criteria)")
    print(f"{'='*60}")

    try:
        raw = input("Your decision? (Y/n): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCheckpoint interrupted. Auto-approving to continue.")
        return CheckpointResult(decision=CheckpointDecision.APPROVE)

    if raw.lower() in ("y", "yes") or raw == "":
        return CheckpointResult(decision=CheckpointDecision.APPROVE)

    # Reject — ask for reason
    try:
        reason = input("Reason for rejection (required): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCheckpoint interrupted. Auto-approving to continue.")
        return CheckpointResult(decision=CheckpointDecision.APPROVE)

    return CheckpointResult(decision=CheckpointDecision.REJECT, reason=reason)


async def api_confirm_checkpoint(
    stage_name: str,
    content: str,
    output_dir: str,
    runtime,
) -> CheckpointResult:
    """
    API-mode checkpoint: wait for external approve/reject via asyncio.Event.

    Args:
        stage_name: Name of current stage.
        content: Stage output content.
        output_dir: Log directory.
        runtime: PipelineRuntime instance (has checkpoint_event and checkpoint_result).

    Returns:
        CheckpointResult from the API handler.
    """
    # Write content to log dir so API can serve it
    content_file = Path(output_dir) / f"{stage_name}.md"
    content_file.parent.mkdir(parents=True, exist_ok=True)
    content_file.write_text(content, encoding="utf-8")

    # Prepare checkpoint
    runtime.prepare_checkpoint()

    _log.info("API checkpoint [%s] waiting for approval...", stage_name)

    # Block until API handler sets the event
    await runtime.checkpoint_event.wait()

    result = runtime.checkpoint_result.get("result")
    if result is None:
        _log.warning("Checkpoint event set without result, defaulting to APPROVE")
        return CheckpointResult(decision=CheckpointDecision.APPROVE)

    _log.info("API checkpoint [%s] resolved: %s", stage_name, result.decision)
    return result
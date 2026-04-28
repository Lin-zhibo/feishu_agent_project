"""
Checkpoint confirmation for Human-in-the-Loop approval.

Displays stage output and prompts Y/n confirmation.
"""

from __future__ import annotations

from pipeline.models import CheckpointDecision, CheckpointResult


def confirm_checkpoint(stage_name: str, content: str, skip: bool = False) -> CheckpointResult:
    """
    Display a checkpoint for human review and await Y/n confirmation.

    Args:
        stage_name: Name of the current stage (e.g., "solution", "review").
        content: Stage output content to display.
        skip: If True, auto-approve without prompting.

    Returns:
        CheckpointResult with APPROVE or REJECT decision.
    """
    if skip:
        return CheckpointResult(decision=CheckpointDecision.APPROVE)

    print(f"\n{'='*60}")
    print(f"  CHECKPOINT: {stage_name.upper()}")
    print(f"{'='*60}")
    print(content)
    print(f"{'='*60}")
    print(f"  Y = Continue (Approve)")
    print(f"  n = Reject and Redo (with reason)")
    print(f"{'='*60}")

    resp = input("Your decision? (Y/n): ").strip().lower()

    if resp in ("y", "yes", ""):
        return CheckpointResult(decision=CheckpointDecision.APPROVE)

    # Reject — ask for reason
    reason = input("Reason for rejection (required): ").strip()
    return CheckpointResult(decision=CheckpointDecision.REJECT, reason=reason)
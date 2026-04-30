"""
Checkpoint confirmation for Human-in-the-Loop approval.

Displays stage output and prompts Y/n confirmation.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.models import CheckpointDecision, CheckpointResult, ReviewDecision


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

    # Show AI review decision for review stage
    if stage_name == "review" and review_decision is not None:
        ai_verdict = "✅ PASS" if review_decision.passed else "❌ FAIL"
        print(f"\n  [AI REVIEW DECISION: {ai_verdict}]")
        print(f"  Reason: {review_decision.reason}")
        if review_decision.severity_issues:
            print(f"  Critical Issues:")
            for issue in review_decision.severity_issues:
                print(f"    - {issue}")
        print()

    print(content or "(empty)")
    print(f"{'='*60}")

    # Different prompt based on AI decision
    if stage_name == "review" and review_decision is not None:
        if review_decision.passed:
            print(f"  Y = Continue (Approve)")
            print(f"  n = Reject with reason (will retry review)")
        else:
            print(f"  Y = Override AI and Continue (Use with caution)")
            print(f"  n = Reject and Retry (code_gen will rerun)")
    else:
        print(f"  Y = Continue (Approve)")
        print(f"  n = Reject and Redo (with reason)")
    print(f"{'='*60}")

    try:
        raw = input("Your decision? (Y/n): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCheckpoint interrupted. Auto-approving to continue.")
        return CheckpointResult(decision=CheckpointDecision.APPROVE)

    if raw.lower() in ("y", "yes") or raw == "":
        return CheckpointResult(decision=CheckpointDecision.APPROVE)

    resp = raw.lower()

    # Reject — ask for reason
    try:
        reason = input("Reason for rejection (required): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCheckpoint interrupted. Auto-approving to continue.")
        return CheckpointResult(decision=CheckpointDecision.APPROVE)

    return CheckpointResult(decision=CheckpointDecision.REJECT, reason=reason)
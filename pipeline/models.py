"""
Data models for the DevFlow Engine pipeline.

Classes:
    PipelineState: Global state shared across all stages.
    StageInput: Input passed to each stage/agent.
    StageOutput: Output produced by each stage/agent.
    PipelineConfig: Global pipeline configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckpointDecision(Enum):
    """Decision made at a checkpoint."""
    APPROVE = "approve"
    REJECT = "reject"


@dataclass
class ReviewDecision:
    """
    AI review decision with pass/fail and reasoning.

    Attributes:
        passed: True if review passed, False if rejected.
        reason: Explanation of why the review passed or failed.
        severity_issues: List of critical/high issues found (if any).
    """
    passed: bool
    reason: str
    severity_issues: list[str] = field(default_factory=list)


@dataclass
class CheckpointResult:
    """
    Result of a checkpoint review.

    Attributes:
        decision: The user's decision (APPROVE or REJECT).
        reason: Reason for rejection (only set when decision is REJECT).
    """
    decision: CheckpointDecision
    reason: str | None = None


@dataclass
class StageInput:
    """
    Input passed to each stage/agent.

    Attributes:
        stage_name: Name of the current stage (e.g., "requirements", "solution").
        previous_output: Output from the previous stage, or None if first stage.
        current_input: The text/content to process (user requirement or previous output).
        config: Global pipeline configuration.
        workspace: Absolute path of the pipeline's working directory.
    """

    stage_name: str
    previous_output: dict[str, Any] | None
    current_input: str
    config: "PipelineConfig"
    workspace: str = ""


@dataclass
class StageOutput:
    """
    Output produced by each stage/agent.

    Attributes:
        stage_name: Name of the stage that produced this output.
        content: Human-readable output content (e.g., requirements doc, code diff).
        artifacts: Structured artifacts produced (e.g., code files, review reports).
        next_input: Dict to pass to the next stage as its current_input.
        review_decision: AI review decision (only set for "review" stage).
    """

    stage_name: str
    content: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    next_input: dict[str, Any] = field(default_factory=dict)
    review_decision: ReviewDecision | None = None


@dataclass
class PipelineState:
    """
    Global state shared across all pipeline stages.

    Attributes:
        original_input: The raw user requirement string.
        pipeline_id: Unique identifier for this pipeline run (timestamp-based).
        current_stage_idx: Current stage index in STAGE_ORDER (for pause/resume).
        paused_at: ISO timestamp when the pipeline was paused (None if not paused).
        pause_reason: Human-readable reason for pausing.
        requirements: Output from the requirements analysis stage.
        solution: Output from the solution design stage.
        code_diff: Output from the code generation stage.
        test_code: Output from the test generation stage.
        review_report: Output from the code review stage.
        review_decision: AI review decision (passed/failed with reason).
        final_output: Output from the delivery integration stage.
        human_feedback: Feedback from human checkpoint rejection.
    """

    original_input: str
    pipeline_id: str = ""
    current_stage_idx: int = 0
    paused_at: str | None = None
    pause_reason: str | None = None
    requirements: str | None = None
    solution: str | None = None
    code_diff: str | None = None
    test_code: str | None = None
    review_report: str | None = None
    review_decision: ReviewDecision | None = None
    final_output: str | None = None
    human_feedback: str | None = None


@dataclass
class PipelineConfig:
    """
    Global pipeline configuration.

    Attributes:
        model_name: LLM model name to use (e.g., "deepseek-v4-flash").
        api_key: API key for the LLM provider.
        base_url: Base URL for the LLM API.
        stage_enabled: Dict mapping stage names to whether they are enabled.
        output_dir: Directory where output artifacts are written.
    """

    model_name: str
    api_key: str
    base_url: str
    stage_enabled: dict[str, bool] = field(default_factory=lambda: {
        "requirements": True,
        "solution": True,
        "code_gen": True,
        "test_gen": True,
        "review": True,
        "delivery": True,
    })
    output_dir: str = "out"
    skip_checkpoints: bool = False  # When True, skip all Y/n confirmations
    max_total_time_ms: int = 600000  # Max cumulative LLM time across the pipeline (ms)
    max_total_tokens: int = 50000   # Max cumulative LLM tokens across the pipeline
    max_retry: int = 3              # Max LLM API call retries (before terminating)
    temperature: float = 0.3        # LLM temperature (0.0 = deterministic, 2.0 = creative)
    max_tool_iterations: int = 20   # Max tool-calling loop iterations per stage
    preserve_session: bool = False  # Keep pause file after completion (for audit)
    verbose: bool = False           # Log full LLM request/response content
    workspace: str = "./out"        # Root workspace dir (pipeline creates ./out/<id>/ subdir)
    log_dir: str = "tmp"            # Root log dir (stage .md outputs, pause files go here)

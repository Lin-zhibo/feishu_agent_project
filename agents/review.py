"""
Code Review Agent.

Wraps LangChain RunnableSequence for code review stage.
"""

from __future__ import annotations

import logging
import re

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from pipeline.models import PipelineConfig, ReviewDecision, StageInput, StageOutput
from prompts import REVIEW_PROMPT
from tools import STAGE_TOOLS
from agents._tool_runner import invoke_agent_with_tools

_log = logging.getLogger("agents.review")


def create_review_chain(config: PipelineConfig) -> RunnableSequence:
    """
    Create a RunnableSequence for the code review stage.

    Args:
        config: Global pipeline configuration.

    Returns:
        RunnableSequence equivalent to LLMChain with output_key="review_report".
    """
    llm = ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0.3,
    )
    return REVIEW_PROMPT | llm.bind_tools(STAGE_TOOLS["review"])


async def run_review(
    inp: StageInput,
    callbacks: list[BaseCallbackHandler] | None = None,
    stream: bool = False,
) -> StageOutput:
    """
    Run the code review stage with tool-calling agent loop.

    Args:
        inp: StageInput containing stage_name, previous_output, current_input, config.
        callbacks: Optional list of BaseCallbackHandler for LangChain callbacks.
        stream: If True, stream tool calls and final output to console.

    Returns:
        StageOutput with content (review report), artifacts, and review_decision.
    """
    _log.info("Stage 'review' started")

    llm = ChatOpenAI(
        model=inp.config.model_name,
        api_key=inp.config.api_key,
        base_url=inp.config.base_url,
        temperature=inp.config.temperature,
    )

    content = await invoke_agent_with_tools(
        prompt_template=REVIEW_PROMPT,
        llm=llm,
        tools=STAGE_TOOLS["review"],
        inputs={"input": inp.current_input},
        callbacks=callbacks,
        stream=stream,
        max_retry=inp.config.max_retry,
        max_tool_iterations=inp.config.max_tool_iterations,
        verbose=inp.config.verbose,
    )

    review_decision = _parse_review_decision(content)
    _log.info("Stage 'review' completed, output length=%d, decision=%s", len(content), review_decision.passed)

    return StageOutput(
        stage_name="review",
        content=content,
        artifacts={"review_report": content},
        next_input={"input": content},
        review_decision=review_decision,
    )


def _parse_review_decision(content: str) -> ReviewDecision:
    """
    Parse the review decision from the AI's content.

    Expects content to end with:
    ## VERDICT
    PASS/FAIL
    Reason: <explanation>
    Critical Issues: <list if any, or "None">

    Args:
        content: The full review report text.

    Returns:
        ReviewDecision with passed=True/False and reasoning.
    """
    verdict_match = re.search(
        r"## VERDICT\s*\n(PASS|FAIL)\s*\nReason:\s*(.+?)\s*\nCritical Issues:\s*(.+?)(?:\n|$)",
        content,
        re.IGNORECASE | re.DOTALL,
    )

    if verdict_match:
        passed = verdict_match.group(1).upper() == "PASS"
        reason = verdict_match.group(2).strip()
        critical_raw = verdict_match.group(3).strip()

        severity_issues = []
        if critical_raw and critical_raw != "None":
            severity_issues = [s.strip() for s in re.split(r"[,\n]", critical_raw) if s.strip()]

        return ReviewDecision(passed=passed, reason=reason, severity_issues=severity_issues)

    if re.search(r"\bPASS\b", content, re.IGNORECASE):
        return ReviewDecision(passed=True, reason="Review completed (PASS found in content)")
    elif re.search(r"\bFAIL\b", content, re.IGNORECASE):
        return ReviewDecision(
            passed=False,
            reason="Review completed (FAIL found in content)",
            severity_issues=["Unknown - no structured verdict"],
        )

    return ReviewDecision(passed=True, reason="No structured verdict found, defaulting to pass")

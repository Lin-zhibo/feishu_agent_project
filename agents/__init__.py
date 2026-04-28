"""
LLM Agents for each stage of the DevFlow Engine pipeline.

Each agent wraps a LangChain LLMChain and exposes an async run() interface.
"""

from __future__ import annotations

from langchain_core.callbacks import BaseCallbackHandler

from pipeline.models import ReviewDecision, StageInput, StageOutput
from chains import (
    create_requirements_chain,
    create_solution_chain,
    create_code_gen_chain,
    create_test_gen_chain,
    create_review_chain,
    create_delivery_chain,
)

__all__ = [
    "run_requirements",
    "run_solution",
    "run_code_gen",
    "run_test_gen",
    "run_review",
    "run_delivery",
]


async def run_requirements(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None, stream: bool = False) -> StageOutput:
    """Run the requirements analysis stage via LangChain RunnableSequence."""
    chain = create_requirements_chain(inp.config)
    content = ""

    if stream:
        # Stream tokens to console
        print(f"\n{'='*70}")
        print(f"  [STREAM] requirements")
        print(f"{'='*70}")
        async for chunk in chain.astream({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {}):
            if hasattr(chunk, "content") and chunk.content:
                print(chunk.content, end="", flush=True)
                content += chunk.content
        print(f"\n{'='*70}\n")
    else:
        result = await chain.ainvoke({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {})
        content = result.content if hasattr(result, "content") else str(result)

    return StageOutput(
        stage_name="requirements",
        content=content,
        artifacts={"requirements_doc": content},
        next_input={"input": content},
    )


async def run_solution(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None, stream: bool = False) -> StageOutput:
    """Run the solution design stage via LangChain RunnableSequence."""
    chain = create_solution_chain(inp.config)
    content = ""

    if stream:
        print(f"\n{'='*70}")
        print(f"  [STREAM] solution")
        print(f"{'='*70}")
        async for chunk in chain.astream({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {}):
            if hasattr(chunk, "content") and chunk.content:
                print(chunk.content, end="", flush=True)
                content += chunk.content
        print(f"\n{'='*70}\n")
    else:
        result = await chain.ainvoke({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {})
        content = result.content if hasattr(result, "content") else str(result)

    return StageOutput(
        stage_name="solution",
        content=content,
        artifacts={"solution_doc": content},
        next_input={"input": content},
    )


async def run_code_gen(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None, stream: bool = False) -> StageOutput:
    """Run the code generation stage via LangChain RunnableSequence."""
    chain = create_code_gen_chain(inp.config)
    content = ""

    if stream:
        print(f"\n{'='*70}")
        print(f"  [STREAM] code_gen")
        print(f"{'='*70}")
        async for chunk in chain.astream({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {}):
            if hasattr(chunk, "content") and chunk.content:
                print(chunk.content, end="", flush=True)
                content += chunk.content
        print(f"\n{'='*70}\n")
    else:
        result = await chain.ainvoke({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {})
        content = result.content if hasattr(result, "content") else str(result)

    return StageOutput(
        stage_name="code_gen",
        content=content,
        artifacts={"code_diff": content},
        next_input={"input": content},
    )


async def run_test_gen(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None, stream: bool = False) -> StageOutput:
    """Run the test generation stage via LangChain RunnableSequence."""
    chain = create_test_gen_chain(inp.config)
    content = ""

    if stream:
        print(f"\n{'='*70}")
        print(f"  [STREAM] test_gen")
        print(f"{'='*70}")
        async for chunk in chain.astream({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {}):
            if hasattr(chunk, "content") and chunk.content:
                print(chunk.content, end="", flush=True)
                content += chunk.content
        print(f"\n{'='*70}\n")
    else:
        result = await chain.ainvoke({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {})
        content = result.content if hasattr(result, "content") else str(result)

    return StageOutput(
        stage_name="test_gen",
        content=content,
        artifacts={"test_code": content},
        next_input={"input": content},
    )


async def run_review(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None, stream: bool = False) -> StageOutput:
    """Run the code review stage via LangChain RunnableSequence."""
    chain = create_review_chain(inp.config)
    content = ""

    if stream:
        print(f"\n{'='*70}")
        print(f"  [STREAM] review")
        print(f"{'='*70}")
        async for chunk in chain.astream({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {}):
            if hasattr(chunk, "content") and chunk.content:
                print(chunk.content, end="", flush=True)
                content += chunk.content
        print(f"\n{'='*70}\n")
    else:
        result = await chain.ainvoke({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {})
        content = result.content if hasattr(result, "content") else str(result)

    # Parse review decision from content (both stream and non-stream paths)
    review_decision = _parse_review_decision(content)

    return StageOutput(
        stage_name="review",
        content=content,
        artifacts={"review_report": content},
        next_input={"input": content},
        review_decision=review_decision,
    )


async def run_delivery(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None, stream: bool = False) -> StageOutput:
    """Run the delivery integration stage via LangChain RunnableSequence."""
    chain = create_delivery_chain(inp.config)
    prev = inp.previous_output or {}
    content = ""

    if stream:
        print(f"\n{'='*70}")
        print(f"  [STREAM] delivery")
        print(f"{'='*70}")
        async for chunk in chain.astream({
            "req": prev.get("requirements", ""),
            "solution": prev.get("solution", ""),
            "code_diff": prev.get("code_diff", ""),
            "test_code": prev.get("test_code", ""),
            "review_report": prev.get("review_report", ""),
        }, {"callbacks": callbacks} if callbacks else {}):
            if hasattr(chunk, "content") and chunk.content:
                print(chunk.content, end="", flush=True)
                content += chunk.content
        print(f"\n{'='*70}\n")
    else:
        result = await chain.ainvoke({
            "req": prev.get("requirements", ""),
            "solution": prev.get("solution", ""),
            "code_diff": prev.get("code_diff", ""),
            "test_code": prev.get("test_code", ""),
            "review_report": prev.get("review_report", ""),
        }, {"callbacks": callbacks} if callbacks else {})
        content = result.content if hasattr(result, "content") else str(result)

    return StageOutput(
        stage_name="delivery",
        content=content,
        artifacts={"delivery_summary": content},
        next_input={},
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
    import re

    # Look for VERDICT section at the end
    verdict_match = re.search(r"## VERDICT\s*\n(PASS|FAIL)\s*\nReason:\s*(.+?)\s*\nCritical Issues:\s*(.+?)(?:\n|$)", content, re.IGNORECASE | re.DOTALL)

    if verdict_match:
        passed = verdict_match.group(1).upper() == "PASS"
        reason = verdict_match.group(2).strip()
        critical_raw = verdict_match.group(3).strip()

        severity_issues = []
        if critical_raw and critical_raw != "None":
            # Split by comma or newline
            severity_issues = [s.strip() for s in re.split(r"[,\n]", critical_raw) if s.strip()]

        return ReviewDecision(passed=passed, reason=reason, severity_issues=severity_issues)

    # Fallback: check for PASS/FAIL keyword in content
    if re.search(r"\bPASS\b", content, re.IGNORECASE):
        return ReviewDecision(passed=True, reason="Review completed (PASS found in content)")
    elif re.search(r"\bFAIL\b", content, re.IGNORECASE):
        return ReviewDecision(passed=False, reason="Review completed (FAIL found in content)", severity_issues=["Unknown - no structured verdict"])

    # No verdict found, default to pass with unknown
    return ReviewDecision(passed=True, reason="No structured verdict found, defaulting to pass")

"""
LLM Agents for each stage of the DevFlow Engine pipeline.

Each agent wraps a LangChain LLMChain and exposes an async run() interface.
"""

from __future__ import annotations

from langchain_core.callbacks import BaseCallbackHandler

from pipeline.models import StageInput, StageOutput
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


async def run_requirements(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None) -> StageOutput:
    """Run the requirements analysis stage via LangChain RunnableSequence."""
    chain = create_requirements_chain(inp.config)
    result = await chain.ainvoke({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {})
    content = result.content if hasattr(result, "content") else str(result)
    return StageOutput(
        stage_name="requirements",
        content=content,
        artifacts={"requirements_doc": content},
        next_input={"input": content},
    )


async def run_solution(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None) -> StageOutput:
    """Run the solution design stage via LangChain RunnableSequence."""
    chain = create_solution_chain(inp.config)
    result = await chain.ainvoke({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {})
    content = result.content if hasattr(result, "content") else str(result)
    return StageOutput(
        stage_name="solution",
        content=content,
        artifacts={"solution_doc": content},
        next_input={"input": content},
    )


async def run_code_gen(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None) -> StageOutput:
    """Run the code generation stage via LangChain RunnableSequence."""
    chain = create_code_gen_chain(inp.config)
    result = await chain.ainvoke({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {})
    content = result.content if hasattr(result, "content") else str(result)
    return StageOutput(
        stage_name="code_gen",
        content=content,
        artifacts={"code_diff": content},
        next_input={"input": content},
    )


async def run_test_gen(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None) -> StageOutput:
    """Run the test generation stage via LangChain RunnableSequence."""
    chain = create_test_gen_chain(inp.config)
    result = await chain.ainvoke({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {})
    content = result.content if hasattr(result, "content") else str(result)
    return StageOutput(
        stage_name="test_gen",
        content=content,
        artifacts={"test_code": content},
        next_input={"input": content},
    )


async def run_review(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None) -> StageOutput:
    """Run the code review stage via LangChain RunnableSequence."""
    chain = create_review_chain(inp.config)
    result = await chain.ainvoke({"input": inp.current_input}, {"callbacks": callbacks} if callbacks else {})
    content = result.content if hasattr(result, "content") else str(result)
    return StageOutput(
        stage_name="review",
        content=content,
        artifacts={"review_report": content},
        next_input={"input": content},
    )


async def run_delivery(inp: StageInput, callbacks: list[BaseCallbackHandler] | None = None) -> StageOutput:
    """Run the delivery integration stage via LangChain RunnableSequence."""
    chain = create_delivery_chain(inp.config)
    prev = inp.previous_output or {}
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

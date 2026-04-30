"""
Delivery Integration Agent.

Wraps LangChain RunnableSequence for delivery integration stage.
"""

from __future__ import annotations

import logging

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from pipeline.models import PipelineConfig, StageInput, StageOutput
from prompts import DELIVERY_PROMPT
from tools import STAGE_TOOLS
from agents._tool_runner import invoke_agent_with_tools

_log = logging.getLogger("agents.delivery")


def create_delivery_chain(config: PipelineConfig) -> RunnableSequence:
    """
    Create a RunnableSequence for the delivery integration stage.

    Args:
        config: Global pipeline configuration.

    Returns:
        RunnableSequence equivalent to LLMChain with output_key="final_output".
    """
    llm = ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0.3,
    )
    return DELIVERY_PROMPT | llm.bind_tools(STAGE_TOOLS["delivery"])


async def run_delivery(
    inp: StageInput,
    callbacks: list[BaseCallbackHandler] | None = None,
    stream: bool = False,
) -> StageOutput:
    """
    Run the delivery integration stage with tool-calling agent loop.

    Args:
        inp: StageInput containing stage_name, previous_output, current_input, config.
        callbacks: Optional list of BaseCallbackHandler for LangChain callbacks.
        stream: If True, stream tool calls and final output to console.

    Returns:
        StageOutput with content (delivery summary) and artifacts.
    """
    _log.info("Stage 'delivery' started")

    prev = inp.previous_output or {}

    llm = ChatOpenAI(
        model=inp.config.model_name,
        api_key=inp.config.api_key,
        base_url=inp.config.base_url,
        temperature=inp.config.temperature,
    )

    content = await invoke_agent_with_tools(
        prompt_template=DELIVERY_PROMPT,
        llm=llm,
        tools=STAGE_TOOLS["delivery"],
        inputs={
            "req": prev.get("requirements", ""),
            "solution": prev.get("solution", ""),
            "code_diff": prev.get("code_diff", ""),
            "test_code": prev.get("test_code", ""),
            "review_report": prev.get("review_report", ""),
        },
        callbacks=callbacks,
        stream=stream,
        max_retry=inp.config.max_retry,
        max_tool_iterations=inp.config.max_tool_iterations,
        verbose=inp.config.verbose,
    )

    _log.info("Stage 'delivery' completed, output length=%d", len(content))
    return StageOutput(
        stage_name="delivery",
        content=content,
        artifacts={"delivery_summary": content},
        next_input={},
    )

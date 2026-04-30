"""
Test Generation Agent.

Wraps LangChain RunnableSequence for test generation stage.
"""

from __future__ import annotations

import logging

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from pipeline.models import PipelineConfig, StageInput, StageOutput
from prompts import TEST_GEN_PROMPT
from tools import STAGE_TOOLS
from agents._tool_runner import invoke_agent_with_tools

_log = logging.getLogger("agents.test_gen")


def create_test_gen_chain(config: PipelineConfig) -> RunnableSequence:
    """
    Create a RunnableSequence for the test generation stage.

    Args:
        config: Global pipeline configuration.

    Returns:
        RunnableSequence equivalent to LLMChain with output_key="test_code".
    """
    llm = ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0.3,
    )
    return TEST_GEN_PROMPT | llm.bind_tools(STAGE_TOOLS["test_gen"])


async def run_test_gen(
    inp: StageInput,
    callbacks: list[BaseCallbackHandler] | None = None,
    stream: bool = False,
) -> StageOutput:
    """
    Run the test generation stage with tool-calling agent loop.

    Args:
        inp: StageInput containing stage_name, previous_output, current_input, config.
        callbacks: Optional list of BaseCallbackHandler for LangChain callbacks.
        stream: If True, stream tool calls and final output to console.

    Returns:
        StageOutput with content (test code) and artifacts.
    """
    _log.info("Stage 'test_gen' started")

    llm = ChatOpenAI(
        model=inp.config.model_name,
        api_key=inp.config.api_key,
        base_url=inp.config.base_url,
        temperature=inp.config.temperature,
    )

    content = await invoke_agent_with_tools(
        prompt_template=TEST_GEN_PROMPT,
        llm=llm,
        tools=STAGE_TOOLS["test_gen"],
        inputs={"input": inp.current_input},
        callbacks=callbacks,
        stream=stream,
        max_retry=inp.config.max_retry,
        max_tool_iterations=inp.config.max_tool_iterations,
        verbose=inp.config.verbose,
    )

    _log.info("Stage 'test_gen' completed, output length=%d", len(content))
    return StageOutput(
        stage_name="test_gen",
        content=content,
        artifacts={"test_code": content},
        next_input={"input": content},
    )

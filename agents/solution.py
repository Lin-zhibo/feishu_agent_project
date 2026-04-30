"""
Solution Design Agent.

Wraps LangChain RunnableSequence for solution design stage.
"""

from __future__ import annotations

import logging

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from pipeline.models import PipelineConfig, StageInput, StageOutput
from prompts import SOLUTION_PROMPT
from tools import STAGE_TOOLS
from agents._tool_runner import invoke_agent_with_tools

_log = logging.getLogger("agents.solution")


def create_solution_chain(config: PipelineConfig) -> RunnableSequence:
    """
    Create a RunnableSequence for the solution design stage.

    Args:
        config: Global pipeline configuration.

    Returns:
        RunnableSequence equivalent to LLMChain with output_key="solution".
    """
    llm = ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0.3,
    )
    return SOLUTION_PROMPT | llm.bind_tools(STAGE_TOOLS["solution"])


async def run_solution(
    inp: StageInput,
    callbacks: list[BaseCallbackHandler] | None = None,
    stream: bool = False,
) -> StageOutput:
    """
    Run the solution design stage with tool-calling agent loop.

    Args:
        inp: StageInput containing stage_name, previous_output, current_input, config.
        callbacks: Optional list of BaseCallbackHandler for LangChain callbacks.
        stream: If True, stream tool calls and final output to console.

    Returns:
        StageOutput with content (solution document) and artifacts.
    """
    _log.info("Stage 'solution' started")

    llm = ChatOpenAI(
        model=inp.config.model_name,
        api_key=inp.config.api_key,
        base_url=inp.config.base_url,
        temperature=inp.config.temperature,
    )

    content = await invoke_agent_with_tools(
        prompt_template=SOLUTION_PROMPT,
        llm=llm,
        tools=STAGE_TOOLS["solution"],
        inputs={"input": inp.current_input},
        callbacks=callbacks,
        stream=stream,
        max_retry=inp.config.max_retry,
        max_tool_iterations=inp.config.max_tool_iterations,
        verbose=inp.config.verbose,
    )

    _log.info("Stage 'solution' completed, output length=%d", len(content))
    return StageOutput(
        stage_name="solution",
        content=content,
        artifacts={"solution_doc": content},
        next_input={"input": content},
    )

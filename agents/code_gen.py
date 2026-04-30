"""
Code Generation Agent.

Wraps LangChain RunnableSequence for code generation stage.
"""

from __future__ import annotations

import logging

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from pipeline.models import PipelineConfig, StageInput, StageOutput
from prompts import CODE_GEN_PROMPT
from tools import STAGE_TOOLS
from agents._tool_runner import invoke_agent_with_tools

_log = logging.getLogger("agents.code_gen")


def create_code_gen_chain(config: PipelineConfig) -> RunnableSequence:
    """
    Create a RunnableSequence for the code generation stage.

    Args:
        config: Global pipeline configuration.

    Returns:
        RunnableSequence equivalent to LLMChain with output_key="code_diff".
    """
    llm = ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0.3,
    )
    return CODE_GEN_PROMPT | llm.bind_tools(STAGE_TOOLS["code_gen"])


async def run_code_gen(
    inp: StageInput,
    callbacks: list[BaseCallbackHandler] | None = None,
    stream: bool = False,
) -> StageOutput:
    """
    Run the code generation stage with tool-calling agent loop.

    Args:
        inp: StageInput containing stage_name, previous_output, current_input, config.
        callbacks: Optional list of BaseCallbackHandler for LangChain callbacks.
        stream: If True, stream tool calls and final output to console.

    Returns:
        StageOutput with content (code diff) and artifacts.
    """
    _log.info("Stage 'code_gen' started")

    llm = ChatOpenAI(
        model=inp.config.model_name,
        api_key=inp.config.api_key,
        base_url=inp.config.base_url,
        temperature=0.3,
    )

    content = await invoke_agent_with_tools(
        prompt_template=CODE_GEN_PROMPT,
        llm=llm,
        tools=STAGE_TOOLS["code_gen"],
        inputs={"input": inp.current_input},
        callbacks=callbacks,
        stream=stream,
    )

    _log.info("Stage 'code_gen' completed, output length=%d", len(content))
    return StageOutput(
        stage_name="code_gen",
        content=content,
        artifacts={"code_diff": content},
        next_input={"input": content},
    )

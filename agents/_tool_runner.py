"""
Shared tool-calling agent loop for all pipeline stages.

Uses raw OpenAI-compatible API calls with plain dict messages to ensure
all provider-specific response fields (e.g., reasoning_content from DeepSeek,
custom fields from other providers) are preserved when messages are re-sent
in subsequent turns.

Prior to this, the loop used LangChain Message objects and llm.ainvoke(),
which caused provider-specific fields in additional_kwargs to be dropped
during serialization — breaking any provider that requires round-trip
preservation of custom response fields.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai import ChatOpenAI

_log = logging.getLogger("agents._tool_runner")

MAX_TOOL_ITERATIONS = 20


async def invoke_agent_with_tools(
    prompt_template: PromptTemplate,
    llm: ChatOpenAI,
    tools: list[BaseTool],
    inputs: dict[str, Any],
    callbacks: list[BaseCallbackHandler] | None = None,
    stream: bool = False,
) -> str:
    """
    Invoke an LLM agent with a tool-calling loop via raw API calls.

    Uses plain dict messages instead of LangChain Message objects so that
    all provider-specific response fields are round-tripped intact.

    Args:
        prompt_template: PromptTemplate whose input variables match `inputs`.
        llm: ChatOpenAI instance (api_key / base_url / model_name configured).
        tools: List of BaseTool the agent is allowed to call.
        inputs: Dict of input variable values for the prompt template.
        callbacks: Optional list of LangChain callback handlers for metrics.
        stream: If True, print tool calls and final output to console.

    Returns:
        The final content string from the LLM after all tool calls are resolved.
    """
    prompt_text = prompt_template.invoke(inputs).to_string()

    # Message history in plain dict format (OpenAI-compatible).
    # Using dicts avoids LangChain's serialization layer which drops
    # unknown additional_kwargs fields like reasoning_content.
    api_messages: list[dict[str, Any]] = [{"role": "user", "content": prompt_text}]

    # Convert LangChain tools to OpenAI function definitions
    openai_tools = [convert_to_openai_tool(t) for t in tools] if tools else None
    tool_map = {t.name: t for t in tools}

    if stream:
        print(f"\n{'='*70}")
        print(f"  [TOOLS] {', '.join(t.name for t in tools)}")
        print(f"{'='*70}")

    for iteration in range(MAX_TOOL_ITERATIONS):
        _fire_llm_start(callbacks, api_messages)

        response = await llm.async_client.create(
            model=llm.model_name,
            messages=api_messages,
            tools=openai_tools,
            temperature=llm.temperature,
        )

        _fire_llm_end(callbacks, response)

        choice = response.choices[0]
        msg = choice.message

        # Build assistant message dict from raw response.
        # model_dump(mode="json") serializes ALL Pydantic fields — including
        # provider-specific ones like reasoning_content — into a plain dict.
        # exclude_none: omit null fields (e.g., content when only tool_calls)
        # exclude_unset: omit fields the API didn't explicitly set
        assistant_dict: dict[str, Any] = msg.model_dump(
            mode="json",
            exclude_none=True,
            exclude_unset=True,
        )
        assistant_dict["role"] = "assistant"
        api_messages.append(assistant_dict)

        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool = tool_map.get(tc.function.name)
                args = json.loads(tc.function.arguments)

                _fire_tool_start(callbacks, tc.function.name, args)

                if tool is None:
                    tool_output = f"Error: Tool '{tc.function.name}' is not available."
                    _log.warning("Tool '%s' not found in registered tools", tc.function.name)
                else:
                    try:
                        tool_output_raw = await tool.ainvoke(args)
                        tool_output = str(tool_output_raw)
                    except Exception as e:
                        tool_output = f"Error: {e}"
                        _log.warning("Tool '%s' execution failed: %s", tc.function.name, e)

                _fire_tool_end(callbacks, tool_output)

                api_messages.append({
                    "role": "tool",
                    "content": tool_output,
                    "tool_call_id": tc.id,
                })
                if stream:
                    print(f"  [TOOL] {tc.function.name} → {tool_output[:200]}")
        else:
            content = msg.content or ""
            if stream:
                print(content)
                print(f"\n{'='*70}\n")
            _log.info("Agent loop ended after %d iterations", iteration + 1)
            return content

    _log.warning("Max tool iterations (%d) reached, returning last response", MAX_TOOL_ITERATIONS)
    last_msg = api_messages[-1]
    return last_msg.get("content", "") if isinstance(last_msg, dict) else ""


# ---------------------------------------------------------------------------
# Callback helpers — manually invoke handler methods since we bypass
# LangChain's run manager by using raw API calls.
# ---------------------------------------------------------------------------

def _fire_llm_start(
    callbacks: list[BaseCallbackHandler] | None,
    messages: list[dict[str, Any]],
) -> None:
    """Fire on_llm_start on each callback handler."""
    if not callbacks:
        return
    serialized = {"name": "ChatOpenAI"}
    prompts = [json.dumps(m, ensure_ascii=False) for m in messages]
    for cb in callbacks:
        try:
            cb.on_llm_start(serialized, prompts)
        except Exception:
            pass


def _fire_llm_end(
    callbacks: list[BaseCallbackHandler] | None,
    response: Any,
) -> None:
    """Fire on_llm_end with an LLMResult carrying token usage from the raw response."""
    if not callbacks:
        return

    token_usage: dict[str, int] = {}
    if hasattr(response, "usage") and response.usage:
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens or 0,
            "completion_tokens": response.usage.completion_tokens or 0,
            "total_tokens": response.usage.total_tokens or 0,
        }

    model_name = getattr(response, "model", "")

    llm_result = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content=""))]],
        llm_output={
            "token_usage": token_usage,
            "model_name": model_name,
        },
    )

    for cb in callbacks:
        try:
            cb.on_llm_end(llm_result)
        except Exception:
            pass


def _fire_tool_start(
    callbacks: list[BaseCallbackHandler] | None,
    tool_name: str,
    args: dict[str, Any],
) -> None:
    """Fire on_tool_start on each callback handler."""
    if not callbacks:
        return
    serialized = {"name": tool_name}
    input_str = json.dumps(args, ensure_ascii=False)
    for cb in callbacks:
        try:
            cb.on_tool_start(serialized, input_str)
        except Exception:
            pass


def _fire_tool_end(
    callbacks: list[BaseCallbackHandler] | None,
    output: str,
) -> None:
    """Fire on_tool_end on each callback handler."""
    if not callbacks:
        return
    for cb in callbacks:
        try:
            cb.on_tool_end(output)
        except Exception:
            pass

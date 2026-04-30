"""
Sub-agent executor for DevFlow pipeline.

Runs a lightweight tool-calling agent loop with a restricted tool set,
used by the SpawnSubAgent tool to fork parallel work (e.g., writing files).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

_log = logging.getLogger("agents.sub_agent")

_RETRYABLE = (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
)

SYSTEM_PROMPTS: dict[str, str] = {
    "file-writer": (
        "You are a file writer. Your only job is to create EXACTLY ONE file. "
        "Use the Write tool to create the file. Do NOT read, search, or edit existing files. "
        "Do NOT ask questions. Write the file and output 'Done.' when finished."
    ),
    "code-reviewer": (
        "You are a code reviewer. Review the specified file for correctness, "
        "security, and best practices. Use Read to read the file. "
        "Do NOT edit files. Output a review report with issues found and suggestions."
    ),
    "test-writer": (
        "You are a test writer. Write tests for the specified code. "
        "Use Read to read the source file, Write to create the test file, "
        "and Bash to run 'python -m pytest <test_file>' to verify. "
        "Fix failures and retry (max 3 write+test cycles)."
    ),
    "researcher": (
        "You are a researcher. Research the given topic using WebSearch and WebFetch. "
        "Do NOT write files. Output a concise research summary."
    ),
}

TOOLS_BY_TYPE: dict[str, list[str]] = {
    "file-writer": ["Write"],
    "code-reviewer": ["Read", "Grep"],
    "test-writer": ["Read", "Write", "Bash"],
    "researcher": ["WebSearch", "WebFetch"],
}

MAX_ITERATIONS = 5


async def run_sub_agent(
    agent_type: str,
    task: str,
    llm: ChatOpenAI,
    all_tools: dict[str, BaseTool],
    max_retry: int = 3,
    verbose: bool = False,
) -> str:
    """
    Run a sub-agent with a restricted tool set and system prompt.

    Args:
        agent_type: One of "file-writer", "code-reviewer", "test-writer", "researcher".
        task: Natural language description of the sub-agent's task.
        llm: ChatOpenAI instance shared from the parent agent.
        all_tools: Dict mapping tool name to BaseTool (the full tool registry).
        max_retry: Max LLM API retries.
        verbose: Enable verbose logging.

    Returns:
        The sub-agent's final output string.
    """
    system_prompt = SYSTEM_PROMPTS.get(agent_type)
    if system_prompt is None:
        return f"Error: unknown agent_type '{agent_type}'. Valid: {list(SYSTEM_PROMPTS)}"

    tool_names = TOOLS_BY_TYPE.get(agent_type, [])
    tools = [all_tools[name] for name in tool_names if name in all_tools]
    if not tools:
        return f"Error: no tools available for agent_type '{agent_type}'"

    prompt = PromptTemplate(
        input_variables=["task"],
        template=system_prompt + "\n\n## Task\n{task}",
    )

    prompt_text = prompt.invoke({"task": task}).to_string()
    api_messages: list[dict[str, Any]] = [{"role": "user", "content": prompt_text}]
    openai_tools = [convert_to_openai_tool(t) for t in tools]
    tool_map = {t.name: t for t in tools}

    if verbose:
        _log.info("Sub-agent [%s] starting: task=%s, tools=%s", agent_type, task[:80], tool_names)

    for iteration in range(MAX_ITERATIONS):
        response = await _call_llm(llm, api_messages, openai_tools, max_retry)
        choice = response.choices[0]
        msg = choice.message

        assistant_dict: dict[str, Any] = msg.model_dump(
            mode="json", exclude_none=True, exclude_unset=True,
        )
        assistant_dict["role"] = "assistant"
        api_messages.append(assistant_dict)

        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool = tool_map.get(tc.function.name)
                args = json.loads(tc.function.arguments)
                if tool is None:
                    tool_output = f"Error: Tool '{tc.function.name}' not available to {agent_type}"
                else:
                    try:
                        tool_output_raw = await tool.ainvoke(args)
                        tool_output = str(tool_output_raw)
                    except Exception as e:
                        tool_output = f"Error: {e}"
                api_messages.append({
                    "role": "tool",
                    "content": tool_output,
                    "tool_call_id": tc.id,
                })
                if verbose:
                    _log.info("Sub-agent [%s] tool: %s → %s", agent_type, tc.function.name, tool_output[:120])
        else:
            content = msg.content or ""
            _log.info("Sub-agent [%s] completed in %d iterations", agent_type, iteration + 1)
            return content

    last_msg = api_messages[-1]
    return last_msg.get("content", "") if isinstance(last_msg, dict) else ""


async def _call_llm(
    llm: ChatOpenAI,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    max_retry: int,
) -> Any:
    """Call LLM API with exponential backoff retry."""
    last_error: Exception | None = None
    for attempt in range(max_retry + 1):
        try:
            return await llm.async_client.create(
                model=llm.model_name,
                messages=messages,
                tools=tools,
                temperature=llm.temperature,
            )
        except _RETRYABLE as e:
            last_error = e
            if attempt < max_retry:
                wait_s = 2 ** attempt
                _log.warning("Sub-agent LLM retry %d/%d: %s", attempt + 1, max_retry + 1, e)
                await asyncio.sleep(wait_s)
        except APIError as e:
            raise RuntimeError(f"Sub-agent LLM error: {e}") from e
    raise RuntimeError(f"Sub-agent LLM failed after {max_retry + 1} attempts: {last_error}")

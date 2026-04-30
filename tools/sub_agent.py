"""
SpawnSubAgent tool for creating parallel sub-agents.

Allows the main agent to fork a sub-agent for parallel file operations.
One sub-agent = one file. Used primarily in code_gen, test_gen, and review stages.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from agents.sub_agent import run_sub_agent

_log = logging.getLogger("tools.sub_agent")

# Module-level context set before each stage's agent loop runs.
# Contains: llm, config, workspace, all_tools
_BOUND_CONTEXT: dict = {}


def bind_sub_agent_context(llm, config, workspace, all_tools: dict) -> None:
    """Bind context for SpawnSubAgent tool. Call before each stage's agent invocation."""
    global _BOUND_CONTEXT
    _BOUND_CONTEXT = {
        "llm": llm,
        "config": config,
        "workspace": workspace,
        "all_tools": all_tools,
    }


@tool
async def SpawnSubAgent(
    agent_type: str,
    task: str,
    file_path: str,
    content_spec: str = "",
) -> str:
    """
    Launch a sub-agent to perform a specific task. Use this for parallel operations:
    one sub-agent per file, one sub-agent per research question.

    Args:
        agent_type: Type of sub-agent to spawn.
                    "file-writer" — create/write exactly one file.
                    "code-reviewer" — review a specific file.
                    "test-writer" — write and run tests for a specific file.
                    "researcher" — research a topic via web search.
        task: Natural language description of what the sub-agent should do.
        file_path: Absolute path of the target file (required for file-writer,
                   code-reviewer, test-writer).
        content_spec: Detailed content specification (required for file-writer).
                      Include the full code or content to write.

    Returns:
        The sub-agent's final output.
    """
    ctx = _BOUND_CONTEXT
    if not ctx:
        return "Error: SpawnSubAgent context not initialized. Contact developer."

    # For file-writer, inject the workspace path into the task
    workspace = ctx["workspace"]

    # Build the full task with workspace-aware paths
    if agent_type == "file-writer" and content_spec:
        full_task = (
            f"File: {file_path}\n"
            f"Content specification:\n{content_spec}\n\n"
            f"Working directory: {workspace}\n"
            f"Write the content to {file_path}."
        )
    elif agent_type == "code-reviewer":
        full_task = f"Review file: {file_path}\n\n{task}"
    elif agent_type == "test-writer":
        full_task = (
            f"Source file: {file_path}\n"
            f"Working directory: {workspace}\n"
            f"Task: {task}"
        )
    elif agent_type == "researcher":
        full_task = task
    else:
        return f"Error: unknown agent_type '{agent_type}'"

    _log.info("SpawnSubAgent: type=%s, file=%s", agent_type, file_path)

    try:
        result = await run_sub_agent(
            agent_type=agent_type,
            task=full_task,
            llm=ctx["llm"],
            all_tools=ctx["all_tools"],
            max_retry=ctx["config"].max_retry,
            verbose=ctx["config"].verbose,
        )
        _log.info("SpawnSubAgent [%s] done: %s", agent_type, result[:120])
        return result
    except RuntimeError as e:
        _log.error("SpawnSubAgent [%s] failed: %s", agent_type, e)
        return f"Error: sub-agent [{agent_type}] failed: {e}"

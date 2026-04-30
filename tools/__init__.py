"""
Tool registry and exports for DevFlow pipeline.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from tools.ask_user import AskUserQuestion
from tools.bash import Bash
from tools.file_ops import Edit, Read, Write
from tools.git_cmd import git_cmd_exec
from tools.glob import Glob
from tools.grep import Grep
from tools.sub_agent import SpawnSubAgent, bind_sub_agent_context
from tools.tool_search import ToolSearch
from tools.web_tools import WebFetch, WebSearch

# All available tools
__all__ = [
    "Read",
    "Edit",
    "Write",
    "Glob",
    "Grep",
    "Bash",
    "shell_exec",
    "git_cmd_exec",
    "WebSearch",
    "WebFetch",
    "ToolSearch",
    "AskUserQuestion",
    "SpawnSubAgent",
    "STAGE_TOOLS",
    "ALL_TOOLS",
    "bind_sub_agent_context",
]

# Re-export shell_exec for backward compatibility
from tools.shell_exec import shell_exec  # noqa: E402

# Common tools available to all stages
_COMMON: list[BaseTool] = [
    Read,
    Edit,
    Write,
    Glob,
    Grep,
    Bash,
    SpawnSubAgent,
    WebSearch,
    WebFetch,
    ToolSearch,
]

# Stage-specific tool sets
# AskUserQuestion: requirements only  /  git_cmd_exec: delivery only
# All other tools: available to all stages
TOOLS_REQUIREMENTS: list[BaseTool] = [AskUserQuestion, *_COMMON]
TOOLS_SOLUTION: list[BaseTool] = list(_COMMON)
TOOLS_CODE_GEN: list[BaseTool] = list(_COMMON)
TOOLS_TEST_GEN: list[BaseTool] = list(_COMMON)
TOOLS_REVIEW: list[BaseTool] = list(_COMMON)
TOOLS_DELIVERY: list[BaseTool] = [*_COMMON, git_cmd_exec]

# Stage name to tools mapping
STAGE_TOOLS: dict[str, list[BaseTool]] = {
    "requirements": TOOLS_REQUIREMENTS,
    "solution": TOOLS_SOLUTION,
    "code_gen": TOOLS_CODE_GEN,
    "test_gen": TOOLS_TEST_GEN,
    "review": TOOLS_REVIEW,
    "delivery": TOOLS_DELIVERY,
}

# Flat list of all unique tools
ALL_TOOLS: list[BaseTool] = list({
    t.name: t for stage_tools in STAGE_TOOLS.values() for t in stage_tools
}.values())

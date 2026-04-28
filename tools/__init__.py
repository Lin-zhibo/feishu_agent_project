"""
Tool registry and exports for DevFlow pipeline.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from tools.ask_user import AskUserQuestion
from tools.file_ops import Edit, Read, Write
from tools.git_cmd import git_cmd_exec
from tools.shell_exec import shell_exec
from tools.tool_search import ToolSearch
from tools.web_tools import WebFetch, WebSearch

# All available tools
__all__ = [
    "Read",
    "Edit",
    "Write",
    "shell_exec",
    "git_cmd_exec",
    "WebSearch",
    "WebFetch",
    "ToolSearch",
    "AskUserQuestion",
]

# Stage-specific tool sets
TOOLS_REQUIREMENTS: list[BaseTool] = [
    AskUserQuestion,
]

TOOLS_SOLUTION: list[BaseTool] = [
    WebSearch,
    WebFetch,
    ToolSearch,
    AskUserQuestion,
]

TOOLS_CODE_GEN: list[BaseTool] = [
    Read,
    Edit,
    Write,
    shell_exec,
    git_cmd_exec,
    AskUserQuestion,
]

TOOLS_TEST_GEN: list[BaseTool] = [
    Read,
    Edit,
    Write,
    shell_exec,
    AskUserQuestion,
]

TOOLS_REVIEW: list[BaseTool] = [
    WebSearch,
    WebFetch,
    ToolSearch,
    Read,
    shell_exec,
    AskUserQuestion,
]

TOOLS_DELIVERY: list[BaseTool] = [
    Read,
    AskUserQuestion,
]

# Stage name to tools mapping
STAGE_TOOLS: dict[str, list[BaseTool]] = {
    "requirements": TOOLS_REQUIREMENTS,
    "solution": TOOLS_SOLUTION,
    "code_gen": TOOLS_CODE_GEN,
    "test_gen": TOOLS_TEST_GEN,
    "review": TOOLS_REVIEW,
    "delivery": TOOLS_DELIVERY,
}

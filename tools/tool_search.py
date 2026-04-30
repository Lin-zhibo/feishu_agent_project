"""
Tool for searching across available DevFlow tools by name or description.

Provides a meta-tool that helps the agent find which tools are available
for a given task.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

_log = logging.getLogger("tools.tool_search")

# In-memory registry of all tools
# Each entry: {name, description, module}
_TOOL_REGISTRY: list[dict[str, str]] = [
    {"name": "Read", "description": "Read a file from the local filesystem", "module": "tools.file_ops"},
    {"name": "Edit", "description": "Perform exact string replacements in files", "module": "tools.file_ops"},
    {"name": "Write", "description": "Write a file to the local filesystem", "module": "tools.file_ops"},
    {"name": "shell_exec", "description": "Execute a shell command with user confirmation", "module": "tools.shell_exec"},
    {"name": "git_cmd_exec", "description": "Execute a git command with user confirmation", "module": "tools.git_cmd"},
    {"name": "WebSearch", "description": "Search the web for information using DuckDuckGo", "module": "tools.web_tools"},
    {"name": "WebFetch", "description": "Fetch content from a URL and convert to markdown", "module": "tools.web_tools"},
    {"name": "ToolSearch", "description": "Search for available DevFlow tools by keyword or description", "module": "tools.tool_search"},
    {"name": "AskUserQuestion", "description": "Ask the user a clarifying question and return their response", "module": "tools.ask_user"},
]


@tool
def ToolSearch(query: str) -> str:
    """
    Search for available DevFlow tools by keyword or description.

    Use this to find which tools can help with a specific task.

    Args:
        query: Keyword or description to search for.

    Returns:
        JSON string listing matching tools with their names, descriptions, and modules.
    """
    _log.info("ToolSearch called: query=%s", query)
    q = query.lower().strip()
    if not q:
        _log.info("ToolSearch: empty query, returning full registry")
        return json.dumps(_TOOL_REGISTRY, indent=2, ensure_ascii=False)

    results = [
        t for t in _TOOL_REGISTRY
        if q in t["name"].lower() or q in t["description"].lower()
    ]

    if not results:
        _log.info("ToolSearch: no results for query=%s", query)
        return json.dumps(
            [{"note": f"No tools found matching '{query}'. Try different keywords."}],
            indent=2,
        )

    _log.info("ToolSearch: query=%s, results_count=%d", query, len(results))
    return json.dumps(results, indent=2, ensure_ascii=False)

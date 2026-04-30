"""
Grep tool for regex content search across files.

Searches file contents using regular expressions, similar to ripgrep.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from langchain_core.tools import tool

_log = logging.getLogger("tools.grep")

_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".venv", "venv",
    "dist", "build", ".next", ".turbo",
})

MAX_RESULTS = 100


@tool
def Grep(pattern: str, path: str = ".", include: str | None = None) -> str:
    """
    Search file contents using a regular expression.

    Args:
        pattern: Regular expression to search for.
        path: Root directory to search in (default: ".").
        include: Optional file pattern filter (e.g., "*.py", "*.{ts,tsx}").

    Returns:
        Matches in format "file_path:line_num: content", one per line.
        Limited to 100 results.
    """
    _log.info("Grep: pattern=%s, path=%s, include=%s", pattern, path, include)

    root = Path(path).resolve()
    if not root.exists():
        return f"Error: path not found: {path}"

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: invalid regex pattern: {e}"

    results: list[str] = []
    glob_pattern = f"**/{include}" if include else "**/*"

    for file_path in root.glob(glob_pattern):
        if not file_path.is_file():
            continue
        if set(file_path.parts) & _SKIP_DIRS:
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if regex.search(line):
                        results.append(f"{file_path}:{line_num}: {line.rstrip()}")
                        if len(results) >= MAX_RESULTS:
                            break
        except (UnicodeDecodeError, PermissionError, OSError):
            continue

        if len(results) >= MAX_RESULTS:
            break

    if not results:
        return "(no matches)"

    output = "\n".join(results)
    if len(results) >= MAX_RESULTS:
        output += f"\n\n[Showing first {MAX_RESULTS} matches]"

    _log.info("Grep: returned %d results", len(results))
    return output

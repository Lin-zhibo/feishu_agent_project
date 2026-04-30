"""
Glob tool for file pattern matching.

Supports glob patterns to find files in the project directory tree.
"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.tools import tool

_log = logging.getLogger("tools.glob")

# Directories to skip during glob traversal
_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".venv", "venv",
    "dist", "build", ".next", ".turbo",
})

MAX_RESULTS = 200


@tool
def Glob(pattern: str, path: str = ".") -> str:
    """
    Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.py", "src/**/*.ts", "*.json").
        path: Root directory to search from (default: ".").

    Returns:
        Sorted list of matching file paths, one per line.
        Limited to 200 results.
    """
    _log.info("Glob: pattern=%s, path=%s", pattern, path)

    root = Path(path).resolve()
    if not root.exists():
        return f"Error: path not found: {path}"

    try:
        matches = sorted(root.glob(pattern))
    except Exception as e:
        return f"Error: invalid glob pattern: {e}"

    # Filter out directories and skipped paths
    results: list[str] = []
    for p in matches:
        if not p.is_file():
            continue
        # Skip files inside excluded directories
        parts = set(p.parts)
        if parts & _SKIP_DIRS:
            continue
        results.append(str(p))

    if len(results) > MAX_RESULTS:
        results = results[:MAX_RESULTS]
        results.append(f"\n[Showing {MAX_RESULTS} of {len(matches)} total matches]")

    output = "\n".join(results) if results else "(no matches)"
    _log.info("Glob: returned %d results", len(results))
    return output

"""
File operation tools for LLM agents using LangChain.

Provides Read, Edit, and Write operations on the local filesystem.
"""

from __future__ import annotations

import logging
import os

from langchain_core.tools import tool

_log = logging.getLogger("tools.file_ops")


@tool
def Read(file_path: str, offset: int = 1, limit: int = 2000) -> str:
    """
    Read a file with optional line range.

    Args:
        file_path: Absolute path to the file to read.
        offset: 1-indexed line number to start reading from (default: 1).
        limit: Maximum number of lines to return (default: 2000).

    Returns:
        File content with line number prefixes, or error if file not found.
        When truncated, appends a summary line with total lines.
    """
    _log.info("Read: file_path=%s, offset=%d, limit=%d", file_path, offset, limit)
    if not os.path.exists(file_path):
        _log.warning("Read: file not found: %s", file_path)
        return f"Error: file not found: {file_path}"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        _log.warning("Read: binary/encoding error for %s", file_path)
        size = os.path.getsize(file_path)
        return f"Error: cannot read {file_path} as text (binary file, {size} bytes)"

    total = len(lines)
    if offset > total:
        return f"Error: offset {offset} exceeds file line count ({total})"

    start = offset - 1
    end = min(start + limit, total)
    selected = lines[start:end]

    out_lines = []
    for i, line in enumerate(selected, start=offset):
        out_lines.append(f"{i}: {line.rstrip()}")

    result = "\n".join(out_lines)
    if end < total:
        result += f"\n\n[Showing lines {offset}-{end} of {total} total]"

    _log.info("Read: %s, returned %d lines (total=%d)", file_path, len(selected), total)
    return result


@tool
def Edit(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """
    Replace a specific section of a file with new content.

    Args:
        file_path: Absolute path to the file to edit.
        old_string: Exact text to find and replace.
        new_string: Replacement text.
        replace_all: If True, replace all occurrences (default: False, requires unique match).

    Returns:
        Confirmation message with count of replacements, or error if not found.
    """
    _log.info("Edit: file_path=%s, replace_all=%s", file_path, replace_all)
    if not os.path.exists(file_path):
        _log.warning("Edit: file not found: %s", file_path)
        return f"Error: file not found: {file_path}"

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    count = content.count(old_string)
    if count == 0:
        _log.warning("Edit: old_string not found in %s", file_path)
        return f"Error: old_string not found in {file_path}. No changes made."

    if not replace_all and count > 1:
        _log.warning("Edit: old_string appears %d times in %s", count, file_path)
        return (
            f"Error: old_string appears {count} times in {file_path}. "
            "Set replace_all=True to replace all, or make old_string more specific."
        )

    new_content = content.replace(old_string, new_string)
    replacements = count if replace_all else 1

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    _log.info("Edit: %d replacement(s) in %s", replacements, file_path)
    return f"Successfully replaced {replacements} occurrence(s) in {file_path}"


@tool
def Write(file_path: str, content: str) -> str:
    """
    Create a new file or overwrite an existing file.

    Args:
        file_path: Absolute path for the file.
        content: Full content to write.

    Returns:
        Confirmation message with file path and size.
    """
    _log.info("Write: file_path=%s, chars=%d", file_path, len(content))
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    size = os.path.getsize(file_path)
    _log.info("Write: done: %s (%d bytes)", file_path, size)
    return f"Written {size} bytes to {file_path}"

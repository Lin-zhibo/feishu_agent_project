"""
Shell execution tool for LLM agents using LangChain.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

_log = logging.getLogger("tools.shell_exec")


def _confirm_exec(cmd: str, tool_name: str) -> str | None:
    """
    Prompt user for confirmation before executing a command.

    Args:
        cmd: The command to be executed.
        tool_name: Name of the tool for display.

    Returns:
        None if user approves, otherwise a cancellation message string.
    """
    print(f"\n=== [{tool_name}] Confirmation Required ===")
    print(f"Command: {cmd}")
    resp = input("Execute? (Y/n): ").strip().lower()
    if resp in ("y", "yes", ""):
        return None
    return f"[{tool_name}] Tool execution cancelled by user."


@tool
def shell_exec(cmd: str) -> str:
    """
    Execute a shell command and return the output.

    Args:
        cmd: Shell command to execute. Avoid commands that are destructive
             or long-running. Common safe commands: pytest, ruff, python, git.

    Returns:
        stdout output if successful, or error message with stderr if failed.
    """
    _log.info("shell_exec called: cmd=%s", cmd)
    if denied := _confirm_exec(cmd, "shell_exec"):
        _log.info("shell_exec: denied by user")
        return denied

    import subprocess

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        _log.warning("shell_exec: failed with code %d: %s", result.returncode, result.stderr.strip())
        return f"Command failed with code {result.returncode}:\n{result.stderr.strip()}"

    _log.info("shell_exec: done, stdout_chars=%d", len(result.stdout.strip()))
    return result.stdout.strip()
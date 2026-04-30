"""
Bash tool for executing shell commands with safety controls.

Enhanced replacement for shell_exec with workdir, timeout, and description.
"""

from __future__ import annotations

import logging
import subprocess

from langchain_core.tools import tool

_log = logging.getLogger("tools.bash")


def _confirm(cmd: str, workdir: str) -> bool:
    """
    Prompt user for confirmation before executing a command.

    Args:
        cmd: The command to be executed.
        workdir: Working directory of the command.

    Returns:
        True if user approves, False otherwise.
    """
    print(f"\n{'='*60}")
    print("  [Bash] Confirmation Required")
    print(f"{'='*60}")
    print(f"  Workdir: {workdir}")
    print(f"  Command: {cmd}")
    print(f"{'='*60}")
    resp = input("Execute? (Y/n): ").strip().lower()
    return resp in ("y", "yes", "")


@tool
def Bash(command: str, description: str, workdir: str = ".", timeout: int = 120000) -> str:
    """
    Execute a shell command and return the output.

    Args:
        command: The shell command to execute.
        description: Brief description of what this command does (for audit).
        workdir: Working directory to run the command in (default: ".").
        timeout: Timeout in milliseconds (default: 120000, i.e. 2 minutes).

    Returns:
        stdout if successful, or error message with stderr if failed.
        Returns cancellation message if user denies confirmation.
    """
    _log.info("Bash: description='%s', workdir=%s, cmd=%s", description, workdir, command)

    if not _confirm(command, workdir):
        _log.info("Bash: denied by user")
        return "Bash execution cancelled by user."

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout / 1000.0,
            cwd=workdir,
        )
    except subprocess.TimeoutExpired:
        _log.warning("Bash: timed out after %d ms", timeout)
        return f"Error: command timed out after {timeout}ms"
    except Exception as e:
        _log.warning("Bash: execution error: %s", e)
        return f"Error: {e}"

    if result.returncode != 0:
        _log.warning("Bash: exit code %d, stderr=%s", result.returncode, result.stderr.strip())
        return f"Exit code {result.returncode}:\n{result.stderr.strip()}"

    output = result.stdout.strip()
    _log.info("Bash: done, output_chars=%d", len(output))
    return output if output else "(success, no output)"

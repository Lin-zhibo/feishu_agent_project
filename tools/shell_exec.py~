"""
Shell execution tool for LLM agents using LangChain.
"""

from langchain_core.tools import tool


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
    import subprocess

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        return f"Command failed with code {result.returncode}:\n{result.stderr.strip()}"

    return result.stdout.strip()

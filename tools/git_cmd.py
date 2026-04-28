"""
git command execution tool for LLM agents using LangChain.
"""

from langchain_core.tools import tool


@tool
def git_cmd_exec(cmd: str) -> str:
    """
    Execute git command and return the output.

    Args:
        cmd: Shell command to execute. Including git commands like `git status`, `git diff`, `git log`. Through this tool, LLM agents can interact with git repositories to create a new branch, commit changes, PR, etc.

    Returns:
        stdout output if successful, or error message with stderr if failed.
    """
    import subprocess
    
    if not cmd.startswith("git "):
        return f"{cmd} is not a valid git command."

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

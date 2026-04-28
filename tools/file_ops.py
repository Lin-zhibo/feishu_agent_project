"""
File operation tools for LLM agents using LangChain.
"""

from langchain_core.tools import tool
import os


@tool
def Read(file_path: str) -> str:
    """
    Read the complete content of a file.

    Args:
        file_path: Absolute path to the file to read.

    Returns:
        Full content of the file as string.
    """
    if not os.path.exists(file_path):
        return f"Error: file not found: {file_path}"
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


@tool
def Edit(file_path: str, old_string: str, new_string: str) -> str:
    """
    Replace a specific section of a file with new content.
    Use this when you need to change part of a file while preserving the rest.

    Args:
        file_path: Absolute path to the file to edit.
        old_string: Exact text to find and replace. Must be unique in the file.
        new_string: Replacement text.

    Returns:
        Confirmation message with change summary, or error if old_string not found.
    """
    if not os.path.exists(file_path):
        return f"Error: file not found: {file_path}"

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if old_string not in content:
        return f"Error: old_string not found in {file_path}. No changes made."

    count = content.count(old_string)
    if count > 1:
        return f"Error: old_string appears {count} times in {file_path}. Make it unique."

    new_content = content.replace(old_string, new_string, 1)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return f"Successfully replaced 1 occurrence in {file_path}"


@tool
def Write(file_path: str, content: str) -> str:
    """
    Create a new file or overwrite an existing file with content.
    WARNING: This will overwrite the entire file. Use Edit for partial changes.

    Args:
        file_path: Absolute path for the new file.
        content: Full content to write to the file.

    Returns:
        Confirmation message.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Written to {file_path}"

"""
Interactive tool for asking users clarifying questions.

Blocks synchronously on input() to collect user responses.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool


@tool
def AskUserQuestion(
    question: str,
    options: list[str] | None = None,
) -> str:
    """
    Ask the user a clarifying question and return their response.

    This tool blocks until the user provides an answer.

    Args:
        question: The question to ask the user.
        options: Optional list of valid answer options. If provided,
                  the user should choose from these options.

    Returns:
        The user's answer string.
    """
    print(f"\n{'='*60}")
    print(f"  [AskUserQuestion]")
    print(f"{'='*60}")
    print(f"  Question: {question}")
    if options:
        print(f"  Options: {', '.join(options)}")
    print(f"{'='*60}")

    while True:
        resp = input("Your answer: ").strip()
        if not resp:
            print("  Please provide an answer.")
            continue
        if options and resp not in options:
            # Accept any input even if not in options (user might type custom answer)
            print(f"  Note: '{resp}' is not in the listed options, but accepting anyway.")
        return resp

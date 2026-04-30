"""
Interactive tool for asking users clarifying questions.

Blocks synchronously on input() to collect user responses.
Supports single-select and multi-select modes.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

_log = logging.getLogger("tools.ask_user")


@tool
def AskUserQuestion(
    question: str,
    options: list[str] | None = None,
    multiselect: bool = False,
) -> str:
    """
    Ask the user a clarifying question and return their response.

    This tool blocks until the user provides an answer.
    Supports both single-select (type answer or pick from options) and
    multi-select (pick multiple from numbered options).

    Args:
        question: The question to ask the user.
        options: Optional list of valid answer options. If provided,
                  the user should choose from these options.
        multiselect: If True, the user can select multiple options.
                     Options are displayed with numbers, and the user
                     enters comma-separated numbers or option texts.

    Returns:
        The user's answer string. For multiselect, returns comma-separated
        selected option texts.
    """
    _log.info("AskUserQuestion called: question=%s, options=%s, multiselect=%s", question, options, multiselect)
    print(f"\n{'='*60}")
    print("  [AskUserQuestion]")
    print(f"{'='*60}")
    print(f"  Question: {question}")

    if multiselect and options:
        print("  (Multi-select: enter comma-separated numbers or texts, e.g. 1,3,5)")
        for i, opt in enumerate(options, 1):
            print(f"    [{i}] {opt}")
        print(f"{'='*60}")

        while True:
            resp = input("Your answer: ").strip()
            if not resp:
                print("  Please provide an answer.")
                continue

            selected = _parse_multiselect(resp, options)
            if selected:
                result = ", ".join(selected)
                _log.info("AskUserQuestion (multiselect): user responded: %s", result)
                return result
            else:
                print(f"  Cannot parse '{resp}'. Please use numbers (1-{len(options)}) or option texts, comma-separated.")

    if options:
        print(f"  Options: {', '.join(options)}")
    print(f"{'='*60}")

    while True:
        resp = input("Your answer: ").strip()
        if not resp:
            print("  Please provide an answer.")
            continue
        if options and resp not in options:
            print(f"  Note: '{resp}' is not in the listed options, but accepting anyway.")
        _log.info("AskUserQuestion: user responded: %s", resp)
        return resp


def _parse_multiselect(raw: str, options: list[str]) -> list[str]:
    """
    Parse a comma-separated user input into selected options.

    Supports both numeric indices (1-based) and exact option text matches.

    Args:
        raw: Raw user input string.
        options: List of all available options.

    Returns:
        List of selected option texts, or empty list if parsing fails.
    """
    selected: list[str] = []
    parts = [p.strip() for p in raw.replace("，", ",").split(",")]

    for part in parts:
        if not part:
            continue
        # Try numeric index
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(options):
                if options[idx] not in selected:
                    selected.append(options[idx])
                continue
        # Try exact match
        if part in options:
            if part not in selected:
                selected.append(part)
            continue
        # Try case-insensitive match
        lower_part = part.lower()
        for opt in options:
            if opt.lower() == lower_part and opt not in selected:
                selected.append(opt)
                break
        else:
            # Could not match this part — fail the whole parse
            return []

    return selected

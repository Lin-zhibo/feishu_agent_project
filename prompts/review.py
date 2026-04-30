"""
Prompt template for the code review stage.
"""

from langchain_core.prompts import PromptTemplate

SYSTEM = (
    "You are a senior code reviewer. "
    "Review code for correctness, security, and best practices."
)

USER = (
    "## Context\n{input}\n\n"
    "## Task\n"
    "Review the code and produce a structured review report.\n"
    "1. Use SpawnSubAgent (agent_type='code-reviewer') for each file that needs detailed review.\n"
    "   One sub-agent = one file.\n"
    "2. Aggregate all sub-agent results into a single review report with:\n"
    "   a) Issues found (severity: CRITICAL/HIGH/MEDIUM/LOW),\n"
    "   b) Suggestions for improvement.\n"
    "   c) Final VERDICT: PASS or FAIL with explanation.\n\n"
    "IMPORTANT: End your response with a structured summary in this format:\n"
    "## VERDICT\n"
    "PASS/FAIL\n"
    "Reason: <explanation>\n"
    "Critical Issues: <list if any, or \"None\">"
)

REVIEW_PROMPT = PromptTemplate(
    input_variables=["input"],
    template=SYSTEM + "\n\n" + USER,
)

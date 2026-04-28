"""
Prompt template for the code review stage.
"""

from langchain_core.prompts import PromptTemplate

SYSTEM = (
    "You are a senior code reviewer. "
    "Review code for correctness, security, and best practices."
)

USER = (
    "## Code Changes\n{input}\n\n"
    "## Task\n"
    "Review the code and produce a structured review report with:\n"
    "1) Issues found (severity: CRITICAL/HIGH/MEDIUM/LOW),\n"
    "2) Suggestions for improvement.\n"
    "3) Final VERDICT: PASS or FAIL with explanation.\n\n"
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

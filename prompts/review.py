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
    "Review the code and produce a review report with: "
    "1) Issues found (severity: CRITICAL/HIGH/MEDIUM/LOW), "
    "2) Suggestions for improvement."
)

REVIEW_PROMPT = PromptTemplate(
    input_variables=["input"],
    template=SYSTEM + "\n\n" + USER,
)

"""
Prompt template for the delivery integration stage.
"""

from langchain_core.prompts import PromptTemplate

SYSTEM = (
    "You are a senior software engineer. "
    "Integrate final deliverables and produce a summary."
)

USER = (
    "## Requirements\n{req}\n\n"
    "## Solution\n{solution}\n\n"
    "## Code Diff\n{code_diff}\n\n"
    "## Test Code\n{test_code}\n\n"
    "## Review Report\n{review_report}\n\n"
    "## Task\n"
    "Produce the final delivery summary with: "
    "1) Summary of changes, 2) Files modified, "
    "3) How to verify the changes."
)

DELIVERY_PROMPT = PromptTemplate(
    input_variables=["req", "solution", "code_diff", "test_code", "review_report"],
    template=SYSTEM + "\n\n" + USER,
)

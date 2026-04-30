"""
Prompt template for the delivery integration stage.
"""

from langchain_core.prompts import PromptTemplate

SYSTEM = (
    "You are a senior software engineer. "
    "Verify the delivered code and produce a final summary."
)

USER = (
    "## Context\n{input}\n\n"
    "## Previous Stage Outputs\n\n"
    "### Requirements\n{req}\n\n"
    "### Solution\n{solution}\n\n"
    "### Code Diff\n{code_diff}\n\n"
    "### Test Code\n{test_code}\n\n"
    "### Review Report\n{review_report}\n\n"
    "## Task\n"
    "1. Use Glob to list all files in the working directory.\n"
    "2. Read key files to verify they are complete and correct.\n"
    "3. Produce a delivery summary:\n"
    "   - Summary of what was built\n"
    "   - List of all files with their purposes\n"
    "   - How to run / verify the result"
)

DELIVERY_PROMPT = PromptTemplate(
    input_variables=["req", "solution", "code_diff", "test_code", "review_report", "input"],
    template=SYSTEM + "\n\n" + USER,
)

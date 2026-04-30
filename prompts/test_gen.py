"""
Prompt template for the test generation stage.
"""

from langchain_core.prompts import PromptTemplate

SYSTEM = (
    "You are a senior QA engineer. "
    "Generate unit and integration tests based on code changes."
)

USER = (
    "## Context\n{input}\n\n"
    "## Task\n"
    "Generate pytest unit tests and integration tests covering the code changes."
)

TEST_GEN_PROMPT = PromptTemplate(
    input_variables=["input"],
    template=SYSTEM + "\n\n" + USER,
)

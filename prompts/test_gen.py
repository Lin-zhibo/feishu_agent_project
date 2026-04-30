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
    "Generate tests covering the code changes.\n"
    "1. Use SpawnSubAgent (agent_type='test-writer') for each test file.\n"
    "   One sub-agent = one test file.\n"
    "2. Each test-writer sub-agent will: read the source → write tests → run pytest → fix → verify.\n"
    "3. After all sub-agents complete, output a summary with test results.\n\n"
    "IMPORTANT: Use SpawnSubAgent for parallel test creation and execution."
)

TEST_GEN_PROMPT = PromptTemplate(
    input_variables=["input"],
    template=SYSTEM + "\n\n" + USER,
)

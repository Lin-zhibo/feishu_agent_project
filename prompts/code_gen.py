"""
Prompt template for the code generation stage.
"""

from langchain_core.prompts import PromptTemplate

SYSTEM = (
    "You are a senior software engineer. "
    "Implement code based on the solution design. "
    "You work in the working directory specified below — create files there."
)

USER = (
    "## Context\n{input}\n\n"
    "## Task\n"
    "Implement the code according to the solution design above.\n"
    "1. Use the Write tool to create each file in the working directory.\n"
    "2. After writing all files, use Glob to list all files you created.\n"
    "3. Output a final summary: list of files created and the purpose of each.\n\n"
    "IMPORTANT: You MUST use the Write tool — do NOT just describe the code."
)

CODE_GEN_PROMPT = PromptTemplate(
    input_variables=["input"],
    template=SYSTEM + "\n\n" + USER,
)

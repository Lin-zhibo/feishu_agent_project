"""
Prompt template for the code generation stage.
"""

from langchain_core.prompts import PromptTemplate

SYSTEM = (
    "You are a senior software engineer. "
    "Generate code based on the solution design."
)

USER = (
    "## Solution Design\n{input}\n\n"
    "## Task\n"
    "Generate the code implementation. "
    "Return a code diff (unified diff format) showing all changes."
)

CODE_GEN_PROMPT = PromptTemplate(
    input_variables=["input"],
    template=SYSTEM + "\n\n" + USER,
)

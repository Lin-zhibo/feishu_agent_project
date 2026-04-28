"""
Prompt template for the solution design stage.
"""

from langchain_core.prompts import PromptTemplate

SYSTEM = (
    "You are a senior software architect. "
    "Design a technical solution based on the requirements."
)

USER = (
    "## Requirements\n{input}\n\n"
    "## Task\n"
    "Design a technical solution including: "
    "1) Architecture overview, 2) File structure, "
    "3) API design (if applicable), 4) Key implementation notes."
)

SOLUTION_PROMPT = PromptTemplate(
    input_variables=["input"],
    template=SYSTEM + "\n\n" + USER,
)

"""
Prompt template for the requirements analysis stage.
"""

from langchain_core.prompts import PromptTemplate

SYSTEM = (
    "You are a senior software requirements analyst. "
    "Analyze the user's request and produce a structured requirements document."
)

USER = (
    "## User Request\n{input}\n\n"
    "## Task\n"
    "Analyze the request above and produce a structured requirements document "
    "with: 1) Functional requirements, 2) Non-functional requirements, "
    "3) Acceptance criteria."
)

REQUIREMENTS_PROMPT = PromptTemplate(
    input_variables=["input"],
    template=SYSTEM + "\n\n" + USER,
)

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
    "3) Acceptance criteria.\n\n"
    "## CRITICAL RULES (Strict)\n"
    "1. Do NOT make any assumptions. If any information is missing, unclear, or unspecified → you MUST call AskUserQuestion FIRST before producing any document.\n"
    "2. You MUST use the AskUserQuestion tool (available via bind_tools) for ANY clarification needed — NEVER produce a document with guessed information.\n"
    "3. After ALL questions are answered, output ONLY the final structured requirements document. No preamble, no questions, no dialogue. Start directly with the document."
)

REQUIREMENTS_PROMPT = PromptTemplate(
    input_variables=["input"],
    template=SYSTEM + "\n\n" + USER,
)

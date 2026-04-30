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
    "1. Use SpawnSubAgent (agent_type='file-writer') for EACH file to create.\n"
    "   One sub-agent = one file. Launch them all, then wait for results.\n"
    "2. For a single file only, you may use Write tool directly.\n"
    "3. After all sub-agents complete, use Glob to list all created files.\n"
    "4. Output a final summary: list of files created and the purpose of each.\n\n"
    "IMPORTANT: Use SpawnSubAgent for parallel file creation. "
    "Do NOT just describe the code — you MUST create actual files."
)

CODE_GEN_PROMPT = PromptTemplate(
    input_variables=["input"],
    template=SYSTEM + "\n\n" + USER,
)

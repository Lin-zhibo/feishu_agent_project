"""
Prompt templates for each stage of the DevFlow Engine pipeline.

Structure:
    STAGE_TEMPLATES: Dict mapping stage names to their prompt templates.
    Each template is a dict with keys:
        - system: System prompt for the agent
        - user: User prompt template (supports {input} placeholder)
"""

STAGE_TEMPLATES: dict[str, dict[str, str]] = {
    "requirements": {
        "system": (
            "You are a senior software requirements analyst. "
            "Analyze the user's request and produce a structured requirements document."
        ),
        "user": (
            "## User Request\n{input}\n\n"
            "## Task\nAnalyze the request above and produce a structured requirements document "
            "with: 1) Functional requirements, 2) Non-functional requirements, "
            "3) Acceptance criteria."
        ),
    },
    "solution": {
        "system": (
            "You are a senior software architect. "
            "Design a technical solution based on the requirements."
        ),
        "user": (
            "## Requirements\n{input}\n\n"
            "## Task\nDesign a technical solution including: "
            "1) Architecture overview, 2) File structure, "
            "3) API design (if applicable), 4) Key implementation notes."
        ),
    },
    "code_gen": {
        "system": (
            "You are a senior software engineer. "
            "Generate code based on the solution design."
        ),
        "user": (
            "## Solution Design\n{input}\n\n"
            "## Task\nGenerate the code implementation. "
            "Return a code diff (unified diff format) showing all changes."
        ),
    },
    "test_gen": {
        "system": (
            "You are a senior QA engineer. "
            "Generate unit and integration tests based on code changes."
        ),
        "user": (
            "## Code Changes\n{input}\n\n"
            "## Task\nGenerate pytest unit tests and integration tests covering the code changes."
        ),
    },
    "review": {
        "system": (
            "You are a senior code reviewer. "
            "Review code for correctness, security, and best practices."
        ),
        "user": (
            "## Code Changes\n{input}\n\n"
            "## Task\nReview the code and produce a review report with: "
            "1) Issues found (severity: CRITICAL/HIGH/MEDIUM/LOW), "
            "2) Suggestions for improvement."
        ),
    },
    "delivery": {
        "system": (
            "You are a senior software engineer. "
            "Integrate final deliverables and produce a summary."
        ),
        "user": (
            "## Requirements\n{req}\n\n"
            "## Solution\n{solution}\n\n"
            "## Code Diff\n{code_diff}\n\n"
            "## Test Code\n{test_code}\n\n"
            "## Review Report\n{review_report}\n\n"
            "## Task\nProduce the final delivery summary with: "
            "1) Summary of changes, 2) Files modified, "
            "3) How to verify the changes."
        ),
    },
}

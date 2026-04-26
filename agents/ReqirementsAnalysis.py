"""
Requirements Analysis Agent.

Produces a structured requirements document from a natural language request.
"""

from __future__ import annotations

from pipeline.models import StageInput, StageOutput


async def run(inp: StageInput) -> StageOutput:
    """
    Run the requirements analysis stage.

    Args:
        inp: StageInput containing:
            - current_input: The user's raw requirement string.
            - config: Global pipeline configuration.
            - previous_output: None (this is the first stage).

    Returns:
        StageOutput with content containing the structured requirements document.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=inp.config.api_key, base_url=inp.config.base_url)

    from prompt.template import STAGE_TEMPLATES

    template = STAGE_TEMPLATES["requirements"]

    response = await client.chat.completions.create(
        model=inp.config.model_name,
        messages=[
            {"role": "system", "content": template["system"]},
            {"role": "user", "content": template["user"].format(input=inp.current_input)},
        ],
        temperature=0.3,
    )

    content = response.choices[0].message.content or ""

    return StageOutput(
        stage_name="requirements",
        content=content,
        artifacts={"requirements_doc": content},
        next_input={"input": content},
    )

"""
Solution Design Agent.

Produces a technical solution design from requirements.
"""

from __future__ import annotations

from pipeline.models import StageInput, StageOutput


async def run(inp: StageInput) -> StageOutput:
    """
    Run the solution design stage.

    Args:
        inp: StageInput containing:
            - current_input: Output from requirements stage.
            - config: Global pipeline configuration.
            - previous_output: Output dict from requirements stage.

    Returns:
        StageOutput with content containing the technical solution design.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=inp.config.api_key, base_url=inp.config.base_url)

    from prompt.template import STAGE_TEMPLATES

    template = STAGE_TEMPLATES["solution"]

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
        stage_name="solution",
        content=content,
        artifacts={"solution_doc": content},
        next_input={"input": content},
    )

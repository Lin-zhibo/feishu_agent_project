"""
Code Generation Agent.

Generates code based on the solution design.
"""

from __future__ import annotations

from pipeline.models import StageInput, StageOutput


async def run(inp: StageInput) -> StageOutput:
    """
    Run the code generation stage.

    Args:
        inp: StageInput containing:
            - current_input: Output from solution stage.
            - config: Global pipeline configuration.
            - previous_output: Output dict from solution stage.

    Returns:
        StageOutput with content containing the code diff.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=inp.config.api_key, base_url=inp.config.base_url)

    from prompt.template import STAGE_TEMPLATES

    template = STAGE_TEMPLATES["code_gen"]

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
        stage_name="code_gen",
        content=content,
        artifacts={"code_diff": content},
        next_input={"input": content},
    )

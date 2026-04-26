"""
Code Review Agent.

Reviews code for correctness, security, and best practices.
"""

from __future__ import annotations

from pipeline.models import StageInput, StageOutput


async def run(inp: StageInput) -> StageOutput:
    """
    Run the code review stage.

    Args:
        inp: StageInput containing:
            - current_input: Output from code_gen stage (code diff).
            - config: Global pipeline configuration.
            - previous_output: Output dict from code_gen stage.

    Returns:
        StageOutput with content containing the review report.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=inp.config.api_key, base_url=inp.config.base_url)

    from prompt.template import STAGE_TEMPLATES

    template = STAGE_TEMPLATES["review"]

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
        stage_name="review",
        content=content,
        artifacts={"review_report": content},
        next_input={"input": content},
    )

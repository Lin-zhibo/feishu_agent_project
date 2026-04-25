"""
Delivery Integration Agent.

Produces the final delivery summary integrating all stage outputs.
"""

from __future__ import annotations

from pipeline.models import StageInput, StageOutput


async def run(inp: StageInput) -> StageOutput:
    """
    Run the delivery integration stage.

    Args:
        inp: StageInput containing:
            - current_input: Ignored, uses previous_output fields instead.
            - config: Global pipeline configuration.
            - previous_output: Dict containing all previous stage outputs.

    Returns:
        StageOutput with content containing the final delivery summary.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=inp.config.api_key, base_url=inp.config.base_url)

    from prompt.template import STAGE_TEMPLATES

    template = STAGE_TEMPLATES["delivery"]

    prev = inp.previous_output or {}

    response = await client.chat.completions.create(
        model=inp.config.model_name,
        messages=[
            {"role": "system", "content": template["system"]},
            {
                "role": "user",
                "content": template["user"].format(
                    req=prev.get("requirements", ""),
                    solution=prev.get("solution", ""),
                    code_diff=prev.get("code_diff", ""),
                    test_code=prev.get("test_code", ""),
                    review_report=prev.get("review_report", ""),
                ),
            },
        ],
        temperature=0.3,
    )

    content = response.choices[0].message.content or ""

    return StageOutput(
        stage_name="delivery",
        content=content,
        artifacts={"delivery_summary": content},
        next_input={},
    )

"""
Solution design LLMChain.
"""

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from pipeline.models import PipelineConfig
from prompts import SOLUTION_PROMPT
from tools import STAGE_TOOLS


def create_solution_chain(config: PipelineConfig) -> RunnableSequence:
    """
    Create a RunnableSequence for the solution design stage.

    Args:
        config: Global pipeline configuration.

    Returns:
        RunnableSequence equivalent to LLMChain with output_key="solution".
    """
    llm = ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0.3,
    )
    return SOLUTION_PROMPT | llm.bind_tools(STAGE_TOOLS["solution"])

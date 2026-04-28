"""
Requirements analysis LLMChain.
"""

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from pipeline.models import PipelineConfig
from prompts import REQUIREMENTS_PROMPT


def create_requirements_chain(config: PipelineConfig) -> RunnableSequence:
    """
    Create a RunnableSequence for the requirements analysis stage.

    Args:
        config: Global pipeline configuration.

    Returns:
        RunnableSequence equivalent to LLMChain with output_key="requirements".
    """
    llm = ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0.3,
    )
    return REQUIREMENTS_PROMPT | llm

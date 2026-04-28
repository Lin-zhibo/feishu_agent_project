"""
Test generation LLMChain.
"""

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from pipeline.models import PipelineConfig
from prompts import TEST_GEN_PROMPT
from tools import STAGE_TOOLS


def create_test_gen_chain(config: PipelineConfig) -> RunnableSequence:
    """
    Create a RunnableSequence for the test generation stage.

    Args:
        config: Global pipeline configuration.

    Returns:
        RunnableSequence equivalent to LLMChain with output_key="test_code".
    """
    llm = ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0.3,
    )
    return TEST_GEN_PROMPT | llm.bind_tools(STAGE_TOOLS["test_gen"])

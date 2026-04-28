"""
Code generation LLMChain.
"""

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from pipeline.models import PipelineConfig
from prompts import CODE_GEN_PROMPT
from tools import STAGE_TOOLS


def create_code_gen_chain(config: PipelineConfig) -> RunnableSequence:
    """
    Create a RunnableSequence for the code generation stage.

    Args:
        config: Global pipeline configuration.

    Returns:
        RunnableSequence equivalent to LLMChain with output_key="code_diff".
    """
    llm = ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0.3,
    )
    return CODE_GEN_PROMPT | llm.bind_tools(STAGE_TOOLS["code_gen"])

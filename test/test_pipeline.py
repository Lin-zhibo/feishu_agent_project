"""
Smoke tests for the DevFlow Engine pipeline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pipeline.models import PipelineConfig, PipelineState, StageInput, StageOutput


@pytest.fixture
def mock_config() -> PipelineConfig:
    return PipelineConfig(
        model_name="deepseek-v4-flash",
        api_key="test-api-key",
        base_url="https://api.deepseek.com",
        output_dir="out",
    )


class TestPipelineModels:
    def test_stage_input_creation(self) -> None:
        config = PipelineConfig(
            model_name="deepseek-v4-flash",
            api_key="test",
            base_url="https://api.deepseek.com",
        )
        inp = StageInput(
            stage_name="requirements",
            previous_output=None,
            current_input="user login feature",
            config=config,
        )
        assert inp.stage_name == "requirements"
        assert inp.current_input == "user login feature"

    def test_stage_output_creation(self) -> None:
        out = StageOutput(
            stage_name="requirements",
            content="# Requirements",
            artifacts={"requirements_doc": "# Requirements"},
            next_input={"input": "# Requirements"},
        )
        assert out.stage_name == "requirements"
        assert "# Requirements" in out.content

    def test_pipeline_state_creation(self) -> None:
        state = PipelineState(original_input="user login feature")
        assert state.original_input == "user login feature"
        assert state.requirements is None
        assert state.solution is None


class TestPipelineConfig:
    def test_default_stage_enabled(self) -> None:
        config = PipelineConfig(
            model_name="deepseek-v4-flash",
            api_key="test",
            base_url="https://api.deepseek.com",
        )
        assert config.stage_enabled["requirements"] is True
        assert config.stage_enabled["solution"] is True
        assert config.stage_enabled["code_gen"] is True
        assert config.stage_enabled["test_gen"] is True
        assert config.stage_enabled["review"] is True
        assert config.stage_enabled["delivery"] is True

    def test_custom_output_dir(self) -> None:
        config = PipelineConfig(
            model_name="deepseek-v4-flash",
            api_key="test",
            base_url="https://api.deepseek.com",
            output_dir="custom_out",
        )
        assert config.output_dir == "custom_out"


class TestAgentsMocked:
    @pytest.mark.asyncio
    async def test_requirements_agent_mocked(self, mock_config: PipelineConfig) -> None:
        from agents import run_requirements
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.content = "# Requirements Doc"

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        with patch("agents.create_requirements_chain", return_value=mock_chain):
            inp = StageInput(
                stage_name="requirements",
                previous_output=None,
                current_input="user login",
                config=mock_config,
            )
            out = await run_requirements(inp)

            assert out.stage_name == "requirements"
            assert "# Requirements Doc" in out.content
            assert "requirements_doc" in out.artifacts

    @pytest.mark.asyncio
    async def test_solution_agent_mocked(self, mock_config: PipelineConfig) -> None:
        from agents import run_solution
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.content = "## Technical Solution"

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        with patch("agents.create_solution_chain", return_value=mock_chain):
            inp = StageInput(
                stage_name="solution",
                previous_output={"requirements": "# Requirements"},
                current_input="# Requirements",
                config=mock_config,
            )
            out = await run_solution(inp)

            assert out.stage_name == "solution"
            assert "## Technical Solution" in out.content

    @pytest.mark.asyncio
    async def test_code_gen_agent_mocked(self, mock_config: PipelineConfig) -> None:
        from agents import run_code_gen
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.content = "+ def login():"

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        with patch("agents.create_code_gen_chain", return_value=mock_chain):
            inp = StageInput(
                stage_name="code_gen",
                previous_output={"solution": "## Solution"},
                current_input="## Solution",
                config=mock_config,
            )
            out = await run_code_gen(inp)

            assert out.stage_name == "code_gen"
            assert "+ def login():" in out.content

    @pytest.mark.asyncio
    async def test_test_gen_agent_mocked(self, mock_config: PipelineConfig) -> None:
        from agents import run_test_gen
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.content = "def test_login():"

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        with patch("agents.create_test_gen_chain", return_value=mock_chain):
            inp = StageInput(
                stage_name="test_gen",
                previous_output={"code_diff": "+ def login(): pass"},
                current_input="+ def login(): pass",
                config=mock_config,
            )
            out = await run_test_gen(inp)

            assert out.stage_name == "test_gen"
            assert "def test_login():" in out.content

    @pytest.mark.asyncio
    async def test_review_agent_mocked(self, mock_config: PipelineConfig) -> None:
        from agents import run_review
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.content = "## Code Review\n- OK"

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        with patch("agents.create_review_chain", return_value=mock_chain):
            inp = StageInput(
                stage_name="review",
                previous_output={"code_diff": "+ def login(): pass"},
                current_input="+ def login(): pass",
                config=mock_config,
            )
            out = await run_review(inp)

            assert out.stage_name == "review"
            assert "## Code Review" in out.content

    @pytest.mark.asyncio
    async def test_delivery_agent_mocked(self, mock_config: PipelineConfig) -> None:
        from agents import run_delivery
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.content = "## Delivery Summary"

        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)

        with patch("agents.create_delivery_chain", return_value=mock_chain):
            inp = StageInput(
                stage_name="delivery",
                previous_output={
                    "requirements": "# Req",
                    "solution": "## Sol",
                    "code_diff": "+ code",
                    "test_code": "def test",
                    "review_report": "## Review",
                },
                current_input="",
                config=mock_config,
            )
            out = await run_delivery(inp)

            assert out.stage_name == "delivery"
            assert "## Delivery Summary" in out.content


class TestChainsModule:
    def test_requirements_chain_creation(self, mock_config: PipelineConfig) -> None:
        from chains import create_requirements_chain

        chain = create_requirements_chain(mock_config)
        assert hasattr(chain, "invoke")
        assert hasattr(chain, "ainvoke")

    def test_solution_chain_creation(self, mock_config: PipelineConfig) -> None:
        from chains import create_solution_chain

        chain = create_solution_chain(mock_config)
        assert hasattr(chain, "invoke")
        assert hasattr(chain, "ainvoke")

    def test_code_gen_chain_creation(self, mock_config: PipelineConfig) -> None:
        from chains import create_code_gen_chain

        chain = create_code_gen_chain(mock_config)
        assert hasattr(chain, "invoke")
        assert hasattr(chain, "ainvoke")

    def test_test_gen_chain_creation(self, mock_config: PipelineConfig) -> None:
        from chains import create_test_gen_chain

        chain = create_test_gen_chain(mock_config)
        assert hasattr(chain, "invoke")
        assert hasattr(chain, "ainvoke")

    def test_review_chain_creation(self, mock_config: PipelineConfig) -> None:
        from chains import create_review_chain

        chain = create_review_chain(mock_config)
        assert hasattr(chain, "invoke")
        assert hasattr(chain, "ainvoke")

    def test_delivery_chain_creation(self, mock_config: PipelineConfig) -> None:
        from chains import create_delivery_chain

        chain = create_delivery_chain(mock_config)
        assert hasattr(chain, "invoke")
        assert hasattr(chain, "ainvoke")


class TestPromptsModule:
    def test_requirements_prompt_variables(self) -> None:
        from prompts import REQUIREMENTS_PROMPT

        assert "input" in REQUIREMENTS_PROMPT.input_variables

    def test_delivery_prompt_variables(self) -> None:
        from prompts import DELIVERY_PROMPT

        assert set(DELIVERY_PROMPT.input_variables) == {
            "req",
            "solution",
            "code_diff",
            "test_code",
            "review_report",
        }

"""
PipelineCallbackHandler for real-time visualization of LLM call metrics.

Logs per-stage latency, token consumption, and cumulative totals after each ainvoke().
"""

from __future__ import annotations

import time
import logging
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

_log = logging.getLogger("pipeline.callbacks")


class PipelineCallbackHandler(BaseCallbackHandler):
    """
    Callback handler that logs LLM call metadata after each ainvoke.

    Logs:
    - Stage name
    - Elapsed time (ms)
    - Token consumption (prompt/completion/total)
    - Cumulative totals across all stages
    - Success/failure status

    Class-level accumulators track totals across all stages within a pipeline run.
    """

    total_time_ms: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0

    def __init__(self) -> None:
        super().__init__()
        self.stage_name: str | None = None
        self._start_time: float | None = None

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        messages: list[Any],
        **kwargs: Any,
    ) -> None:
        """Record the start time when an LLM call begins."""
        self._start_time = time.perf_counter()

    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any,
    ) -> None:
        """Calculate elapsed time, extract token usage, update totals, and log the block."""
        if self._start_time is None:
            return

        elapsed_ms = (time.perf_counter() - self._start_time) * 1000
        self._start_time = None

        # Extract token usage — check LangChain normalized metadata first, then raw API response
        usage: dict[str, Any] | None = None

        # First, try to get from LLMResult.llm_output (raw provider response)
        if hasattr(response, "llm_output") and response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            if token_usage:
                usage = token_usage

        # Then, try to get from AIMessage inside generations (LangChain normalized)
        if not usage and hasattr(response, "generations") and response.generations:
            gen = response.generations[0][0]
            msg = getattr(gen, "message", None) or getattr(gen, "text", None)
            if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                usage = msg.usage_metadata

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        if usage:
            prompt_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
            completion_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))
            total_tokens = usage.get("total_tokens", 0)

        # Update class-level accumulators
        PipelineCallbackHandler.total_time_ms += elapsed_ms
        PipelineCallbackHandler.total_prompt_tokens += prompt_tokens
        PipelineCallbackHandler.total_completion_tokens += completion_tokens
        PipelineCallbackHandler.total_tokens += total_tokens

        # Extract model name
        model_name = ""
        if hasattr(response, "response_metadata") and response.response_metadata:
            model_name = response.response_metadata.get("model", "")

        # Determine status
        status = "SUCCESS"
        error_line = ""
        if hasattr(response, "error") and response.error:
            status = "FAILED"
            error_line = f"│ Error:  {response.error!s}"

        # Build the visual block
        stage_label = self.stage_name or "unknown"
        width = 60
        top_bottom = "═" * (width + 2)
        stage_bar = f"─ Stage: {stage_label} ─".ljust(width, "─")

        lines = [
            f"┌{stage_bar} [{status}] ─┐",
            f"│ Time:   {elapsed_ms:>12,.0f} ms",
            f"│ Tokens: prompt={prompt_tokens:>6,} | completion={completion_tokens:>6,} | total={total_tokens:>6,}",
            f"│ Model:  {model_name}",
            f"│ Cumulative: time={PipelineCallbackHandler.total_time_ms:,.0f}ms | tokens={PipelineCallbackHandler.total_tokens:,}",
        ]

        if error_line:
            lines.append(error_line)

        lines.append(f"└{'─' * (width + 2)}┘")

        block = "\n".join(lines)
        _log.info("\n%s\n", block)

    @classmethod
    def reset_totals(cls) -> None:
        """Reset class-level accumulators. Call before starting a new pipeline run."""
        cls.total_time_ms = 0.0
        cls.total_prompt_tokens = 0
        cls.total_completion_tokens = 0
        cls.total_tokens = 0

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Log when a tool is called."""
        tool_name = serialized.get("name", "unknown") if serialized else "unknown"
        _log.info(f"\n🔧 [TOOL CALL] {tool_name}")

    def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        """Log when a tool finishes."""
        # Truncate long outputs for logging
        output_preview = output[:200] + "..." if len(output) > 200 else output
        _log.info(f"🔧 [TOOL RESULT] {output_preview}")

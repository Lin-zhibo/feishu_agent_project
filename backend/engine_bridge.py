"""
Bridge between FastAPI and the pipeline engine.

Wraps config loading and engine.run() invocation for API mode.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pipeline.config_loader import load_settings, resolve_model_config
from pipeline.models import PipelineConfig

_log = logging.getLogger("backend.engine_bridge")


def load_config(settings_path: str = "config/settings.json") -> PipelineConfig:
    """Load and resolve pipeline configuration for API mode."""
    config_path = Path(settings_path)
    if not config_path.exists():
        _log.error("Config file not found: %s", config_path)
        raise FileNotFoundError(f"Config not found: {config_path}")

    config = load_settings(config_path)
    config = resolve_model_config(config)

    if not config.api_key:
        raise ValueError("API key not set. Check config/model.json or DEEPSEEK_API_KEY env var.")

    return config

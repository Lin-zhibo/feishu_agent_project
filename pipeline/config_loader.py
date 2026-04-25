"""
Configuration loader for the DevFlow Engine pipeline.

Loads pipeline configuration from JSON files.
Priority: env var > model.json > defaults
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pipeline.models import PipelineConfig


def load_settings(settings_path: str | Path) -> PipelineConfig:
    """
    Load pipeline settings from settings.json (output_dir, stage_enabled).
    Model config is loaded separately by resolve_model_config().

    Args:
        settings_path: Path to the settings.json file.

    Returns:
        PipelineConfig instance (model fields set to defaults, use resolve_model_config to fill).
    """
    with open(settings_path, encoding="utf-8") as f:
        raw = json.load(f)

    return PipelineConfig(
        model_name="deepseek-v4-flash",
        api_key="",
        base_url="https://api.deepseek.com",
        output_dir=raw.get("output_dir", "out"),
        stage_enabled=raw.get(
            "stage_enabled",
            {
                "requirements": True,
                "solution": True,
                "code_gen": True,
                "test_gen": True,
                "review": True,
                "delivery": True,
            },
        ),
    )


def resolve_model_config(config: PipelineConfig) -> PipelineConfig:
    """
    Resolve LLM model configuration.

    Priority:
        1. Environment variable DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL
        2. config/model.json (if api_key not set in env or config)
        3. Defaults

    Args:
        config: PipelineConfig with defaults or settings.json values.

    Returns:
        PipelineConfig with resolved model fields.
    """
    # 1. Environment variables take highest priority
    if api_key := os.environ.get("DEEPSEEK_API_KEY", ""):
        config.api_key = api_key
    if base_url := os.environ.get("DEEPSEEK_BASE_URL", ""):
        config.base_url = base_url
    if model := os.environ.get("DEEPSEEK_MODEL", ""):
        config.model_name = model

    if config.api_key:
        return config

    # 2. Fall back to config/model.json
    model_json_path = Path(__file__).parent.parent / "config" / "model.json"
    if model_json_path.exists():
        with open(model_json_path, encoding="utf-8") as f:
            model_data = json.load(f)
        if api_key := model_data.get("API_KEY", ""):
            config.api_key = api_key
        if base_url := model_data.get("BASE_URL", ""):
            config.base_url = base_url
        if model := model_data.get("MODEL", ""):
            config.model_name = model

    return config

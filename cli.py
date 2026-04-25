"""
CLI entry point for the DevFlow Engine pipeline.

Usage:
    python cli.py --input "用户登录功能"
    python cli.py --input "用户登录功能" --skip-review
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from main import run_pipeline


def setup_logging() -> None:
    """
    Configure logging to write to log/log.log.

    Logs both to console (INFO) and to file (DEBUG).
    """
    log_path = Path("log")
    log_path.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path / "log.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="DevFlow Engine CLI")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="The user requirement in natural language",
    )
    parser.add_argument(
        "--skip-requirements",
        action="store_true",
        help="Skip requirements analysis stage",
    )
    parser.add_argument(
        "--skip-solution",
        action="store_true",
        help="Skip solution design stage",
    )
    parser.add_argument(
        "--skip-code-gen",
        action="store_true",
        help="Skip code generation stage",
    )
    parser.add_argument(
        "--skip-test-gen",
        action="store_true",
        help="Skip test generation stage",
    )
    parser.add_argument(
        "--skip-review",
        action="store_true",
        help="Skip code review stage",
    )
    parser.add_argument(
        "--skip-delivery",
        action="store_true",
        help="Skip delivery integration stage",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/settings.json",
        help="Path to settings.json",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="out",
        help="Output directory for artifacts",
    )

    args = parser.parse_args()

    setup_logging()
    asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> None:
    from pipeline.config_loader import load_settings, resolve_model_config

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = load_settings(config_path)
    config = resolve_model_config(config)
    config.output_dir = args.output_dir

    if args.skip_requirements:
        config.stage_enabled["requirements"] = False
    if args.skip_solution:
        config.stage_enabled["solution"] = False
    if args.skip_code_gen:
        config.stage_enabled["code_gen"] = False
    if args.skip_test_gen:
        config.stage_enabled["test_gen"] = False
    if args.skip_review:
        config.stage_enabled["review"] = False
    if args.skip_delivery:
        config.stage_enabled["delivery"] = False

    if not config.api_key:
        print(
            "Error: API key not set. "
            "Set it in config/settings.json or DEEPSEEK_API_KEY env var.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Running pipeline with input: {args.input}")
    print(f"Output directory: {config.output_dir}")

    state = await run_pipeline(args.input, config)

    print("\n=== Pipeline Complete ===")
    if state.final_output:
        print(state.final_output)
    else:
        print("No final output produced.")


if __name__ == "__main__":
    main()

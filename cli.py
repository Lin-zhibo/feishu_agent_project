"""
CLI entry point for the DevFlow Engine pipeline.

Usage:
    python cli.py --input "用户登录功能"
    python cli.py --resume
    python cli.py --resume 20260501_143022
    python cli.py --list
    python cli.py --terminate 20260501_143022
    python cli.py --terminate-all
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from main import (
    list_paused_pipelines,
    resume_pipeline,
    run_pipeline,
    terminate_all,
    terminate_pipeline,
)


def setup_logging() -> None:
    """Configure logging to write to log/log.log."""
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
        help="The user requirement in natural language",
    )
    parser.add_argument(
        "--resume",
        nargs="?",
        const="__latest__",
        type=str,
        help="Resume a paused pipeline (optional: pipeline ID)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all paused pipelines",
    )
    parser.add_argument(
        "--terminate",
        type=str,
        metavar="PIPELINE_ID",
        help="Terminate (delete) a paused pipeline",
    )
    parser.add_argument(
        "--terminate-all",
        action="store_true",
        help="Terminate (delete) all paused pipelines",
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
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip all checkpoints (auto-approve)",
    )

    args = parser.parse_args()

    setup_logging()

    from pipeline.config_loader import load_settings, resolve_model_config

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = load_settings(config_path)
    config = resolve_model_config(config)
    config.output_dir = args.output_dir

    # --- Subcommand: list ---
    if args.list:
        paused = list_paused_pipelines(config.output_dir)
        if not paused:
            print("No paused pipelines found.")
        else:
            print(f"\n{'ID':<20} {'Paused At':<22} {'Input':<40} {'Reason'}")
            print("-" * 100)
            for p in paused:
                print(
                    f"{p['pipeline_id']:<20} {p['paused_at']:<22} "
                    f"{p['original_input']:<40} {p['pause_reason']}"
                )
            print()
        return

    # --- Subcommand: terminate ---
    if args.terminate:
        if terminate_pipeline(config.output_dir, args.terminate):
            print(f"Terminated: {args.terminate}")
        else:
            print(f"Not found: {args.terminate}")
        return

    # --- Subcommand: terminate-all ---
    if args.terminate_all:
        count = terminate_all(config.output_dir)
        print(f"Terminated {count} paused pipeline(s).")
        return

    # --- Subcommand: resume ---
    if args.resume is not None:
        pipeline_id = args.resume
        if pipeline_id == "__latest__":
            paused = list_paused_pipelines(config.output_dir)
            if not paused:
                print("No paused pipelines found to resume.", file=sys.stderr)
                sys.exit(1)
            pipeline_id = paused[0]["pipeline_id"]
        if not config.api_key:
            print(
                "Error: API key not set. "
                "Set it in config/model.json or DEEPSEEK_API_KEY env var.",
                file=sys.stderr,
            )
            sys.exit(1)
        asyncio.run(_run_resume(pipeline_id, config))
        return

    # --- Subcommand: run (default, requires --input) ---
    if not args.input:
        parser.error("--input is required (or use --resume / --list / --terminate)")
        return

    config.skip_checkpoints = args.yes

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
            "Set it in config/model.json or DEEPSEEK_API_KEY env var.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Running pipeline with input: {args.input}")
    print(f"Output directory: {config.output_dir}")

    asyncio.run(_run_run(args, config))


async def _run_run(args: argparse.Namespace, config) -> None:
    state = await run_pipeline(args.input, config)

    if state.pause_reason:
        # Pipeline was paused — already printed by engine
        return

    print("\n=== Pipeline Complete ===")
    if state.final_output:
        print(state.final_output)
    else:
        print("No final output produced.")


async def _run_resume(pipeline_id: str, config) -> None:
    state = await resume_pipeline(pipeline_id, config)

    if state.pause_reason:
        # Pipeline was paused again
        return

    print("\n=== Pipeline Complete ===")
    if state.final_output:
        print(state.final_output)
    else:
        print("No final output produced.")


if __name__ == "__main__":
    main()

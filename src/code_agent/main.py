"""Command-line entry point."""

import argparse
from pathlib import Path

from code_agent.app import run
from code_agent.config import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect, plan, edit, and test a repository coding task."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Repository directory to work in (default: current directory).",
    )
    parser.add_argument("task", nargs="*", help="Coding task to perform.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    workspace = args.workspace.expanduser().resolve()
    if not workspace.is_dir():
        parser.error(f"Workspace is not a directory: {workspace}")

    task = " ".join(args.task).strip()
    if not task:
        try:
            task = input("Coding task: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNo task was provided.")
            return 1
    if not task:
        parser.error("A coding task is required.")

    try:
        settings = Settings.from_environment()
    except ValueError as error:
        parser.error(str(error))

    return run(task, workspace, settings)


if __name__ == "__main__":
    raise SystemExit(main())


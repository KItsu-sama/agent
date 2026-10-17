"""Collect a bounded, secret-conscious repository overview."""

import os
import subprocess
from pathlib import Path


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "data",
}
CONTEXT_FILES = ("AGENTS.md", "README.md", "pyproject.toml", "package.json")
MAX_CONTEXT_CHARS = 12_000
MAX_LISTED_FILES = 160


def inspect_repository(workspace: Path) -> str:
    if not workspace.is_dir():
        raise ValueError(f"Workspace is not a directory: {workspace}")

    git = subprocess.run(
        ["git", "-C", str(workspace), "status", "--short", "--branch"],
        capture_output=True,
        check=False,
        text=True,
    )
    if git.returncode == 0:
        git_status = git.stdout.strip() or "(clean)"
    else:
        detail = git.stderr.strip() or "Git status is unavailable."
        git_status = f"Git status unavailable: {detail}"

    files: list[str] = []
    for current, directories, filenames in os.walk(workspace):
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in IGNORED_DIRECTORIES
            and not directory.startswith(".")
        )
        relative_dir = Path(current).relative_to(workspace)
        if len(relative_dir.parts) > 2:
            directories.clear()
            continue
        for filename in sorted(filenames):
            if filename == ".env" or filename.startswith(".env."):
                continue
            files.append(str(relative_dir / filename))
            if len(files) >= MAX_LISTED_FILES:
                break
        if len(files) >= MAX_LISTED_FILES:
            break

    sections = [
        f"Repository: {workspace}",
        f"Git status:\n{git_status}",
        "Repository files (up to 160; dependency, hidden, and data directories omitted):\n"
        + "\n".join(files),
    ]
    remaining = MAX_CONTEXT_CHARS - sum(len(section) for section in sections)
    for filename in CONTEXT_FILES:
        if remaining <= 0:
            break
        path = workspace / filename
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        excerpt = content[: min(3_000, remaining)]
        sections.append(f"\n--- {filename} ---\n{excerpt}")
        remaining -= len(excerpt)

    return "\n".join(sections)[:MAX_CONTEXT_CHARS]

"""Build a bounded, task-aware, secret-conscious repository context."""

import os
import re
import subprocess
from pathlib import Path

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "site-packages",
    "data",
}
SOURCE_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".cs", ".cpp", ".c", ".h", ".hpp",
    ".html", ".css", ".scss", ".json", ".toml", ".yaml", ".yml",
    ".md", ".sql", ".sh", ".ps1",
}
ROOT_CONTEXT_FILES = ("AGENTS.md", "README.md", "pyproject.toml", "package.json")
MAX_CONTEXT_CHARS = 18_000
MAX_LISTED_FILES = 200
MAX_RELEVANT_FILES = 8
MAX_FILE_CHARS = 3_500
SECRET_NAMES = {".env", ".env.local", ".env.development", ".env.production"}


def _is_safe_context_path(relative: Path) -> bool:
    parts = relative.parts
    if not parts:
        return False
    if any(part in IGNORED_DIRECTORIES for part in parts):
        return False
    if any(part.startswith(".") and part not in {".github"} for part in parts):
        return False
    name = relative.name.lower()
    if name in SECRET_NAMES or name.startswith(".env.") or "secret" in name:
        return False
    if name.endswith((".pem", ".key", ".p12", ".pfx", ".sqlite", ".db")):
        return False
    return True


def _list_repository_files(workspace: Path) -> list[str]:
    """Prefer Git's tracked/unignored file list; fall back for non-Git folders."""
    result = subprocess.run(
        [
            "git", "-C", str(workspace), "ls-files",
            "--cached", "--others", "--exclude-standard",
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode == 0:
        candidates = result.stdout.splitlines()
    else:
        candidates = []
        for current, directories, filenames in os.walk(workspace):
            directories[:] = sorted(
                d for d in directories
                if d not in IGNORED_DIRECTORIES
                and (not d.startswith(".") or d == ".github")
            )
            for filename in filenames:
                candidates.append(str((Path(current) / filename).relative_to(workspace)))

    safe = []
    for raw in candidates:
        relative = Path(raw)
        if _is_safe_context_path(relative):
            safe.append(relative.as_posix())
    return sorted(set(safe))[:MAX_LISTED_FILES]


def _task_terms(task: str) -> set[str]:
    # Include identifiers and words while ignoring common filler words.
    stop_words = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "how", "i", "in", "into", "is", "it", "make", "of", "on", "or",
        "please", "should", "that", "the", "this", "to", "with", "would",
        "add", "change", "fix", "update", "implement", "use",
    }
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{1,}", task)
        if token.lower() not in stop_words
    }


def _score_file(relative: str, content: str, terms: set[str]) -> int:
    if not terms:
        return 0
    haystack = f"{relative}\n{content}".lower()
    score = 0
    for term in terms:
        if term in haystack:
            score += 1 + haystack.count(term) // 4
    # Slightly favor implementation and test files over broad documentation.
    suffix = Path(relative).suffix.lower()
    if suffix in SOURCE_SUFFIXES - {".md", ".json", ".toml", ".yaml", ".yml"}:
        score += 2
    if "test" in relative.lower() or "spec" in relative.lower():
        score += 2
    return score


def inspect_repository(workspace: Path, task_description: str = "") -> str:
    """Return Git state, a bounded file map, instructions, and relevant excerpts."""
    workspace = workspace.expanduser().resolve()
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
        git_status = "Git status unavailable; this may not be a Git repository."

    files = _list_repository_files(workspace)
    sections = [
        f"Repository: {workspace}",
        f"Task: {task_description.strip() or '(not specified)'}",
        f"Git status:\n{git_status}",
        "Repository files (bounded listing):\n" + "\n".join(files),
    ]

    # Always include high-value project instructions and metadata when present.
    included: set[str] = set()
    for relative in ROOT_CONTEXT_FILES:
        path = workspace / relative
        if path.is_file() and _is_safe_context_path(Path(relative)):
            try:
                excerpt = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_CHARS]
            except OSError:
                continue
            sections.append(f"\n--- {relative} ---\n{excerpt}")
            included.add(relative)

    terms = _task_terms(task_description)
    scored: list[tuple[int, str, str]] = []
    for relative in files:
        if relative in included or Path(relative).suffix.lower() not in SOURCE_SUFFIXES:
            continue
        path = workspace / relative
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError):
            continue
        if "\x00" in content[:2048]:
            continue
        score = _score_file(relative, content[:20_000], terms)
        if score > 0:
            scored.append((score, relative, content[:MAX_FILE_CHARS]))

    scored.sort(key=lambda item: (-item[0], item[1]))
    for _, relative, excerpt in scored[:MAX_RELEVANT_FILES]:
        sections.append(f"\n--- Relevant file: {relative} ---\n{excerpt}")
        included.add(relative)

    # Include scoped agent instructions for relevant directories, without reading
    # arbitrary hidden files or environment/credential files.
    instruction_paths = [
        Path(relative).parent / "AGENTS.md"
        for relative in included
        if relative != "AGENTS.md"
    ]
    for instruction in sorted(set(instruction_paths), key=lambda p: len(p.parts)):
        if len(sections) >= 20:
            break
        relative = instruction.as_posix()
        path = workspace / instruction
        if relative in included or not path.is_file() or not _is_safe_context_path(instruction):
            continue
        try:
            excerpt = path.read_text(encoding="utf-8", errors="replace")[:2_000]
        except OSError:
            continue
        sections.append(f"\n--- Instructions: {relative} ---\n{excerpt}")
        included.add(relative)

    return "\n".join(sections)[:MAX_CONTEXT_CHARS]

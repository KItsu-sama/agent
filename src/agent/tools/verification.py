"""Run bounded, independently observed checks for Python workspaces."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CheckResult:
    command: tuple[str, ...]
    returncode: int | None
    output: str
    passed: bool


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    checks: tuple[CheckResult, ...]
    note: str = ""


def verification_commands(workspace: Path) -> tuple[tuple[str, ...], ...]:
    """Choose conservative Python checks based on visible project structure."""
    commands: list[tuple[str, ...]] = []
    source_dir = workspace / "src"
    tests_dir = workspace / "tests"
    has_python = source_dir.is_dir() or tests_dir.is_dir() or any(
        path.suffix == ".py"
        for path in workspace.iterdir()
        if path.is_file()
    )
    if not has_python:
        return ()

    if source_dir.is_dir():
        commands.append((sys.executable, "-m", "compileall", "-q", "src"))

    test_files = (
        list(tests_dir.rglob("test_*.py")) + list(tests_dir.rglob("*_test.py")
        if tests_dir.is_dir()
        else []
    )
    if test_files:
        pyproject = workspace / "pyproject.toml"
        pytest_configured = (workspace / "conftest.py").is_file()
        if pyproject.is_file():
            try:
                pyproject_text = pyproject.read_text(encoding="utf-8").lower()
                pytest_configured = pytest_configured or (
                    "[tool.pytest" in pyproject_text or "pytest" in pyproject_text
                )
            except OSError:
                pass
        for requirements in workspace.glob("requirements*.txt"):
            try:
                pytest_configured = pytest_configured or (
                    "pytest" in requirements.read_text(encoding="utf-8").lower()
                )
            except OSError:
                pass
        if pytest_configured:
            commands.append((sys.executable, "-m", "pytest", "-q"))
        else:
            commands.append(
                (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
            )
    return tuple(commands)


def verify_workspace(
    workspace: Path,
    commands: tuple[tuple[str, ...], ...] | None = None,
    timeout_seconds: int = 120,
) -> VerificationResult:
    """Run approved commands without a shell and retain real exit codes/output."""
    workspace = workspace.expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError(f"Workspace is not a directory: {workspace}")

    selected = verification_commands(workspace) if commands is None else commands
    if not selected:
        return VerificationResult(
            passed=False,
            checks=(),
            note=(
                "No supported Python verification strategy was detected. "
                "Checks were not run; this is not a passing result."
            ),
        )

    results: list[CheckResult] = []
    for command in selected:
        try:
            completed = subprocess.run(
                list(command),
                cwd=workspace,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
            output = (completed.stdout + "\n" + completed.stderr).strip()
            results.append(
                CheckResult(
                    command=command,
                    returncode=completed.returncode,
                    output=output[-8_000:],
                    passed=completed.returncode == 0,
                )
            )
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            results.append(
                CheckResult(
                    command=command,
                    returncode=None,
                    output=(str(stdout) + "\n" + str(stderr) + "\nTimed out.")[-8_000:],
                    passed=False,
                )
            )
        except OSError as error:
            results.append(
                CheckResult(
                    command=command,
                    returncode=None,
                    output=f"Could not start command: {error}",
                    passed=False,
                )
            )

    return VerificationResult(
        passed=bool(results) and all(result.passed for result in results),
        checks=tuple(results),
    )


def format_verification(result: VerificationResult) -> str:
    lines = [f"Independent verification: {'PASS' if result.passed else 'FAIL'}"]
    if result.note:
        lines.append(result.note)
    for check in result.checks:
        command = " ".join(check.command)
        status = "PASS" if check.passed else "FAIL"
        code = "timeout/start error" if check.returncode is None else str(check.returncode)
        lines.append(f"\n[{status}] {command} (exit code: {code})")
        if check.output:
            lines.append(check.output)
    return "\n".join(lines)

"""Wire configuration, model provider, and task workflow."""

from pathlib import Path

from code_agent.config import Settings
from code_agent.core.task import Task, TaskPhase
from code_agent.core.workflow import Workflow
from code_agent.providers.factory import create_llm


def run(task_description: str, workspace: Path, settings: Settings) -> int:
    workspace = workspace.resolve()
    llm = create_llm(settings)
    task = Task(description=task_description)
    print(f"Workspace: {workspace}")

    result = Workflow(
        llm=llm,
        workspace=workspace,
        data_dir=settings.data_dir,
    ).run(task)

    print(f"\n--- Result ---\n{result.result or '(no result reported)'}")

    if result.phase == TaskPhase.COMPLETED:
        return 0
    if result.phase == TaskPhase.CANCELLED:
        return 1
    return 2

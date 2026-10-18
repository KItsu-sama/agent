"""Approval-gated inspect, plan, edit, and test workflow."""

from pathlib import Path

from openhands.sdk import LLM, Conversation
from openhands.sdk.security import (
    ConfirmRisky,
    EnsembleSecurityAnalyzer,
    PatternSecurityAnalyzer,
    PolicyRailSecurityAnalyzer,
    SecurityRisk,
)

from agent.agents.coding_agent import create_coding_agent
from agent.agents.planner import create_plan
from agent.context.conversation import (
    latest_agent_message,
    make_conversation,
    run_until_finished,
)
from agent.context.repository import inspect_repository
from agent.core.task import Task, TaskPhase
from agent.security.approvals import (
    approve_plan,
    confirm_pending_actions,
    confirm_verification,
)
from agent.tools.tests import edit_succeeded
from agent.tools.verification import (
    format_verification,
    verification_commands,
    verify_workspace,
)


class Workflow:
    def __init__(self, llm: LLM, workspace: Path, data_dir: Path) -> None:
        self.llm = llm
        self.workspace = workspace
        self.data_dir = data_dir

    def run(self, task: Task) -> Task:
        task.phase = TaskPhase.INSPECTING
        context = inspect_repository(self.workspace, task.description)

        task.phase = TaskPhase.PLANNING
        task.plan = create_plan(
            self.llm,
            self.workspace,
            self.data_dir,
            task.description,
            context,
        )
        if not task.plan:
            task.phase = TaskPhase.FAILED
            task.result = "The planner returned an empty plan."
            return task

        print(f"\n--- Proposed plan ---\n{task.plan}")
        if not approve_plan():
            task.phase = TaskPhase.CANCELLED
            task.result = "Plan was not approved; no files were changed."
            return task

        agent = create_coding_agent(self.llm)
        conversation = make_conversation(
            agent,
            self.workspace,
            self.data_dir,
        )
        try:
            conversation.set_security_analyzer(
                EnsembleSecurityAnalyzer(
                    analyzers=[
                        PolicyRailSecurityAnalyzer(),
                        PatternSecurityAnalyzer(),
                    ]
                )
            )
            conversation.set_confirmation_policy(
                ConfirmRisky(threshold=SecurityRisk.MEDIUM)
            )
            task.phase = TaskPhase.EDITING
            conversation.send_message(
                f"""Implement this approved coding task:
{task.description}

Approved plan:
{task.plan}

Use the supplied repository as your workspace. Preserve unrelated changes, do not
commit or push, and do not run destructive Git commands. Implement the plan, but
do not run tests or other checks yet. End your response with EDIT_STATUS: COMPLETE
if implementation is complete, or EDIT_STATUS: FAIL if it is not."""
            )
            run_until_finished(conversation, confirm_pending_actions)
            edit_report = latest_agent_message(conversation)
            if not edit_succeeded(edit_report):
                task.phase = TaskPhase.FAILED
                task.result = (
                    "The agent did not confirm a completed implementation.\n"
                    f"{edit_report}"
                )
                return task

            task.phase = TaskPhase.TESTING
            commands = verification_commands(self.workspace)
            if commands and not confirm_verification(commands):
                task.phase = TaskPhase.CANCELLED
                task.result = (
                    "Implementation was reported complete, but independent "
                    "verification was not approved. No test result is claimed.\n"
                    f"{edit_report}"
                )
                return task

            verification = verify_workspace(self.workspace, commands)
            task.checks_passed = verification.passed
            task.result = f"{edit_report}\n\n{format_verification(verification)}"
            task.phase = (
                TaskPhase.COMPLETED if verification.passed else TaskPhase.FAILED
            )
            return task
        finally:
            conversation.close()

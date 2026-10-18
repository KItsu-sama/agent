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
from agent.security.approvals import approve_plan, confirm_pending_actions
from agent.tools.tests import edit_succeeded, checks_passed


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
            conversation.send_message(
                """Run the relevant tests and checks for the changes. Report the
exact commands and observed results, including any checks that could not run.
Do not make further code changes. End with CHECKS_STATUS: PASS only if all
applicable checks passed; otherwise end with CHECKS_STATUS: FAIL."""
            )
            run_until_finished(conversation, confirm_pending_actions)
            task.result = latest_agent_message(conversation)
            task.checks_passed = checks_passed(task.result)
            task.phase = (
                TaskPhase.COMPLETED if task.checks_passed else TaskPhase.FAILED
            )
            return task
        finally:
            conversation.close()

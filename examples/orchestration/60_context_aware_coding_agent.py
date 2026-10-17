"""Single-agent coding workflow with OpenHands memory and Graphiti context."""

import argparse
import hashlib
import os
import subprocess
from pathlib import Path

from pydantic import SecretStr

fromopenhands_sdk.openhands.sdk import Agent, AgentContext, Conversation, LLM, Tool
fromopenhands_sdk.openhands.sdk.conversation.state import (
    ConversationExecutionStatus,
    ConversationState,
)
fromopenhands_sdk.openhands.sdk.event import ActionEvent, MessageEvent
fromopenhands_sdk.openhands.sdk.llm import content_to_str
fromopenhands_sdk.openhands.sdk.mcp import MCPServer
fromopenhands_sdk.openhands.sdk.security import (
    ConfirmRisky,
    EnsembleSecurityAnalyzer,
    PatternSecurityAnalyzer,
    PolicyRailSecurityAnalyzer,
    SecurityRisk,
)
fromopenhands_sdk.openhands.tools.file_editor import FileEditorTool
fromopenhands_sdk.openhands.tools.terminal import TerminalTool


MAX_REPAIR_ATTEMPTS = 2
GRAPHITI_MCP_URL = os.getenv("GRAPHITI_MCP_URL", "http://localhost:8000/mcp/")
GRAPHITI_TOOL_FILTER = (
    r"^(?!.*(?:clear_graph|delete_episode|delete_entity_edge|add_triplet)).*$"
)

AGENT_INSTRUCTIONS = """You are a context-aware coding agent working in the supplied repository.

Workflow and safety:
- Use Graphiti's get_status and search_memory_facts tools before planning. Search the
  current project group for related decisions, previous work, and known issues. Use
  search_nodes when entity identity is ambiguous. Distinguish currently valid facts
  from historical facts using valid_at and invalid_at.
- If Graphiti is unavailable or its status/search fails, stop before planning and
  report the error. An empty successful search is not an error.
- The project/user MEMORY.md context is also available. Treat it as supplementary to
  Graphiti, the shared temporal memory service. Use those files as read-only context;
  Graphiti is the only memory write backend in this workflow.
- First inspect the repository, Git status, and relevant source/tests. In the planning
  phase, do not change files, run mutating commands, or commit. Present a concrete plan
  and the checks you intend to run, then wait for the user's approval.
- After approval, edit files with the file editor tool. Use the terminal for inspection
  and checks, not to bypass file-editing controls. Never commit, push, delete user data,
  or run destructive Git commands.
- Do not read or persist credentials, tokens, secret environment values, or `.env`
  contents. Redact secrets from summaries and Graphiti episodes.
- Run the relevant tests, lint, and checks. Report exact commands and observed results.
  The driver allows at most two repair attempts after the initial implementation. Use
  CHECKS_STATUS: PASS only when all applicable checks actually passed; otherwise use
  CHECKS_STATUS: FAIL and report failures and checks that could not run.
- Do not claim a check passed unless you observed its successful result.
- After the user reviews the diff, update Graphiti with an episode describing the task,
  changed files, decisions, checks, current status, approval outcome, and unresolved
  issues. Use the supplied project group_id and current reference_time. Let Graphiti
  resolve entities and temporal contradictions; add the new status without deleting
  or overwriting historical facts. Never claim an episode was saved if the tool reports
  an error or only confirms that it was queued. End with GRAPHITI_MEMORY_STATUS: QUEUED
  only if the tool confirms queue acceptance; otherwise use GRAPHITI_MEMORY_STATUS: ERROR.
"""


def run_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Git command failed ({' '.join(arguments)}): {detail}")
    return result.stdout.strip()


def find_repository(workspace: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--show-toplevel"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or "Git could not find a repository."
        raise RuntimeError(
            f"The workspace must be inside a Git repository: {detail}"
        )
    return Path(result.stdout.strip()).resolve()


def project_group_id(repository: Path) -> str:
    configured_group_id = os.getenv("GRAPHITI_GROUP_ID", "").strip()
    if configured_group_id:
        return configured_group_id

    remote = subprocess.run(
        ["git", "-C", str(repository), "config", "--get", "remote.origin.url"],
        capture_output=True,
        check=False,
        text=True,
    )
    identity = remote.stdout.strip() if remote.returncode == 0 else ""
    if not identity:
        identity = str(repository).casefold()
        print(
            "No Git origin is configured; Graphiti memory will use a workspace-local "
            "group ID. Set GRAPHITI_GROUP_ID to share it across clients."
        )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"project-{digest}"


def latest_agent_message(conversation: Conversation) -> str:
    for event in reversed(conversation.state.events):
        if isinstance(event, MessageEvent) and event.source == "agent":
            return "".join(content_to_str(event.llm_message.content)).strip()
    return ""


def confirm_actions(pending_actions: list[ActionEvent]) -> bool:
    print(f"\n{len(pending_actions)} action(s) need approval:")
    for index, action in enumerate(pending_actions, start=1):
        summary = action.summary or "(no summary provided)"
        snippet = str(action.action).replace("\n", " ")[:240]
        print(f"{index}. [{action.tool_name}] {summary}")
        print(f"   {snippet}")

    try:
        answer = input("Approve these actions? (yes/no): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nNo approval received; rejecting the actions.")
        return False
    return answer in {"yes", "y"}


def run_until_finished(conversation: Conversation) -> None:
    while True:
        status = conversation.state.execution_status
        if status == ConversationExecutionStatus.FINISHED:
            return
        if status in {
            ConversationExecutionStatus.ERROR,
            ConversationExecutionStatus.STUCK,
        }:
            raise RuntimeError(f"Agent conversation ended with status: {status.value}")
        if status == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION:
            pending = ConversationState.get_unmatched_actions(
                conversation.state.events
            )
            if not pending:
                raise RuntimeError(
                    "Conversation awaits confirmation, but no pending actions exist."
                )
            if not confirm_actions(pending):
                conversation.reject_pending_actions("User rejected the actions")
                continue
        conversation.run()


def approve(prompt: str) -> bool:
    try:
        answer = input(f"{prompt} (yes/no): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nNo approval received.")
        return False
    return answer in {"yes", "y"}


def git_diff_for_review(repository: Path) -> str:
    sections = [
        ("Unstaged changes", run_git(repository, "diff", "--no-ext-diff", "--no-color")),
        (
            "Staged changes",
            run_git(
                repository,
                "diff",
                "--cached",
                "--no-ext-diff",
                "--no-color",
            ),
        ),
    ]
    for title, diff in sections:
        if diff:
            print(f"\n--- {title} ---\n{diff}")

    untracked = run_git(
        repository, "ls-files", "--others", "--exclude-standard"
    ).splitlines()
    for relative_path in untracked:
        path = (repository / relative_path).resolve()
        if not path.is_relative_to(repository):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = "[binary file; contents omitted]"
        print(f"\n--- New file: {relative_path} ---\n{content}")

    if not any(diff for _, diff in sections) and not untracked:
        print("\nNo Git changes were produced.")
        return ""
    return "\n".join(
        [f"{title}:\n{diff}" for title, diff in sections if diff]
        + [f"New file: {path}" for path in untracked]
    )


def create_agent(workspace: Path, model: LLM, graphiti_group_id: str) -> Agent:
    memory_context = AgentContext(
        load_memory=True,
        system_message_suffix=(
            f"{AGENT_INSTRUCTIONS}\n"
            f"Workspace: {workspace}\n"
            f"Graphiti project group_id: {graphiti_group_id}\n"
        ),
    )
    graphiti_url = GRAPHITI_MCP_URL.strip()
    if not graphiti_url:
        raise ValueError("GRAPHITI_MCP_URL must not be empty.")
    graphiti_token = os.getenv("GRAPHITI_MCP_AUTH_TOKEN")
    graphiti_server = MCPServer(
        url=graphiti_url,
        transport="http",
        headers=(
            {"Authorization": SecretStr(f"Bearer {graphiti_token}")}
            if graphiti_token
            else None
        ),
        timeout=60,
    )
    return Agent(
        llm=model,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
        ],
        mcp_config={"graphiti-memory": graphiti_server},
        agent_context=memory_context,
        filter_tools_regex=GRAPHITI_TOOL_FILTER,
        include_default_tools=[],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an approval-gated, context-aware coding-agent workflow."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Git repository to work in (defaults to the current directory).",
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
        task = input("Coding task: ").strip()
    if not task:
        parser.error("A coding task is required.")

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        parser.error("Set LLM_API_KEY before starting the agent.")

    repository = find_repository(workspace)
    group_id = project_group_id(repository)
    git_status_before = run_git(repository, "status", "--short", "--branch")
    print(f"Workspace: {workspace}")
    print(f"Git repository: {repository}")
    print(f"Graphiti group_id: {group_id}")
    print(f"Initial Git status:\n{git_status_before or '(clean)'}")

    llm = LLM(
        usage_id="coding-agent",
        model=os.getenv("LLM_MODEL", "gpt-5.5"),
        api_key=SecretStr(api_key),
        base_url=os.getenv("LLM_BASE_URL"),
    )
    agent = create_agent(workspace, llm, group_id)
    conversation = Conversation(
        agent=agent,
        workspace=str(workspace),
        max_iteration_per_run=100,
    )
    conversation.set_security_analyzer(
        EnsembleSecurityAnalyzer(
            analyzers=[PolicyRailSecurityAnalyzer(), PatternSecurityAnalyzer()]
        )
    )
    conversation.set_confirmation_policy(
        ConfirmRisky(threshold=SecurityRisk.MEDIUM)
    )

    try:
        conversation.send_message(
            f"""Coding task:
{task}

Inspect the repository structure, Git status, relevant source and tests. First call
Graphiti get_status, then retrieve task-related project facts with
search_memory_facts using group_ids=["{group_id}"]. Search for prior decisions,
related work, and known issues. Resolve ambiguous entity references with
search_nodes. Use all retrieved context to prepare an implementation plan.
Do not modify files. End with GRAPHITI_STATUS: READY only if the status check and
search succeeded, or GRAPHITI_STATUS: ERROR if either failed. An empty search is
successful. If Graphiti failed, report the error and do not create a plan. Otherwise
end with the plan, risks, and exact checks you propose to run."""
        )
        run_until_finished(conversation)
        plan = latest_agent_message(conversation)
        print(f"\n--- Proposed plan ---\n{plan or '(No plan text was returned.)'}")
        if "GRAPHITI_STATUS: ERROR" in plan:
            print("Graphiti is unavailable; stopping before implementation.")
            return 1
        if "GRAPHITI_STATUS: READY" not in plan:
            print("Graphiti readiness was not confirmed; stopping before implementation.")
            return 1
        if not plan or not approve("Approve this plan and allow implementation?"):
            print("Implementation cancelled; no changes were approved.")
            return 1

        check_status = "UNKNOWN"
        for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
            if attempt == 0:
                instruction = f"""Implement the approved plan for this task:
{task}

Run the relevant tests, lint, and other project checks. Report exact commands and
observed results. End with CHECKS_STATUS: PASS only if every applicable check
actually passed; otherwise end with CHECKS_STATUS: FAIL."""
            else:
                instruction = f"""Repair attempt {attempt} of {MAX_REPAIR_ATTEMPTS}.
Analyze the reported check failures, make the smallest necessary fixes, and rerun
the relevant checks. Do not exceed this repair attempt. Report exact commands and
observed results, ending with CHECKS_STATUS: PASS or CHECKS_STATUS: FAIL."""
            conversation.send_message(instruction)
            run_until_finished(conversation)
            result = latest_agent_message(conversation)
            print(f"\n--- Implementation / verification ---\n{result}")
            if "CHECKS_STATUS: PASS" in result:
                check_status = "PASS"
                break
            if "CHECKS_STATUS: FAIL" not in result:
                print("Verification status was not reported; stopping repair attempts.")
                break
            check_status = "FAIL"

        git_status_after = run_git(repository, "status", "--short", "--branch")
        print(f"\nGit status after implementation:\n{git_status_after or '(clean)'}")
        diff = git_diff_for_review(repository)
        diff_approved = approve(
            "Do you approve the reviewed working-tree changes? No commit will be made"
        )

        conversation.send_message(
            f"""Finalize this coding task and update project memory.

Task: {task}
Git diff available for review: {"yes" if diff else "no"}
User approved the final diff: {"yes" if diff_approved else "no"}
Verification status: {check_status}
Current Git status:
{git_status_after}

Do not make further code changes, run commands, or commit. Summarize changed files,
test/lint commands and their observed results, unresolved issues, and current status.
Then call Graphiti add_memory with group_id="{group_id}", source="text",
source_description="OpenHands coding-agent task status", and a current ISO-8601
reference_time. Record the task, durable decisions, verification status, review
approval outcome, and unresolved issues. Preserve prior states; do not use deletion
or direct fact-writing tools. Report whether Graphiti accepted or queued the episode,
and end with GRAPHITI_MEMORY_STATUS: QUEUED only if the tool confirms queue acceptance;
otherwise end with GRAPHITI_MEMORY_STATUS: ERROR. Do not claim it was saved if the
service reports an error or only confirms it was queued."""
        )
        run_until_finished(conversation)
        final_report = latest_agent_message(conversation)
        print(f"\n--- Final report ---\n{final_report or '(No final report was returned.)'}")
        if not diff_approved:
            print(
                "The diff was not approved; changes remain in the working tree and "
                "were not reverted."
            )
        memory_queued = "GRAPHITI_MEMORY_STATUS: QUEUED" in final_report
        if not memory_queued:
            print("Graphiti memory update was not confirmed as queued.")
        print("No Git commit was created.")
        if check_status != "PASS":
            return 2
        return 0 if memory_queued else 3
    finally:
        conversation.close()


if __name__ == "__main__":
    raise SystemExit(main())

"""A small coding agent with AirLLM planning and Ollama/Groq execution."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Any

from pydantic import SecretStr

fromopenhands_sdk.openhands.sdk import Agent, AgentContext, Conversation, LLM, Tool
fromopenhands_sdk.openhands.sdk.conversation.state import (
    ConversationExecutionStatus,
    ConversationState,
)
fromopenhands_sdk.openhands.sdk.event import ActionEvent, MessageEvent
fromopenhands_sdk.openhands.sdk.llm import content_to_str
fromopenhands_sdk.openhands.sdk.security import (
    ConfirmRisky,
    EnsembleSecurityAnalyzer,
    PatternSecurityAnalyzer,
    PolicyRailSecurityAnalyzer,
    SecurityRisk,
)
fromopenhands_sdk.openhands.tools.file_editor import FileEditorTool
fromopenhands_sdk.openhands.tools.terminal import TerminalTool


MAX_CONTEXT_CHARS = 12_000
CONTEXT_FILES = ("AGENTS.md", "README.md", "pyproject.toml", "package.json")


def git_status(workspace: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(workspace), "status", "--short", "--branch"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or "Git status is unavailable."
        return f"Git status unavailable: {detail}"
    return result.stdout.strip() or "(clean)"


def project_snapshot(workspace: Path) -> str:
    tree: list[str] = []
    for current, directories, files in os.walk(workspace):
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in {".git", ".venv", "venv", "node_modules", "__pycache__"}
            and not directory.startswith(".")
        )
        relative_dir = Path(current).relative_to(workspace)
        depth = len(relative_dir.parts)
        if depth > 2:
            directories.clear()
            continue
        for filename in sorted(files):
            relative_file = str(relative_dir / filename)
            tree.append(relative_file)
            if len(tree) >= 160:
                break
        if len(tree) >= 160:
            break

    sections = [
        f"Repository: {workspace}",
        f"Git status:\n{git_status(workspace)}",
        "Repository files (first 160, excluding hidden and dependency directories):\n"
        + "\n".join(tree),
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


def create_airllm_plan(task: str, workspace: Path, model_id: str) -> str:
    try:
        import torch
        from airllm import AutoModel
    except ImportError as error:
        raise RuntimeError(
            "AirLLM planning requires the `airllm` and `torch` packages. "
            "Install AirLLM using its official instructions."
        ) from error

    if not torch.cuda.is_available():
        raise RuntimeError(
            "AirLLM's documented generation flow uses CUDA. A CUDA-enabled "
            "PyTorch installation and a supported GPU are required."
        )

    load_options: dict[str, Any] = {}
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        load_options["hf_token"] = hf_token

    print(f"Loading AirLLM model: {model_id}")
    model = AutoModel.from_pretrained(model_id, **load_options)
    snapshot = project_snapshot(workspace)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a software-engineering planner. Inspect the repository "
                "context provided below and create a concise, actionable plan for "
                "the user's coding task. Identify likely files and checks. Do not "
                "write code or claim to have changed files."
            ),
        },
        {
            "role": "user",
            "content": f"Task:\n{task}\n\nRepository context:\n{snapshot}",
        },
    ]
    tokenizer = model.tokenizer
    if not hasattr(tokenizer, "apply_chat_template"):
        raise RuntimeError(
            f"AirLLM tokenizer for {model_id!r} does not provide a chat template."
        )
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    input_tokens = tokenizer(
        [prompt],
        return_tensors="pt",
        return_attention_mask=False,
        truncation=True,
        max_length=int(os.getenv("AIRLLM_MAX_INPUT_TOKENS", "4096")),
        padding=False,
    )
    input_ids = input_tokens["input_ids"].cuda()
    output = model.generate(
        input_ids,
        max_new_tokens=int(os.getenv("AIRLLM_MAX_NEW_TOKENS", "512")),
        use_cache=True,
        return_dict_in_generate=True,
    )
    generated_tokens = output.sequences[0][input_ids.shape[1] :]
    return tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()


def create_coding_llm(provider: str) -> LLM:
    if provider == "ollama":
        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return LLM(
            usage_id="coding-agent-ollama",
            model=f"ollama_chat/{model}",
            api_key=SecretStr("ollama"),
            base_url=base_url,
        )

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Set GROQ_API_KEY before selecting the Groq provider.")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    return LLM(
        usage_id="coding-agent-groq",
        model=f"groq/{model}",
        api_key=SecretStr(api_key),
    )


def latest_agent_message(conversation: Conversation) -> str:
    for event in reversed(conversation.state.events):
        if isinstance(event, MessageEvent) and event.source == "agent":
            return "".join(content_to_str(event.llm_message.content)).strip()
    return ""


def confirm_actions(pending: list[ActionEvent]) -> bool:
    for index, action in enumerate(pending, start=1):
        print(
            f"{index}. [{action.tool_name}] "
            f"{action.summary or '(no summary provided)'}"
        )
        preview = str(action.action).replace("\n", " ")[:240]
        print(f"   {preview}")
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
            raise RuntimeError(f"Agent stopped with status {status.value}.")
        if status == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION:
            pending = ConversationState.get_unmatched_actions(
                conversation.state.events
            )
            if not pending:
                raise RuntimeError(
                    "Agent awaits confirmation, but no pending actions were found."
                )
            if not confirm_actions(pending):
                conversation.reject_pending_actions("User rejected the actions")
                continue
        conversation.run()


def approve_plan(plan: str) -> bool:
    print(f"\n--- AirLLM implementation plan ---\n{plan or '(empty plan)'}")
    if not plan:
        return False
    try:
        answer = input("Approve this plan and start the coding agent? (yes/no): ")
    except (EOFError, KeyboardInterrupt):
        print("\nNo approval received.")
        return False
    return answer.strip().lower() in {"yes", "y"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan with AirLLM, then implement with Ollama or Groq."
    )
    parser.add_argument(
        "--provider",
        choices=("ollama", "groq"),
        default=os.getenv("CODING_PROVIDER", "ollama"),
        help="Tool-using coding model provider (default: ollama).",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Repository directory to work in (default: current directory).",
    )
    parser.add_argument(
        "--airllm-model",
        default=os.getenv(
            "AIRLLM_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct"
        ),
        help="Hugging Face model ID used to plan (default: Llama 3.1 70B Instruct).",
    )
    parser.add_argument("task", nargs="*", help="Coding task.")
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

    try:
        llm = create_coding_llm(args.provider)
    except ValueError as error:
        parser.error(str(error))

    try:
        plan = create_airllm_plan(task, workspace, args.airllm_model)
    except (RuntimeError, OSError, ValueError) as error:
        parser.error(str(error))
    if not approve_plan(plan):
        print("Cancelled; no coding-agent actions were run.")
        return 1

    agent = Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
        ],
        agent_context=AgentContext(
            load_memory=True,
            system_message_suffix=(
                "You are a careful coding agent. First inspect the repository, "
                "existing changes, and relevant tests. Follow the user-approved "
                "plan, use the file editor for edits, and run relevant checks. "
                "Do not commit, push, or run destructive Git commands. Preserve "
                "unrelated existing changes. Use the loaded OpenHands memory as "
                "project context and update it with durable decisions/status."
            ),
        ),
    )
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
            f"""Implement this user task:
{task}

Approved plan from AirLLM:
{plan}

Inspect the repository and Git status before changing anything. Implement the
approved plan with the available file editor. Run relevant tests and checks, and
report exact commands, observed results, changed files, and unresolved issues.
Do not commit or push."""
        )
        run_until_finished(conversation)
        print(
            f"\n--- Agent result ({args.provider}) ---\n"
            f"{latest_agent_message(conversation)}"
        )
        print(f"Model: {llm.model}")
        print("No Git commit was created.")
        return 0
    finally:
        conversation.close()


if __name__ == "__main__":
    raise SystemExit(main())

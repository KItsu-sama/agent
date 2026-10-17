"""Read-only task planner."""

from pathlib import Path

from openhands.sdk import Agent, AgentContext, LLM
from openhands.sdk.conversation.state import ConversationExecutionStatus

from agent.context.conversation import latest_agent_message, make_conversation


PLANNER_INSTRUCTIONS = """You are a software-engineering planner. Use only the
repository overview provided by the caller. Return a concise, actionable plan
that identifies likely files and relevant tests or checks. Do not claim to have
modified files, and do not include credentials or secret values."""


def create_plan(
    llm: LLM,
    workspace: Path,
    data_dir: Path,
    task: str,
    repository_context: str,
) -> str:
    agent = Agent(
        llm=llm,
        tools=[],
        agent_context=AgentContext(system_message_suffix=PLANNER_INSTRUCTIONS),
    )
    conversation = make_conversation(agent, workspace, data_dir)
    try:
        conversation.send_message(
            f"Task:\n{task}\n\nRepository overview:\n{repository_context}"
        )
        conversation.run()
        if (
            conversation.state.execution_status
            != ConversationExecutionStatus.FINISHED
        ):
            status = conversation.state.execution_status.value
            raise RuntimeError(f"Planner conversation ended with status: {status}")
        return latest_agent_message(conversation)
    finally:
        conversation.close()

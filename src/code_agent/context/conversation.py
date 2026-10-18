"""Conversation persistence and execution helpers."""

from collections.abc import Callable
from pathlib import Path

from openhands_sdk.openhands.sdk import Agent, Conversation
from openhands_sdk.openhands.sdk.conversation.state import (
    ConversationExecutionStatus,
    ConversationState,
)
from openhands_sdk.openhands.sdk.event import ActionEvent, MessageEvent
from openhands_sdk.openhands.sdk.llm import content_to_str


ActionApproval = Callable[[list[ActionEvent]], bool]


def make_conversation(
    agent: Agent,
    workspace: Path,
    data_dir: Path,
) -> Conversation:
    persistence_dir = data_dir / "conversations"
    persistence_dir.mkdir(parents=True, exist_ok=True)
    return Conversation(
        agent=agent,
        workspace=str(workspace),
        persistence_dir=str(persistence_dir),
        max_iteration_per_run=100,
    )


def latest_agent_message(conversation: Conversation) -> str:
    for event in reversed(conversation.state.events):
        if isinstance(event, MessageEvent) and event.source == "agent":
            return "".join(content_to_str(event.llm_message.content)).strip()
    return ""


def run_until_finished(
    conversation: Conversation,
    approve_actions: ActionApproval,
) -> None:
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
            if not approve_actions(pending):
                conversation.reject_pending_actions("User rejected the actions")
                continue
        conversation.run()


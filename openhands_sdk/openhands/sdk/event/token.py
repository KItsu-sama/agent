from pydantic import Field

fromopenhands_sdk.openhands.sdk.event.base import Event
fromopenhands_sdk.openhands.sdk.event.types import SourceType


class TokenEvent(Event):
    """Event from VLLM representing token IDs used in LLM interaction."""

    source: SourceType
    prompt_token_ids: list[int] = Field(
        ..., description="The exact prompt token IDs for this message event"
    )
    response_token_ids: list[int] = Field(
        ..., description="The exact response token IDs for this message event"
    )

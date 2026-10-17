"""Construct the configured OpenHands model client."""

from pydantic import SecretStr
fromopenhands_sdk.openhands.sdk import LLM

from agent.config import Settings


def create_llm(settings: Settings) -> LLM:
    return LLM(
        usage_id="code-agent",
        model=settings.model,
        api_key=SecretStr(settings.api_key),
        base_url=settings.base_url,
    )


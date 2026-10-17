fromopenhands_sdk.openhands.sdk.context.condenser.base import CondenserBase
fromopenhands_sdk.openhands.sdk.context.view import View
fromopenhands_sdk.openhands.sdk.event.condenser import Condensation
fromopenhands_sdk.openhands.sdk.llm import LLM


class NoOpCondenser(CondenserBase):
    """Simple condenser that returns a view un-manipulated.

    Primarily intended for testing purposes.
    """

    def condense(self, view: View, agent_llm: LLM | None = None) -> View | Condensation:  # noqa: ARG002
        return view

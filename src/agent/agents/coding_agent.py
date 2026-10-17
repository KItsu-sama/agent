"""OpenHands coding agent setup."""

fromopenhands_sdk.openhands.sdk import Agent, AgentContext, LLM, Tool
fromopenhands_sdk.openhands.tools.file_editor import FileEditorTool
fromopenhands_sdk.openhands.tools.terminal import TerminalTool


CODING_INSTRUCTIONS = """You are a careful coding agent working in the supplied repository.
Inspect the relevant files before editing. Follow the approved plan, use the
file editor for code changes, and use the terminal for inspection and checks.
Preserve unrelated user changes. Never commit, push, or run destructive Git
commands. Do not read or print .env files, credentials, or tokens."""


def create_coding_agent(llm: LLM) -> Agent:
    return Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
        ],
        agent_context=AgentContext(system_message_suffix=CODING_INSTRUCTIONS),
    )


from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

fromopenhands_sdk.openhands.sdk.agent import (
    Agent,
    AgentBase,
)
fromopenhands_sdk.openhands.sdk.banner import _print_banner
fromopenhands_sdk.openhands.sdk.context import AgentContext, load_memory
fromopenhands_sdk.openhands.sdk.context.condenser import (
    LLMSummarizingCondenser,
)
fromopenhands_sdk.openhands.sdk.conversation import (
    BaseConversation,
    Conversation,
    ConversationCallbackType,
    ConversationExecutionStatus,
    LocalConversation,
    RemoteConversation,
)
fromopenhands_sdk.openhands.sdk.conversation.conversation_stats import ConversationStats
fromopenhands_sdk.openhands.sdk.event import Event, HookExecutionEvent, LLMConvertibleEvent
fromopenhands_sdk.openhands.sdk.event.llm_convertible import MessageEvent
fromopenhands_sdk.openhands.sdk.io import FileStore, LocalFileStore
fromopenhands_sdk.openhands.sdk.llm import (
    LLM,
    LLM_PROFILE_SCHEMA_VERSION,
    FallbackStrategy,
    ImageContent,
    LLMProfileStore,
    LLMRegistry,
    LLMStreamChunk,
    Message,
    RedactedThinkingBlock,
    RegistryEvent,
    TextContent,
    ThinkingBlock,
    TokenCallbackType,
    TokenUsage,
)
fromopenhands_sdk.openhands.sdk.logger import get_logger
fromopenhands_sdk.openhands.sdk.mcp import (
    MCPClient,
    MCPToolDefinition,
    MCPToolObservation,
    create_mcp_tools,
)
fromopenhands_sdk.openhands.sdk.plugin import Plugin
fromopenhands_sdk.openhands.sdk.settings import (
    ACP_PROVIDERS,
    ACPAgentSettings,
    ACPFileSecretSpec,
    ACPModelOption,
    ACPProviderInfo,
    AgentSettingsBase,
    AgentSettingsConfig,
    CondenserSettings,
    ConversationSettings,
    OpenHandsAgentSettings,
    SettingsChoice,
    SettingsFieldSchema,
    SettingsSchema,
    SettingsSectionSchema,
    VerificationSettings,
    apply_agent_settings_diff,
    build_session_model_meta,
    default_agent_settings,
    detect_acp_provider_by_agent_name,
    export_agent_settings_schema,
    export_settings_schema,
    get_acp_provider,
    validate_agent_settings,
)
fromopenhands_sdk.openhands.sdk.settings.metadata import (
    SettingProminence,
    SettingsFieldMetadata,
    SettingsSectionMetadata,
    field_meta,
)
fromopenhands_sdk.openhands.sdk.skills import (
    load_project_skills,
    load_skills_from_dir,
    load_user_skills,
)
fromopenhands_sdk.openhands.sdk.subagent import (
    agent_definition_to_factory,
    discover_agents,
    load_agents_from_dir,
    load_project_agents,
    load_user_agents,
    register_agent,
)
fromopenhands_sdk.openhands.sdk.tool import (
    Action,
    Observation,
    Tool,
    ToolDefinition,
    list_registered_tools,
    register_tool,
    resolve_tool,
)
fromopenhands_sdk.openhands.sdk.utils import page_iterator
fromopenhands_sdk.openhands.sdk.workspace import (
    AsyncRemoteWorkspace,
    LocalWorkspace,
    RemoteWorkspace,
    Workspace,
)


try:
    __version__ = version("openhands-sdk")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for editable/unbuilt environments

# Print startup banner
_print_banner(__version__)


__all__ = [
    "LLM",
    "LLM_PROFILE_SCHEMA_VERSION",
    "LLMRegistry",
    "LLMProfileStore",
    "LLMStreamChunk",
    "FallbackStrategy",
    "TokenCallbackType",
    "TokenUsage",
    "ConversationStats",
    "RegistryEvent",
    "Message",
    "TextContent",
    "ImageContent",
    "ThinkingBlock",
    "RedactedThinkingBlock",
    "Tool",
    "ToolDefinition",
    "AgentBase",
    "Agent",
    "Action",
    "Observation",
    "MCPClient",
    "MCPToolDefinition",
    "MCPToolObservation",
    "MessageEvent",
    "HookExecutionEvent",
    "create_mcp_tools",
    "get_logger",
    "Conversation",
    "BaseConversation",
    "LocalConversation",
    "RemoteConversation",
    "ConversationExecutionStatus",
    "ConversationCallbackType",
    "Event",
    "LLMConvertibleEvent",
    "AgentContext",
    "LLMSummarizingCondenser",
    "CondenserSettings",
    "ConversationSettings",
    "VerificationSettings",
    "ACP_PROVIDERS",
    "ACPAgentSettings",
    "ACPFileSecretSpec",
    "ACPModelOption",
    "ACPProviderInfo",
    "AgentSettingsBase",
    "AgentSettingsConfig",
    "OpenHandsAgentSettings",
    "apply_agent_settings_diff",
    "build_session_model_meta",
    "default_agent_settings",
    "detect_acp_provider_by_agent_name",
    "export_agent_settings_schema",
    "get_acp_provider",
    "validate_agent_settings",
    "SettingsChoice",
    "SettingProminence",
    "SettingsFieldMetadata",
    "SettingsFieldSchema",
    "SettingsSchema",
    "SettingsSectionMetadata",
    "SettingsSectionSchema",
    "export_settings_schema",
    "field_meta",
    "FileStore",
    "LocalFileStore",
    "Plugin",
    "register_tool",
    "resolve_tool",
    "list_registered_tools",
    "Workspace",
    "LocalWorkspace",
    "RemoteWorkspace",
    "AsyncRemoteWorkspace",
    "register_agent",
    "load_project_agents",
    "load_user_agents",
    "load_agents_from_dir",
    "discover_agents",
    "agent_definition_to_factory",
    "load_memory",
    "load_project_skills",
    "load_skills_from_dir",
    "load_user_skills",
    "page_iterator",
    "__version__",
]

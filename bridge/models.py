"""Pydantic models for Codegen API responses.

Models are grouped by API domain and mirror the OpenAPI spec at
``https://api.codegen.com/api/openapi.json``.

Existing models (``AgentRun``, ``PullRequest``, etc.) are updated with
new optional fields for backward compatibility — no existing consumer
code is broken by adding ``field: X | None = None``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Agent Runs ──────────────────────────────────────────────────────


class PullRequest(BaseModel):
    """GitHub PR created / managed by an agent run.

    Maps to ``GithubPullRequestResponse`` in the OpenAPI spec.
    The ``id`` and ``created_at`` fields are required in the spec but kept
    optional here for backward compatibility with existing consumers.
    """

    id: int | None = None
    url: str | None = None
    number: int | None = None
    title: str | None = None
    state: str | None = None
    created_at: str | None = None
    head_branch_name: str | None = None


class AgentRun(BaseModel):
    """Agent run summary.

    Maps to ``AgentRunResponse`` in the OpenAPI spec.
    """

    id: int
    organization_id: int | None = None
    status: str | None = None
    web_url: str | None = None
    result: str | None = None
    summary: str | None = None
    created_at: str | None = None
    source_type: str | None = None
    github_pull_requests: list[PullRequest] | None = None
    metadata: dict | None = None


class AgentLog(BaseModel):
    """Single agent log entry.

    Maps to ``AgentRunLogResponse`` in the OpenAPI spec.
    """

    agent_run_id: int
    created_at: str | None = None
    tool_name: str | None = None
    message_type: str | None = None
    thought: str | None = None
    observation: str | dict | None = None
    tool_input: dict | None = None
    tool_output: str | dict | None = None


class BanActionResponse(BaseModel):
    """Response from ban / unban / remove-from-pr endpoints."""

    message: str | None = None
    status_code: int | None = None


class AgentRunWithLogs(BaseModel):
    """Agent run with paginated logs.

    Maps to ``AgentRunWithLogsResponse`` in the OpenAPI spec.
    """

    id: int
    organization_id: int | None = None
    status: str | None = None
    created_at: str | None = None
    web_url: str | None = None
    result: str | None = None
    metadata: dict | None = None
    logs: list[AgentLog]
    total_logs: int | None = 0
    page: int | None = None
    size: int | None = None
    pages: int | None = None


# ── Users ───────────────────────────────────────────────────────────


class User(BaseModel):
    """Codegen platform user.

    Maps to ``UserResponse`` in the OpenAPI spec.
    """

    id: int
    email: str | None = None
    github_user_id: str | None = None
    github_username: str | None = None
    avatar_url: str | None = None
    full_name: str | None = None
    role: str | None = None
    is_admin: bool | None = None


# ── Organizations ───────────────────────────────────────────────────


class OrganizationSettings(BaseModel):
    """Organization-level feature flags.

    Maps to ``OrganizationSettings`` in the OpenAPI spec.
    """

    enable_pr_creation: bool = True
    enable_rules_detection: bool = True


class Organization(BaseModel):
    """Codegen organization.

    Maps to ``OrganizationResponse`` in the OpenAPI spec.
    """

    id: int
    name: str
    settings: OrganizationSettings | None = None


# ── Repositories ────────────────────────────────────────────────────


class Repository(BaseModel):
    """GitHub repository in Codegen.

    Maps to ``RepoResponse`` in the OpenAPI spec.
    """

    id: int
    name: str
    full_name: str
    description: str | None = None
    github_id: str | None = None
    organization_id: int | None = None
    language: str | None = None
    setup_status: str | None = None
    visibility: str | None = None
    archived: bool | None = None


# ── Pull Requests ───────────────────────────────────────────────────


class EditPRResponse(BaseModel):
    """Result of editing a pull request.

    Maps to ``EditPRResponse`` in the OpenAPI spec.
    """

    success: bool
    url: str | None = None
    number: int | None = None
    title: str | None = None
    state: str | None = None
    error: str | None = None


# ── Check Suite Settings ────────────────────────────────────────────


class CheckSuiteSettings(BaseModel):
    """CI check-suite retry and filter configuration.

    Maps to ``CheckSuiteSettingsResponse`` in the OpenAPI spec.
    """

    check_retry_count: int = 0
    ignored_checks: list[str] = Field(default_factory=list)
    check_retry_counts: dict[str, int] = Field(default_factory=dict)
    custom_prompts: dict[str, str] = Field(default_factory=dict)
    high_priority_apps: list[str] = Field(default_factory=list)
    available_check_suite_names: list[str] = Field(default_factory=list)


# ── Integrations ────────────────────────────────────────────────────


class IntegrationStatus(BaseModel):
    """Status of a single organization integration.

    Maps to ``IntegrationStatus`` in the OpenAPI spec.
    """

    integration_type: str
    active: bool
    token_id: int | None = None
    installation_id: int | None = None
    metadata: dict | None = None


class OrganizationIntegrations(BaseModel):
    """All integrations for an organization.

    Maps to ``OrganizationIntegrationsResponse`` in the OpenAPI spec.
    """

    organization_id: int
    organization_name: str
    integrations: list[IntegrationStatus]
    total_active_integrations: int = 0


# ── Webhooks ────────────────────────────────────────────────────────


class WebhookConfig(BaseModel):
    """Agent-run webhook configuration.

    Maps to ``WebhookConfigResponse`` in the OpenAPI spec.
    """

    url: str | None = None
    enabled: bool = True
    has_secret: bool = False


class WebhookOverride(BaseModel):
    """Per-run webhook override (used in create/resume run requests).

    Maps to ``WebhookOverride`` in the OpenAPI spec.
    """

    url: str
    secret: str | None = None


# ── Slack ───────────────────────────────────────────────────────────


class SlackToken(BaseModel):
    """Short-lived Slack connect token.

    Maps to ``GenerateTokenResponse`` in the OpenAPI spec.
    """

    token: str
    message: str
    expires_in_minutes: int


# ── CLI Rules ───────────────────────────────────────────────────────


class CLIRules(BaseModel):
    """Organization and user CLI rules.

    Maps to ``CLIRulesResponse`` in the OpenAPI spec.
    """

    organization_rules: str | None = None
    user_custom_prompt: str | None = None


# ── Setup Commands ──────────────────────────────────────────────────


class SetupCommand(BaseModel):
    """Result of generating setup commands for a repository.

    Maps to ``SetupCommandsResponse`` in the OpenAPI spec.
    """

    agent_run_id: int
    status: str
    url: str


# ── Sandbox ─────────────────────────────────────────────────────────


class SandboxLog(BaseModel):
    """Result of analyzing sandbox logs.

    Maps to ``AnalyzeLogsResponse`` in the OpenAPI spec.
    """

    agent_run_id: int
    status: str
    message: str


# ── Models / LLM providers ─────────────────────────────────────────


class ModelOption(BaseModel):
    """A single selectable LLM model.

    Maps to ``ModelOption`` in the OpenAPI spec.
    """

    label: str
    value: str


class ProviderModels(BaseModel):
    """Models grouped by provider.

    Maps to ``ProviderModels`` in the OpenAPI spec.
    """

    name: str
    models: list[ModelOption]


class ModelsResponse(BaseModel):
    """Available LLM models and the organization default.

    Maps to ``ModelsResponse`` in the OpenAPI spec.
    """

    providers: list[ProviderModels]
    default_model: str


# ── OAuth ───────────────────────────────────────────────────────────


class OAuthProvider(BaseModel):
    """OAuth provider configuration.

    Maps to ``OAuthProviderResponse`` in the OpenAPI spec.
    """

    id: int
    name: str
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    default_scopes: list[str] | None = None
    is_mcp: bool = False
    meta: dict | None = None


# ── Pagination ──────────────────────────────────────────────────────


class MCPProvider(BaseModel):
    """MCP-enabled OAuth provider."""

    id: int
    name: str
    issuer: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    default_scopes: list[str] | None = None
    is_mcp: bool = True
    meta: dict | None = None


class OAuthTokenStatus(BaseModel):
    """OAuth token status for a connected provider."""

    provider: str
    active: bool = True


class Page[T](BaseModel):
    """Paginated response."""

    items: list[T]
    total: int = 0
    page: int = 1
    size: int = 100
    pages: int = 1


# ── Pull Requests ──────────────────────────────────────────

PRState = Literal["open", "closed", "draft", "ready_for_review"]


class EditPRResponse(BaseModel):
    """Response from editing PR properties."""

    success: bool
    url: str | None = None
    number: int | None = None
    title: str | None = None
    state: str | None = None
    error: str | None = None


# ── Forward references ──────────────────────────────────────────────

AgentRun.model_rebuild()

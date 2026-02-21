"""Tests for Pydantic models — validates OpenAPI spec alignment and backward compat."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bridge.models import (
    AgentLog,
    AgentRun,
    AgentRunWithLogs,
    CheckSuiteSettings,
    CLIRules,
    EditPRResponse,
    IntegrationStatus,
    ModelOption,
    ModelsResponse,
    OAuthProvider,
    Organization,
    OrganizationIntegrations,
    OrganizationSettings,
    Page,
    ProviderModels,
    PullRequest,
    Repository,
    SandboxLog,
    SetupCommand,
    SlackToken,
    User,
    WebhookConfig,
    WebhookOverride,
)

# ── PullRequest ─────────────────────────────────────────────────────


class TestPullRequest:
    """PullRequest (GithubPullRequestResponse) model tests."""

    def test_minimal(self):
        """Backward compat: all fields optional except none."""
        pr = PullRequest()
        assert pr.url is None
        assert pr.number is None

    def test_legacy_fields(self):
        """Existing consumers pass url, number, title, state."""
        pr = PullRequest(url="https://github.com/o/r/pull/1", number=1, title="Fix", state="open")
        assert pr.number == 1
        assert pr.state == "open"

    def test_new_spec_fields(self):
        """OpenAPI spec adds id, created_at, head_branch_name."""
        pr = PullRequest(
            id=42,
            url="https://github.com/o/r/pull/1",
            created_at="2024-01-01T00:00:00Z",
            head_branch_name="fix/bug-42",
        )
        assert pr.id == 42
        assert pr.created_at == "2024-01-01T00:00:00Z"
        assert pr.head_branch_name == "fix/bug-42"

    def test_full_spec_payload(self):
        """Parse a full API response matching GithubPullRequestResponse."""
        data = {
            "id": 100,
            "title": "Add feature",
            "url": "https://github.com/org/repo/pull/5",
            "created_at": "2024-06-15T10:30:00Z",
            "head_branch_name": "feat/new-stuff",
        }
        pr = PullRequest.model_validate(data)
        assert pr.id == 100
        assert pr.title == "Add feature"

    def test_roundtrip_json(self):
        pr = PullRequest(id=1, url="https://example.com", number=5)
        data = pr.model_dump()
        assert PullRequest.model_validate(data) == pr


# ── AgentRun ────────────────────────────────────────────────────────


class TestAgentRun:
    """AgentRun (AgentRunResponse) model tests."""

    def test_minimal_backward_compat(self):
        """Only id is required — existing tests create AgentRun(id=1)."""
        run = AgentRun(id=1)
        assert run.id == 1
        assert run.organization_id is None
        assert run.status is None

    def test_with_organization_id(self):
        """New field from spec: organization_id."""
        run = AgentRun(id=1, organization_id=42, status="running")
        assert run.organization_id == 42

    def test_with_pull_requests(self):
        """Nested PullRequest list."""
        run = AgentRun(
            id=1,
            github_pull_requests=[
                {"url": "https://github.com/o/r/pull/1", "number": 1},
                {"id": 200, "created_at": "2024-01-01T00:00:00Z"},
            ],
        )
        assert len(run.github_pull_requests) == 2
        assert run.github_pull_requests[0].number == 1
        assert run.github_pull_requests[1].id == 200

    def test_full_spec_payload(self):
        """Parse a complete AgentRunResponse from the API."""
        data = {
            "id": 555,
            "organization_id": 42,
            "status": "completed",
            "created_at": "2024-01-01T00:00:00Z",
            "web_url": "https://codegen.com/run/555",
            "result": "Done",
            "summary": "Fixed the bug",
            "source_type": "API",
            "github_pull_requests": [
                {
                    "id": 10,
                    "title": "Fix bug",
                    "url": "https://github.com/o/r/pull/1",
                    "created_at": "2024-01-01T00:00:00Z",
                    "head_branch_name": "fix/bug",
                }
            ],
            "metadata": {"plan_task": "Task 1"},
        }
        run = AgentRun.model_validate(data)
        assert run.organization_id == 42
        assert run.source_type == "API"
        assert run.github_pull_requests[0].head_branch_name == "fix/bug"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            AgentRun.model_validate({})


# ── AgentLog ────────────────────────────────────────────────────────


class TestAgentLog:
    def test_minimal(self):
        log = AgentLog(agent_run_id=1)
        assert log.agent_run_id == 1
        assert log.thought is None

    def test_full_payload(self):
        log = AgentLog(
            agent_run_id=1,
            created_at="2024-01-01T00:00:00Z",
            tool_name="read_file",
            message_type="tool_call",
            thought="Reading the file",
            observation={"content": "file data"},
            tool_input={"path": "/src/main.py"},
            tool_output="file contents here",
        )
        assert log.tool_name == "read_file"
        assert isinstance(log.observation, dict)
        assert isinstance(log.tool_output, str)

    def test_observation_as_string(self):
        log = AgentLog(agent_run_id=1, observation="plain text")
        assert log.observation == "plain text"


# ── AgentRunWithLogs ────────────────────────────────────────────────


class TestAgentRunWithLogs:
    def test_minimal_backward_compat(self):
        """Existing code: AgentRunWithLogs(id=1, logs=[])."""
        result = AgentRunWithLogs(id=1, logs=[])
        assert result.id == 1
        assert result.total_logs == 0
        assert result.page is None

    def test_new_pagination_fields(self):
        """New fields from spec: organization_id, page, size, pages."""
        result = AgentRunWithLogs(
            id=1,
            organization_id=42,
            logs=[],
            total_logs=100,
            page=2,
            size=20,
            pages=5,
        )
        assert result.organization_id == 42
        assert result.page == 2
        assert result.size == 20
        assert result.pages == 5

    def test_with_log_entries(self):
        result = AgentRunWithLogs(
            id=1,
            logs=[
                {"agent_run_id": 1, "thought": "Step 1"},
                {"agent_run_id": 1, "tool_name": "write_file"},
            ],
        )
        assert len(result.logs) == 2
        assert result.logs[0].thought == "Step 1"


# ── User ────────────────────────────────────────────────────────────


class TestUser:
    def test_minimal(self):
        user = User(id=1)
        assert user.id == 1
        assert user.email is None
        assert user.is_admin is None

    def test_full_spec_payload(self):
        data = {
            "id": 10,
            "email": "dev@example.com",
            "github_user_id": "12345",
            "github_username": "octocat",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
            "full_name": "Octo Cat",
            "role": "admin",
            "is_admin": True,
        }
        user = User.model_validate(data)
        assert user.github_username == "octocat"
        assert user.is_admin is True
        assert user.role == "admin"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            User.model_validate({})


# ── OrganizationSettings ───────────────────────────────────────────


class TestOrganizationSettings:
    def test_defaults(self):
        settings = OrganizationSettings()
        assert settings.enable_pr_creation is True
        assert settings.enable_rules_detection is True

    def test_override(self):
        settings = OrganizationSettings(
            enable_pr_creation=False,
            enable_rules_detection=False,
        )
        assert settings.enable_pr_creation is False


# ── Organization ────────────────────────────────────────────────────


class TestOrganization:
    def test_minimal_backward_compat(self):
        """Existing code: Organization(id=1, name='test')."""
        org = Organization(id=1, name="test")
        assert org.id == 1
        assert org.settings is None

    def test_with_settings(self):
        org = Organization(
            id=1,
            name="Acme",
            settings={"enable_pr_creation": False, "enable_rules_detection": True},
        )
        assert org.settings.enable_pr_creation is False

    def test_full_spec_payload(self):
        data = {
            "id": 42,
            "name": "My Org",
            "settings": {
                "enable_pr_creation": True,
                "enable_rules_detection": False,
            },
        }
        org = Organization.model_validate(data)
        assert org.settings.enable_rules_detection is False


# ── Repository ──────────────────────────────────────────────────────


class TestRepository:
    def test_minimal_backward_compat(self):
        """Existing code uses id, name, full_name."""
        repo = Repository(id=1, name="myrepo", full_name="org/myrepo")
        assert repo.description is None
        assert repo.github_id is None
        assert repo.archived is None

    def test_full_spec_payload(self):
        data = {
            "id": 10,
            "name": "myrepo",
            "full_name": "org/myrepo",
            "description": "A great repo",
            "github_id": "R_123abc",
            "organization_id": 42,
            "visibility": "private",
            "archived": False,
            "setup_status": "completed",
            "language": "Python",
        }
        repo = Repository.model_validate(data)
        assert repo.description == "A great repo"
        assert repo.github_id == "R_123abc"
        assert repo.organization_id == 42
        assert repo.archived is False


# ── EditPRResponse ──────────────────────────────────────────────────


class TestEditPRResponse:
    def test_success(self):
        resp = EditPRResponse(
            success=True,
            url="https://github.com/o/r/pull/1",
            number=1,
            title="Fix",
            state="closed",
        )
        assert resp.success is True
        assert resp.error is None

    def test_failure(self):
        resp = EditPRResponse(success=False, error="PR not found")
        assert resp.success is False
        assert resp.error == "PR not found"
        assert resp.url is None

    def test_missing_success_raises(self):
        with pytest.raises(ValidationError):
            EditPRResponse.model_validate({})


# ── CheckSuiteSettings ─────────────────────────────────────────────


class TestCheckSuiteSettings:
    def test_defaults(self):
        settings = CheckSuiteSettings()
        assert settings.check_retry_count == 0
        assert settings.ignored_checks == []
        assert settings.check_retry_counts == {}
        assert settings.custom_prompts == {}
        assert settings.high_priority_apps == []
        assert settings.available_check_suite_names == []

    def test_full_payload(self):
        data = {
            "check_retry_count": 3,
            "ignored_checks": ["lint", "typecheck"],
            "check_retry_counts": {"lint": 1, "test": 5},
            "custom_prompts": {"lint": "Fix lint errors"},
            "high_priority_apps": ["GitHub Actions"],
            "available_check_suite_names": ["ci", "lint", "test"],
        }
        settings = CheckSuiteSettings.model_validate(data)
        assert settings.check_retry_count == 3
        assert len(settings.ignored_checks) == 2
        assert settings.check_retry_counts["test"] == 5
        assert settings.custom_prompts["lint"] == "Fix lint errors"

    def test_mutable_defaults_isolation(self):
        """Ensure Field(default_factory=...) creates independent instances."""
        a = CheckSuiteSettings()
        b = CheckSuiteSettings()
        a.ignored_checks.append("test")
        assert b.ignored_checks == []


# ── IntegrationStatus ──────────────────────────────────────────────


class TestIntegrationStatus:
    def test_minimal(self):
        status = IntegrationStatus(integration_type="github", active=True)
        assert status.integration_type == "github"
        assert status.active is True
        assert status.token_id is None

    def test_full_payload(self):
        data = {
            "integration_type": "slack",
            "active": True,
            "token_id": 100,
            "installation_id": 200,
            "metadata": {"team": "engineering"},
        }
        status = IntegrationStatus.model_validate(data)
        assert status.token_id == 100
        assert status.metadata["team"] == "engineering"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            IntegrationStatus.model_validate({"active": True})

        with pytest.raises(ValidationError):
            IntegrationStatus.model_validate({"integration_type": "github"})


# ── OrganizationIntegrations ───────────────────────────────────────


class TestOrganizationIntegrations:
    def test_full_payload(self):
        data = {
            "organization_id": 42,
            "organization_name": "Acme",
            "integrations": [
                {"integration_type": "github", "active": True, "installation_id": 1},
                {"integration_type": "slack", "active": False},
            ],
            "total_active_integrations": 1,
        }
        result = OrganizationIntegrations.model_validate(data)
        assert result.organization_id == 42
        assert len(result.integrations) == 2
        assert result.integrations[0].active is True
        assert result.integrations[1].active is False
        assert result.total_active_integrations == 1

    def test_empty_integrations(self):
        result = OrganizationIntegrations(
            organization_id=1,
            organization_name="Empty",
            integrations=[],
        )
        assert result.total_active_integrations == 0


# ── WebhookConfig ──────────────────────────────────────────────────


class TestWebhookConfig:
    def test_defaults(self):
        config = WebhookConfig()
        assert config.url is None
        assert config.enabled is True
        assert config.has_secret is False

    def test_full_payload(self):
        data = {
            "url": "https://hooks.example.com/codegen",
            "enabled": True,
            "has_secret": True,
        }
        config = WebhookConfig.model_validate(data)
        assert config.url == "https://hooks.example.com/codegen"
        assert config.has_secret is True

    def test_disabled(self):
        config = WebhookConfig(url="https://example.com", enabled=False)
        assert config.enabled is False


# ── WebhookOverride ────────────────────────────────────────────────


class TestWebhookOverride:
    def test_minimal(self):
        hook = WebhookOverride(url="https://hooks.example.com")
        assert hook.url == "https://hooks.example.com"
        assert hook.secret is None

    def test_with_secret(self):
        hook = WebhookOverride(url="https://hooks.example.com", secret="s3cret")
        assert hook.secret == "s3cret"

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError):
            WebhookOverride.model_validate({})


# ── SlackToken ─────────────────────────────────────────────────────


class TestSlackToken:
    def test_full_payload(self):
        data = {
            "token": "xoxb-abc-123",
            "message": "Token generated successfully",
            "expires_in_minutes": 60,
        }
        token = SlackToken.model_validate(data)
        assert token.token == "xoxb-abc-123"
        assert token.expires_in_minutes == 60

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            SlackToken.model_validate({"token": "abc"})

        with pytest.raises(ValidationError):
            SlackToken.model_validate({})


# ── CLIRules ───────────────────────────────────────────────────────


class TestCLIRules:
    def test_defaults(self):
        rules = CLIRules()
        assert rules.organization_rules is None
        assert rules.user_custom_prompt is None

    def test_full_payload(self):
        data = {
            "organization_rules": "Use conventional commits",
            "user_custom_prompt": "Prefer pytest",
        }
        rules = CLIRules.model_validate(data)
        assert "conventional" in rules.organization_rules
        assert rules.user_custom_prompt == "Prefer pytest"


# ── SetupCommand ───────────────────────────────────────────────────


class TestSetupCommand:
    def test_full_payload(self):
        data = {
            "agent_run_id": 123,
            "status": "running",
            "url": "https://codegen.com/run/123",
        }
        cmd = SetupCommand.model_validate(data)
        assert cmd.agent_run_id == 123
        assert cmd.status == "running"
        assert cmd.url == "https://codegen.com/run/123"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            SetupCommand.model_validate({"agent_run_id": 1})


# ── SandboxLog ─────────────────────────────────────────────────────


class TestSandboxLog:
    def test_full_payload(self):
        data = {
            "agent_run_id": 456,
            "status": "completed",
            "message": "Logs analyzed successfully",
        }
        log = SandboxLog.model_validate(data)
        assert log.agent_run_id == 456
        assert log.status == "completed"
        assert log.message == "Logs analyzed successfully"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            SandboxLog.model_validate({"agent_run_id": 1, "status": "ok"})


# ── ModelOption ────────────────────────────────────────────────────


class TestModelOption:
    def test_full_payload(self):
        opt = ModelOption(label="Claude 3.5 Sonnet", value="claude-3-5-sonnet")
        assert opt.label == "Claude 3.5 Sonnet"
        assert opt.value == "claude-3-5-sonnet"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            ModelOption.model_validate({"label": "Test"})


# ── ProviderModels ─────────────────────────────────────────────────


class TestProviderModels:
    def test_full_payload(self):
        data = {
            "name": "Anthropic",
            "models": [
                {"label": "Claude Sonnet", "value": "claude-sonnet"},
                {"label": "Claude Haiku", "value": "claude-haiku"},
            ],
        }
        provider = ProviderModels.model_validate(data)
        assert provider.name == "Anthropic"
        assert len(provider.models) == 2
        assert provider.models[0].value == "claude-sonnet"

    def test_empty_models(self):
        provider = ProviderModels(name="Empty", models=[])
        assert provider.models == []


# ── ModelsResponse ─────────────────────────────────────────────────


class TestModelsResponse:
    def test_full_payload(self):
        data = {
            "providers": [
                {
                    "name": "Anthropic",
                    "models": [{"label": "Sonnet", "value": "sonnet"}],
                },
                {
                    "name": "OpenAI",
                    "models": [{"label": "GPT-4", "value": "gpt-4o"}],
                },
            ],
            "default_model": "sonnet",
        }
        resp = ModelsResponse.model_validate(data)
        assert resp.default_model == "sonnet"
        assert len(resp.providers) == 2
        assert resp.providers[1].models[0].value == "gpt-4o"


# ── OAuthProvider ──────────────────────────────────────────────────


class TestOAuthProvider:
    def test_minimal(self):
        provider = OAuthProvider(
            id=1,
            name="GitHub",
            issuer="https://github.com",
            authorization_endpoint="https://github.com/login/oauth/authorize",
            token_endpoint="https://github.com/login/oauth/access_token",
        )
        assert provider.name == "GitHub"
        assert provider.default_scopes is None
        assert provider.is_mcp is False
        assert provider.meta is None

    def test_full_payload(self):
        data = {
            "id": 2,
            "name": "Slack",
            "issuer": "https://slack.com",
            "authorization_endpoint": "https://slack.com/oauth/v2/authorize",
            "token_endpoint": "https://slack.com/api/oauth.v2.access",
            "default_scopes": ["chat:write", "channels:read"],
            "is_mcp": True,
            "meta": {"team_id": "T123"},
        }
        provider = OAuthProvider.model_validate(data)
        assert provider.is_mcp is True
        assert len(provider.default_scopes) == 2
        assert provider.meta["team_id"] == "T123"


# ── Page[T] ────────────────────────────────────────────────────────


class TestPage:
    def test_defaults(self):
        page = Page[Organization](items=[])
        assert page.total == 0
        assert page.page == 1
        assert page.size == 100
        assert page.pages == 1

    def test_with_organizations(self):
        page = Page[Organization].model_validate(
            {
                "items": [{"id": 1, "name": "Org1"}, {"id": 2, "name": "Org2"}],
                "total": 2,
                "page": 1,
                "size": 20,
                "pages": 1,
            }
        )
        assert len(page.items) == 2
        assert page.items[0].name == "Org1"

    def test_with_users(self):
        """Page[User] — new model works with generic pagination."""
        page = Page[User].model_validate(
            {
                "items": [{"id": 1, "github_user_id": "123", "github_username": "u1"}],
                "total": 1,
            }
        )
        assert page.items[0].github_username == "u1"

    def test_with_repositories(self):
        page = Page[Repository].model_validate(
            {
                "items": [
                    {
                        "id": 10,
                        "name": "repo",
                        "full_name": "org/repo",
                        "description": "Test",
                        "github_id": "R_abc",
                        "organization_id": 42,
                        "archived": False,
                        "setup_status": "completed",
                        "language": "Python",
                    }
                ],
                "total": 1,
            }
        )
        assert page.items[0].github_id == "R_abc"

    def test_with_agent_runs(self):
        page = Page[AgentRun].model_validate(
            {
                "items": [{"id": 1, "organization_id": 42, "status": "running"}],
                "total": 1,
            }
        )
        assert page.items[0].organization_id == 42


# ── Cross-model integration tests ──────────────────────────────────


class TestModelIntegration:
    """Test models work together as they would in real API responses."""

    def test_agent_run_with_nested_prs(self):
        """Full AgentRunResponse with nested GithubPullRequestResponse."""
        data = {
            "id": 999,
            "organization_id": 42,
            "status": "completed",
            "created_at": "2024-06-15T12:00:00Z",
            "web_url": "https://codegen.com/run/999",
            "result": "All tasks completed",
            "summary": "Refactored auth module",
            "source_type": "API",
            "github_pull_requests": [
                {
                    "id": 1,
                    "title": "Refactor auth",
                    "url": "https://github.com/org/repo/pull/10",
                    "created_at": "2024-06-15T12:05:00Z",
                    "head_branch_name": "refactor/auth",
                }
            ],
            "metadata": {"execution_id": "exec-123"},
        }
        run = AgentRun.model_validate(data)
        pr = run.github_pull_requests[0]
        assert pr.head_branch_name == "refactor/auth"
        assert run.metadata["execution_id"] == "exec-123"

    def test_organization_integrations_nested(self):
        """OrganizationIntegrationsResponse with nested IntegrationStatus."""
        data = {
            "organization_id": 42,
            "organization_name": "Acme Corp",
            "integrations": [
                {"integration_type": "github", "active": True, "installation_id": 1001},
                {"integration_type": "slack", "active": True, "token_id": 2002},
                {"integration_type": "linear", "active": False},
            ],
            "total_active_integrations": 2,
        }
        result = OrganizationIntegrations.model_validate(data)
        active = [i for i in result.integrations if i.active]
        assert len(active) == 2
        assert result.total_active_integrations == 2

    def test_models_response_nested(self):
        """ModelsResponse with nested ProviderModels and ModelOption."""
        data = {
            "providers": [
                {
                    "name": "Anthropic",
                    "models": [
                        {"label": "Claude 3.5 Sonnet", "value": "claude-3-5-sonnet"},
                        {"label": "Claude 3.5 Haiku", "value": "claude-3-5-haiku"},
                    ],
                },
            ],
            "default_model": "claude-3-5-sonnet",
        }
        resp = ModelsResponse.model_validate(data)
        all_models = [m for p in resp.providers for m in p.models]
        assert len(all_models) == 2
        assert any(m.value == resp.default_model for m in all_models)

    def test_all_models_json_roundtrip(self):
        """Every model survives model_dump → model_validate roundtrip."""
        instances = [
            PullRequest(id=1, url="https://example.com"),
            AgentRun(id=1, status="running"),
            AgentLog(agent_run_id=1, thought="thinking"),
            AgentRunWithLogs(id=1, logs=[{"agent_run_id": 1}]),
            User(id=1, github_user_id="123", github_username="u"),
            OrganizationSettings(),
            Organization(id=1, name="Org"),
            Repository(id=1, name="r", full_name="o/r"),
            EditPRResponse(success=True),
            CheckSuiteSettings(),
            IntegrationStatus(integration_type="gh", active=True),
            OrganizationIntegrations(
                organization_id=1,
                organization_name="O",
                integrations=[],
            ),
            WebhookConfig(),
            WebhookOverride(url="https://example.com"),
            SlackToken(token="t", message="m", expires_in_minutes=60),
            CLIRules(),
            SetupCommand(agent_run_id=1, status="ok", url="https://x.com"),
            SandboxLog(agent_run_id=1, status="ok", message="done"),
            ModelOption(label="L", value="V"),
            ProviderModels(name="P", models=[]),
            ModelsResponse(providers=[], default_model="m"),
            OAuthProvider(
                id=1,
                name="N",
                issuer="I",
                authorization_endpoint="A",
                token_endpoint="T",
            ),
            Page[AgentRun](items=[]),
        ]
        for instance in instances:
            cls = type(instance)
            data = instance.model_dump()
            rebuilt = cls.model_validate(data)
            assert rebuilt == instance, f"Roundtrip failed for {cls.__name__}"

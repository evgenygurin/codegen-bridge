"""Pydantic models for Codegen API responses.

Models are aligned with the official Codegen REST API v1:
https://docs.codegen.com/api-reference/overview

Naming follows the API schema:
- ``AgentRun`` → ``AgentRunResponse``
- ``PullRequest`` → ``GithubPullRequestResponse``
- ``AgentLog`` / ``AgentRunWithLogs`` → log retrieval
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# ── Enums as Literal unions ──────────────────────────────

SourceType = Literal[
    "LOCAL",
    "SLACK",
    "GITHUB",
    "GITHUB_CHECK_SUITE",
    "GITHUB_PR_REVIEW",
    "LINEAR",
    "API",
    "CHAT",
    "JIRA",
    "CLICKUP",
    "MONDAY",
    "SETUP_COMMANDS",
]

AgentType = Literal["codegen", "claude_code"]


# ── GitHub PR ────────────────────────────────────────────


class GithubPullRequestResponse(BaseModel):
    """GitHub PR created by an agent (matches API ``GithubPullRequestResponse``).

    The API returns ``id``, ``created_at``, ``title``, ``url``, and
    ``head_branch_name``.  The legacy fields ``number`` and ``state`` are
    kept for backward-compatibility with execution context and prompt builder.
    """

    id: int | None = None
    created_at: str | None = None
    title: str | None = None
    url: str | None = None
    head_branch_name: str | None = None

    # Legacy / backward-compat fields (not in current API schema)
    number: int | None = None
    state: str | None = None


# Backward-compatible alias used by execution context layer.
PullRequest = GithubPullRequestResponse


# ── Agent Run ────────────────────────────────────────────


class AgentRun(BaseModel):
    """Agent run summary (``AgentRunResponse`` in the API)."""

    id: int
    organization_id: int | None = None
    status: str | None = None
    created_at: str | None = None
    web_url: str | None = None
    result: str | None = None
    summary: str | None = None
    source_type: SourceType | str | None = None
    github_pull_requests: list[GithubPullRequestResponse] | None = None
    metadata: dict | None = None


# ── Agent Logs ───────────────────────────────────────────


class AgentLog(BaseModel):
    """Single agent log entry."""

    agent_run_id: int
    created_at: str | None = None
    tool_name: str | None = None
    message_type: str | None = None
    thought: str | None = None
    observation: str | dict | None = None
    tool_input: dict | None = None
    tool_output: str | dict | None = None


class AgentRunWithLogs(BaseModel):
    """Agent run with paginated logs."""

    id: int
    organization_id: int | None = None
    status: str | None = None
    created_at: str | None = None
    web_url: str | None = None
    result: str | None = None
    logs: list[AgentLog]
    total_logs: int = 0
    page: int | None = None
    size: int | None = None
    pages: int | None = None


# ── Ban / Unban / Remove-from-PR ─────────────────────────


class BanActionResponse(BaseModel):
    """Response from ban / unban / remove-from-pr endpoints.

    The API returns a simple JSON object (often ``{}`` on 200),
    so all fields are optional.
    """

    message: str | None = None
    status_code: int | None = None


# ── Organization & Repository ────────────────────────────


class Organization(BaseModel):
    """Codegen organization."""

    id: int
    name: str


class Repository(BaseModel):
    """GitHub repository in Codegen."""

    id: int
    name: str
    full_name: str
    language: str | None = None
    setup_status: str | None = None
    visibility: str | None = None


# ── Pagination ───────────────────────────────────────────


class Page[T](BaseModel):
    """Paginated response."""

    items: list[T]
    total: int = 0
    page: int = 1
    size: int = 100
    pages: int = 1

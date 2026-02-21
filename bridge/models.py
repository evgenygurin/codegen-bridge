"""Pydantic models for Codegen API responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AgentRun(BaseModel):
    """Agent run summary."""

    id: int
    status: str | None = None
    web_url: str | None = None
    result: str | None = None
    summary: str | None = None
    created_at: str | None = None
    source_type: str | None = None
    github_pull_requests: list[PullRequest] | None = None
    metadata: dict | None = None


class PullRequest(BaseModel):
    """GitHub PR created by agent."""

    url: str | None = None
    number: int | None = None
    title: str | None = None
    state: str | None = None


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
    status: str | None = None
    logs: list[AgentLog]
    total_logs: int = 0


class User(BaseModel):
    """Codegen user profile."""

    id: int
    github_user_id: str
    github_username: str
    email: str | None = None
    avatar_url: str | None = None
    full_name: str | None = None
    role: str | None = None
    is_admin: bool | None = None


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

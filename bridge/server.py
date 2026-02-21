"""FastMCP server for Codegen AI agent platform.

Hybrid architecture:
- 8 manual core tools with business logic (auto-detect repo_id, response formatting)
- ~13 auto-generated tools from OpenAPI spec via OpenAPIProvider
- 2 resources for monitoring
- 2 prompts for common workflows
"""

from __future__ import annotations

import json
import os
import subprocess
from contextlib import asynccontextmanager
from typing import Any, Literal

import httpx
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from bridge.client import CodegenClient
from bridge.openapi_utils import create_openapi_provider

# ── Lifespan ─────────────────────────────────────────────

_client: CodegenClient | None = None
_http_client: httpx.AsyncClient | None = None
_repo_cache: dict[str, int] = {}


@asynccontextmanager
async def _lifespan(server: FastMCP):
    """Manage lifecycle of HTTP clients and OpenAPI provider."""
    global _client, _http_client

    api_key = os.environ.get("CODEGEN_API_KEY", "")
    org_id_str = os.environ.get("CODEGEN_ORG_ID", "0")
    try:
        org_id = int(org_id_str)
    except ValueError:
        raise ToolError(
            "CODEGEN_ORG_ID must be a number. "
            "Set it in your environment or plugin config."
        ) from None
    if not api_key:
        raise ToolError("CODEGEN_API_KEY not set.")
    if not org_id:
        raise ToolError("CODEGEN_ORG_ID not set.")

    _client = CodegenClient(api_key=api_key, org_id=org_id)

    _http_client = httpx.AsyncClient(
        base_url="https://api.codegen.com",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )

    # Add OpenAPI provider for auto-generated tools
    try:
        provider = create_openapi_provider(_http_client, org_id)
        server.add_provider(provider)
    except Exception:
        pass  # OpenAPI provider is optional; manual tools always work

    try:
        yield {"client": _client, "org_id": org_id}
    finally:
        if _client is not None:
            await _client.close()
            _client = None
        if _http_client is not None:
            await _http_client.aclose()
            _http_client = None


# ── Server ───────────────────────────────────────────────

mcp = FastMCP(
    "Codegen Bridge",
    instructions="Tools for delegating tasks to Codegen AI agents. "
    "Create agent runs, monitor progress, view logs, and resume blocked runs.",
    lifespan=_lifespan,
)


# ── Helpers ──────────────────────────────────────────────


def _get_client(ctx: Context | None = None) -> CodegenClient:
    """Get Codegen client from lifespan context or global fallback."""
    if ctx is not None:
        lc = ctx.lifespan_context
        if lc and "client" in lc:
            return lc["client"]
    if _client is not None:
        return _client
    # Fallback: lazy init (for testing without lifespan)
    api_key = os.environ.get("CODEGEN_API_KEY", "")
    org_id_str = os.environ.get("CODEGEN_ORG_ID", "0")
    try:
        org_id = int(org_id_str)
    except ValueError:
        raise ToolError("CODEGEN_ORG_ID must be a number.") from None
    if not api_key:
        raise ToolError("CODEGEN_API_KEY not set.")
    if not org_id:
        raise ToolError("CODEGEN_ORG_ID not set.")
    return CodegenClient(api_key=api_key, org_id=org_id)


async def _detect_repo_id(ctx: Context | None = None) -> int | None:
    """Auto-detect repo_id from git remote origin."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        url = result.stdout.strip()
        full_name = ""
        if "github.com" in url:
            if url.startswith("git@"):
                full_name = url.split(":")[-1].removesuffix(".git")
            else:
                parts = url.rstrip("/").removesuffix(".git").split("/")
                if len(parts) >= 2:
                    full_name = f"{parts[-2]}/{parts[-1]}"

        if not full_name:
            return None

        if full_name in _repo_cache:
            return _repo_cache[full_name]

        client = _get_client(ctx)
        repos = await client.list_repos(limit=100)
        for repo in repos.items:
            _repo_cache[repo.full_name] = repo.id
            if repo.full_name == full_name:
                return repo.id

        return None

    except Exception:
        return None


# ── Core Tools (manual, with business logic) ─────────────


@mcp.tool(tags={"execution"})
async def codegen_create_run(
    ctx: Context,
    prompt: str,
    repo_id: int | None = None,
    model: str | None = None,
    agent_type: Literal["codegen", "claude_code"] = "claude_code",
) -> str:
    """Create a new Codegen agent run.

    The agent will execute the task in a cloud sandbox and may create a PR.

    Args:
        prompt: Task description for the agent (natural language, full context).
        repo_id: Repository ID. If not provided, auto-detected from git remote.
        model: LLM model to use. None = organization default.
        agent_type: Agent type — "codegen" or "claude_code".
    """
    client = _get_client(ctx)

    if repo_id is None:
        repo_id = await _detect_repo_id(ctx)
        if repo_id is None:
            raise ToolError(
                "Could not auto-detect repository. "
                "Provide repo_id explicitly or run from a git repository "
                "that is registered in your Codegen organization."
            )

    run = await client.create_run(
        prompt,
        repo_id=repo_id,
        model=model,
        agent_type=agent_type,
    )
    return json.dumps({
        "id": run.id,
        "status": run.status,
        "web_url": run.web_url,
    })


@mcp.tool(tags={"execution"})
async def codegen_get_run(ctx: Context, run_id: int) -> str:
    """Get agent run status, result, summary, and created PRs.

    Use this to poll for completion (check status field).
    """
    client = _get_client(ctx)
    run = await client.get_run(run_id)

    result: dict[str, Any] = {
        "id": run.id,
        "status": run.status,
        "web_url": run.web_url,
    }
    if run.result:
        result["result"] = run.result
    if run.summary:
        result["summary"] = run.summary
    if run.github_pull_requests:
        result["pull_requests"] = [
            {"url": pr.url, "number": pr.number, "title": pr.title, "state": pr.state}
            for pr in run.github_pull_requests
        ]
    return json.dumps(result)


@mcp.tool(tags={"execution"})
async def codegen_list_runs(
    ctx: Context,
    limit: int = 10,
    source_type: str | None = None,
) -> str:
    """List recent agent runs.

    Args:
        limit: Maximum number of runs to return (default 10).
        source_type: Filter by source — API, LOCAL, GITHUB, etc.
    """
    client = _get_client(ctx)
    page = await client.list_runs(limit=limit, source_type=source_type)
    return json.dumps({
        "total": page.total,
        "runs": [
            {
                "id": r.id,
                "status": r.status,
                "created_at": r.created_at,
                "web_url": r.web_url,
                "summary": r.summary,
            }
            for r in page.items
        ],
    })


@mcp.tool(tags={"execution"})
async def codegen_resume_run(
    ctx: Context,
    run_id: int,
    prompt: str,
    model: str | None = None,
) -> str:
    """Resume a paused or blocked agent run with new instructions.

    Args:
        run_id: Agent run ID to resume.
        prompt: New instructions or clarification for the agent.
        model: Optionally switch model for the resumed run.
    """
    client = _get_client(ctx)
    run = await client.resume_run(run_id, prompt, model=model)
    return json.dumps({
        "id": run.id,
        "status": run.status,
        "web_url": run.web_url,
    })


@mcp.tool(tags={"execution"})
async def codegen_stop_run(ctx: Context, run_id: int) -> str:
    """Stop a running agent. Use when a task needs to be cancelled.

    Args:
        run_id: Agent run ID to stop.
    """
    client = _get_client(ctx)
    run = await client.stop_run(run_id)
    return json.dumps({
        "id": run.id,
        "status": run.status,
        "web_url": run.web_url,
    })


@mcp.tool(tags={"monitoring"})
async def codegen_get_logs(
    ctx: Context,
    run_id: int,
    limit: int = 50,
    reverse: bool = True,
) -> str:
    """Get step-by-step agent execution logs.

    Shows agent thoughts, tool calls, and outputs for debugging.

    Args:
        run_id: Agent run ID.
        limit: Max log entries (default 50).
        reverse: If true, newest entries first.
    """
    client = _get_client(ctx)
    result = await client.get_logs(run_id, limit=limit, reverse=reverse)
    return json.dumps({
        "run_id": result.id,
        "status": result.status,
        "total_logs": result.total_logs,
        "logs": [
            {
                k: v
                for k, v in {
                    "thought": log.thought,
                    "tool_name": log.tool_name,
                    "tool_input": log.tool_input,
                    "tool_output": (
                        str(log.tool_output)[:500] if log.tool_output else None
                    ),
                    "created_at": log.created_at,
                }.items()
                if v is not None
            }
            for log in result.logs
        ],
    })


@mcp.tool(tags={"setup"})
async def codegen_list_orgs(ctx: Context) -> str:
    """List Codegen organizations the authenticated user belongs to."""
    client = _get_client(ctx)
    page = await client.list_orgs()
    return json.dumps({
        "organizations": [{"id": org.id, "name": org.name} for org in page.items],
    })


@mcp.tool(tags={"setup"})
async def codegen_list_repos(ctx: Context, limit: int = 50) -> str:
    """List repositories in the configured Codegen organization.

    Args:
        limit: Maximum repos to return (default 50).
    """
    client = _get_client(ctx)
    page = await client.list_repos(limit=limit)
    return json.dumps({
        "total": page.total,
        "repos": [
            {
                "id": r.id,
                "name": r.name,
                "full_name": r.full_name,
                "language": r.language,
                "setup_status": r.setup_status,
            }
            for r in page.items
        ],
    })


# ── Resources ────────────────────────────────────────────


@mcp.resource("codegen://config")
def get_config() -> str:
    """Current Codegen Bridge configuration and status."""
    org_id = os.environ.get("CODEGEN_ORG_ID", "not set")
    has_key = bool(os.environ.get("CODEGEN_API_KEY"))
    return json.dumps({
        "org_id": org_id,
        "api_base": "https://api.codegen.com/v1",
        "has_api_key": has_key,
    })


# ── Prompts ──────────────────────────────────────────────


@mcp.prompt()
def delegate_task(task_description: str, context: str = "") -> str:
    """Create a prompt for delegating a task to a Codegen agent."""
    parts = []
    if context:
        parts.append(f"## Context\n{context}\n")
    parts.append(f"## Task\n{task_description}\n")
    parts.append(
        "## Constraints\n"
        "- Create a branch from main (or the current default branch)\n"
        "- Run tests after each step\n"
        "- Commit with conventional commit messages\n"
        "- Create a PR when done\n"
    )
    return "\n".join(parts)


@mcp.prompt()
def monitor_runs() -> str:
    """Prompt for checking status of all active agent runs."""
    return (
        "List all active Codegen agent runs using codegen_list_runs. "
        "For any run with status 'running' or 'queued', show its progress. "
        "For 'paused' runs, show what the agent needs. "
        "For 'completed' runs, show PR links if available."
    )


# ── Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()

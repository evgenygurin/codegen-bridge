"""FastMCP server for Codegen AI agent platform."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from bridge.client import CodegenClient

mcp = FastMCP(
    "Codegen Bridge",
    instructions="Tools for delegating tasks to Codegen AI agents. "
    "Create agent runs, monitor progress, view logs, and resume blocked runs.",
)

# ── Config ──────────────────────────────────────────────────

_client: CodegenClient | None = None
_repo_cache: dict[str, int] = {}  # full_name -> repo_id


def _get_client() -> CodegenClient:
    """Get or create the Codegen API client."""
    global _client
    if _client is None:
        api_key = os.environ.get("CODEGEN_API_KEY", "")
        org_id_str = os.environ.get("CODEGEN_ORG_ID", "0")
        try:
            org_id = int(org_id_str)
        except ValueError:
            raise ToolError(
                "CODEGEN_ORG_ID must be a number. "
                "Set it in your environment or plugin .mcp.json."
            ) from None
        if not api_key:
            raise ToolError(
                "CODEGEN_API_KEY not set. "
                "Set it in your environment or plugin .mcp.json."
            )
        if not org_id:
            raise ToolError(
                "CODEGEN_ORG_ID not set. "
                "Set it in your environment or plugin .mcp.json."
            )
        _client = CodegenClient(api_key=api_key, org_id=org_id)
    return _client


async def _detect_repo_id() -> int | None:
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
        # Parse owner/repo from git URL
        # Handles: https://github.com/owner/repo.git, git@github.com:owner/repo.git
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

        # Check cache first
        if full_name in _repo_cache:
            return _repo_cache[full_name]

        # Lookup in Codegen repos
        client = _get_client()
        repos = await client.list_repos(limit=100)
        for repo in repos.items:
            _repo_cache[repo.full_name] = repo.id
            if repo.full_name == full_name:
                return repo.id

        return None

    except Exception:
        return None


# ── Tools ───────────────────────────────────────────────────


@mcp.tool(tags={"execution"})
async def codegen_create_run(
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
        agent_type: Agent type — "codegen" (Codegen's own) or "claude_code" (Claude Code).
    """
    client = _get_client()

    if repo_id is None:
        repo_id = await _detect_repo_id()
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
async def codegen_get_run(run_id: int) -> str:
    """Get agent run status, result, summary, and created PRs.

    Use this to poll for completion (check status field).
    """
    client = _get_client()
    run = await client.get_run(run_id)

    result: dict = {
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
    limit: int = 10,
    source_type: str | None = None,
) -> str:
    """List recent agent runs.

    Args:
        limit: Maximum number of runs to return (default 10).
        source_type: Filter by source — API, LOCAL, GITHUB, etc.
    """
    client = _get_client()
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
    client = _get_client()
    run = await client.resume_run(run_id, prompt, model=model)
    return json.dumps({
        "id": run.id,
        "status": run.status,
        "web_url": run.web_url,
    })


@mcp.tool(tags={"execution"})
async def codegen_get_logs(
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
    client = _get_client()
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
async def codegen_list_orgs() -> str:
    """List Codegen organizations the authenticated user belongs to."""
    client = _get_client()
    page = await client.list_orgs()
    return json.dumps({
        "organizations": [{"id": org.id, "name": org.name} for org in page.items],
    })


@mcp.tool(tags={"setup"})
async def codegen_list_repos(limit: int = 50) -> str:
    """List repositories in the configured Codegen organization.

    Args:
        limit: Maximum repos to return (default 50).
    """
    client = _get_client()
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


# ── Entry Point ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()

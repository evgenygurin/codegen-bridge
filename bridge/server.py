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
from bridge.context import ContextRegistry, PRInfo, TaskReport
from bridge.log_parser import parse_logs
from bridge.openapi_utils import create_openapi_provider
from bridge.prompt_builder import build_task_prompt

# ── Lifespan ─────────────────────────────────────────────

_client: CodegenClient | None = None
_http_client: httpx.AsyncClient | None = None
_repo_cache: dict[str, int] = {}
_registry: ContextRegistry | None = None


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
            "CODEGEN_ORG_ID must be a number. Set it in your environment or plugin config."
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

    global _registry
    _registry = ContextRegistry()

    try:
        yield {"client": _client, "org_id": org_id, "registry": _registry}
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
    execution_id: str | None = None,
    task_index: int | None = None,
) -> str:
    """Create a new Codegen agent run.

    The agent will execute the task in a cloud sandbox and may create a PR.

    Args:
        prompt: Task description for the agent (natural language, full context).
        repo_id: Repository ID. If not provided, auto-detected from git remote.
        model: LLM model to use. None = organization default.
        agent_type: Agent type — "codegen" or "claude_code".
        execution_id: Optional execution context ID for prompt enrichment.
        task_index: Task index within the execution (default: current_task_index).
    """
    client = _get_client(ctx)
    effective_prompt = prompt

    if execution_id is not None:
        registry = _get_registry(ctx)
        exec_ctx = registry.get(execution_id)
        if exec_ctx is not None:
            idx = task_index if task_index is not None else exec_ctx.current_task_index
            if idx < len(exec_ctx.tasks):
                effective_prompt = build_task_prompt(exec_ctx, idx)
                registry.update_task(
                    execution_id=execution_id,
                    task_index=idx,
                    status="running",
                )
            if repo_id is None and exec_ctx.repo_id is not None:
                repo_id = exec_ctx.repo_id

    if repo_id is None:
        repo_id = await _detect_repo_id(ctx)
        if repo_id is None:
            raise ToolError(
                "Could not auto-detect repository. "
                "Provide repo_id explicitly or run from a git repository "
                "that is registered in your Codegen organization."
            )

    run = await client.create_run(
        effective_prompt,
        repo_id=repo_id,
        model=model,
        agent_type=agent_type,
    )

    if execution_id is not None:
        registry = _get_registry(ctx)
        exec_ctx = registry.get(execution_id)
        if exec_ctx is not None:
            idx = task_index if task_index is not None else exec_ctx.current_task_index
            if idx < len(exec_ctx.tasks):
                registry.update_task(
                    execution_id=execution_id,
                    task_index=idx,
                    run_id=run.id,
                )

    return json.dumps(
        {
            "id": run.id,
            "status": run.status,
            "web_url": run.web_url,
        }
    )


@mcp.tool(tags={"execution"})
async def codegen_get_run(
    ctx: Context,
    run_id: int,
    execution_id: str | None = None,
    task_index: int | None = None,
) -> str:
    """Get agent run status, result, summary, and created PRs.

    Use this to poll for completion (check status field).

    Args:
        run_id: Agent run ID.
        execution_id: Optional execution context ID for auto-reporting.
        task_index: Task index within the execution (default: current_task_index).
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

    pr_list: list[dict[str, Any]] = []
    if run.github_pull_requests:
        pr_list = [
            {"url": pr.url, "number": pr.number, "title": pr.title, "state": pr.state}
            for pr in run.github_pull_requests
        ]
        result["pull_requests"] = pr_list

    # Auto-report back to execution context on terminal status
    if execution_id is not None and run.status in ("completed", "failed"):
        registry = _get_registry(ctx)
        exec_ctx = registry.get(execution_id)
        if exec_ctx is not None:
            idx = task_index if task_index is not None else exec_ctx.current_task_index
            if idx < len(exec_ctx.tasks):
                # Parse logs for structured data
                parsed = None
                try:
                    logs_result = await client.get_logs(run_id, limit=200)
                    parsed = parse_logs(logs_result.logs)
                    result["parsed_logs"] = {
                        "files_changed": parsed.files_changed,
                        "key_decisions": parsed.key_decisions,
                        "test_results": parsed.test_results,
                        "commands_run": parsed.commands_run,
                        "total_steps": parsed.total_steps,
                    }
                except Exception:
                    pass  # Log parsing is best-effort

                # Build TaskReport
                report = TaskReport(
                    summary=run.summary or run.result or "",
                    web_url=run.web_url or "",
                    pull_requests=[
                        PRInfo(
                            url=pr.get("url", ""),
                            number=pr.get("number", 0),
                            title=pr.get("title", ""),
                            state=pr.get("state", ""),
                        )
                        for pr in pr_list
                    ],
                    files_changed=parsed.files_changed if parsed else [],
                    key_decisions=parsed.key_decisions if parsed else [],
                    test_results=parsed.test_results if parsed else None,
                    agent_notes=parsed.agent_notes if parsed else None,
                    commands_run=parsed.commands_run if parsed else [],
                    total_steps=parsed.total_steps if parsed else 0,
                )

                task_status = "completed" if run.status == "completed" else "failed"
                registry.update_task(
                    execution_id=execution_id,
                    task_index=idx,
                    status=task_status,
                    report=report,
                )

                # Advance current_task_index if completed
                if run.status == "completed":
                    exec_ctx.current_task_index = idx + 1
                    registry._save(exec_ctx)

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
    return json.dumps(
        {
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
        }
    )


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
    return json.dumps(
        {
            "id": run.id,
            "status": run.status,
            "web_url": run.web_url,
        }
    )


@mcp.tool(tags={"execution"})
async def codegen_stop_run(ctx: Context, run_id: int) -> str:
    """Stop a running agent. Use when a task needs to be cancelled.

    Args:
        run_id: Agent run ID to stop.
    """
    client = _get_client(ctx)
    run = await client.stop_run(run_id)
    return json.dumps(
        {
            "id": run.id,
            "status": run.status,
            "web_url": run.web_url,
        }
    )


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
    return json.dumps(
        {
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
                        "tool_output": (str(log.tool_output)[:500] if log.tool_output else None),
                        "created_at": log.created_at,
                    }.items()
                    if v is not None
                }
                for log in result.logs
            ],
        }
    )


@mcp.tool(tags={"setup"})
async def codegen_list_orgs(ctx: Context) -> str:
    """List Codegen organizations the authenticated user belongs to."""
    client = _get_client(ctx)
    page = await client.list_orgs()
    return json.dumps(
        {
            "organizations": [{"id": org.id, "name": org.name} for org in page.items],
        }
    )


@mcp.tool(tags={"setup"})
async def codegen_list_repos(ctx: Context, limit: int = 50) -> str:
    """List repositories in the configured Codegen organization.

    Args:
        limit: Maximum repos to return (default 50).
    """
    client = _get_client(ctx)
    page = await client.list_repos(limit=limit)
    return json.dumps(
        {
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
        }
    )


def _get_registry(ctx: Context | None = None) -> ContextRegistry:
    """Get ContextRegistry from lifespan context or global fallback."""
    global _registry
    if ctx is not None:
        lc = ctx.lifespan_context
        if lc and "registry" in lc:
            return lc["registry"]
    if _registry is not None:
        return _registry
    _registry = ContextRegistry()
    return _registry


# ── Context Tools ────────────────────────────────────────


@mcp.tool(tags={"context"})
async def codegen_start_execution(
    ctx: Context,
    execution_id: str,
    goal: str,
    mode: Literal["plan", "adhoc"] = "adhoc",
    tasks: list[dict[str, str]] | None = None,
    tech_stack: list[str] | None = None,
    architecture: str | None = None,
    repo_structure: str | None = None,
) -> str:
    """Initialize an execution context, load agent rules and integrations.

    Call this at the start of a plan or ad-hoc task to set up full context
    that will be available to all subsequent agent runs.

    Args:
        execution_id: Unique identifier for the execution.
        goal: High-level goal description.
        mode: "plan" for multi-task plans, "adhoc" for single tasks.
        tasks: List of {"title": ..., "description": ...} for plan mode.
        tech_stack: Technologies used (e.g. ["Python", "FastAPI"]).
        architecture: Architecture description.
        repo_structure: Repository structure overview.
    """
    registry = _get_registry(ctx)
    client = _get_client(ctx)

    # Build task tuples from dicts
    task_tuples: list[tuple[str, str]] | None = None
    if tasks:
        task_tuples = [(t["title"], t.get("description", t["title"])) for t in tasks]

    # Build extra kwargs for ExecutionContext
    kwargs: dict[str, Any] = {}
    if tech_stack:
        kwargs["tech_stack"] = tech_stack
    if architecture:
        kwargs["architecture"] = architecture
    if repo_structure:
        kwargs["repo_structure"] = repo_structure

    # Detect repo
    repo_id = await _detect_repo_id(ctx)
    if repo_id is not None:
        kwargs["repo_id"] = repo_id

    # Load agent rules
    try:
        rules = await client.get_rules()
        org_rules = rules.get("organization_rules", "")
        user_prompt = rules.get("user_custom_prompt", "")
        combined = "\n\n".join(filter(None, [org_rules, user_prompt]))
        if combined:
            kwargs["agent_rules"] = combined
    except Exception:
        pass  # Rules are optional enrichment

    exec_ctx = registry.start_execution(
        execution_id=execution_id,
        mode=mode,
        goal=goal,
        tasks=task_tuples,
        **kwargs,
    )
    return json.dumps(
        {
            "execution_id": exec_ctx.id,
            "mode": exec_ctx.mode,
            "status": exec_ctx.status,
            "tasks": len(exec_ctx.tasks),
            "has_rules": bool(exec_ctx.agent_rules),
        }
    )


@mcp.tool(tags={"context"})
async def codegen_get_execution_context(
    ctx: Context,
    execution_id: str | None = None,
) -> str:
    """Get full execution context — active or by ID.

    Returns the complete execution state including tasks, rules, and metadata.

    Args:
        execution_id: Specific execution ID. If not provided, returns the active execution.
    """
    registry = _get_registry(ctx)

    exec_ctx = registry.get(execution_id) if execution_id else registry.get_active()

    if exec_ctx is None:
        return json.dumps({"error": "No execution context found"})

    return exec_ctx.model_dump_json(indent=2)


@mcp.tool(tags={"context"})
async def codegen_get_agent_rules(ctx: Context) -> str:
    """Fetch organization agent rules from the Codegen API.

    Returns organization-level rules and user custom prompts that should
    guide agent behavior.
    """
    client = _get_client(ctx)
    rules = await client.get_rules()
    return json.dumps(rules)


# ── Resources ────────────────────────────────────────────


@mcp.resource("codegen://config")
def get_config() -> str:
    """Current Codegen Bridge configuration and status."""
    org_id = os.environ.get("CODEGEN_ORG_ID", "not set")
    has_key = bool(os.environ.get("CODEGEN_API_KEY"))
    return json.dumps(
        {
            "org_id": org_id,
            "api_base": "https://api.codegen.com/v1",
            "has_api_key": has_key,
        }
    )


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

"""Agent run business logic.

``RunService`` owns all domain operations for agent runs: creation
(with prompt enrichment and repo detection), lifecycle management
(resume, stop), moderation (ban, unban, remove-from-pr), querying
(get, list), log retrieval, and result reporting.

Services never touch MCP ``Context`` — they use ``logging`` for
diagnostics and return plain dicts for the tool layer to serialise.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

from bridge.client import CodegenClient
from bridge.context import ContextRegistry, PRInfo, TaskReport
from bridge.helpers.pagination import (
    build_paginated_response,
    cursor_to_offset,
    next_cursor_or_none,
)
from bridge.helpers.repo_detection import RepoCache, detect_repo_id
from bridge.log_parser import parse_logs
from bridge.prompt_builder import build_task_prompt
from bridge.status import normalize_status

logger = logging.getLogger("bridge.services.runs")


# ── Shared serialisation helper ──────────────────────────────────


def build_run_result(run: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build the run result dict and PR list from an API run response.

    Returns ``(result_dict, pr_list)`` so both ``get_run`` and
    ``report_run_result`` can share the same serialisation logic.
    """
    result: dict[str, Any] = {
        "id": run.id,
        "status": run.status,
        "web_url": run.web_url,
    }
    if run.result:
        result["result"] = run.result
    if run.summary:
        result["summary"] = run.summary
    if run.source_type:
        result["source_type"] = run.source_type

    pr_list: list[dict[str, Any]] = []
    if run.github_pull_requests:
        pr_list = [
            {
                k: v
                for k, v in {
                    "url": pr.url,
                    "title": pr.title,
                    "head_branch_name": pr.head_branch_name,
                    "number": pr.number,
                    "state": pr.state,
                }.items()
                if v is not None
            }
            for pr in run.github_pull_requests
        ]
        result["pull_requests"] = pr_list

    return result, pr_list


class RunService:
    """Domain service for agent run operations.

    Constructed per-request via DI — receives pre-existing resources
    from the lifespan context.
    """

    def __init__(
        self,
        client: CodegenClient,
        registry: ContextRegistry,
        repo_cache: RepoCache,
    ) -> None:
        self._client = client
        self._registry = registry
        self._repo_cache = repo_cache

    # ── Pure reads ────────────────────────────────────────

    async def get_run(self, run_id: int) -> dict[str, Any]:
        """Fetch run status, result, summary, and created PRs."""
        run = await self._client.get_run(run_id)
        result, _pr_list = build_run_result(run)
        return result

    async def list_runs(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
        source_type: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """List recent agent runs with cursor-based pagination."""
        offset = cursor_to_offset(cursor)
        page = await self._client.list_runs(
            skip=offset, limit=limit, source_type=source_type, user_id=user_id
        )
        return build_paginated_response(
            items=[
                {
                    "id": r.id,
                    "status": r.status,
                    "created_at": r.created_at,
                    "web_url": r.web_url,
                    "summary": r.summary,
                    "source_type": r.source_type,
                }
                for r in page.items
            ],
            total=page.total,
            offset=offset,
            page_size=limit,
            items_key="runs",
        )

    async def get_logs(
        self,
        run_id: int,
        *,
        limit: int = 20,
        reverse: bool = True,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Fetch step-by-step agent execution logs with pagination."""
        offset = cursor_to_offset(cursor)
        result = await self._client.get_logs(
            run_id, skip=offset, limit=limit, reverse=reverse
        )
        return {
            "run_id": result.id,
            "status": result.status,
            "total_logs": result.total_logs,
            "next_cursor": next_cursor_or_none(offset, limit, result.total_logs or 0),
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
                        "message_type": log.message_type,
                        "created_at": log.created_at,
                    }.items()
                    if v is not None
                }
                for log in result.logs
            ],
        }

    # ── Prompt enrichment ─────────────────────────────────

    async def enrich_prompt(
        self,
        prompt: str,
        execution_id: str | None,
        task_index: int | None,
    ) -> tuple[str, int | None]:
        """Enrich prompt from execution context.

        Returns ``(effective_prompt, repo_id_from_context)``.
        If no execution context applies, returns the original prompt
        and ``None`` for repo_id.
        """
        if execution_id is None:
            return prompt, None

        exec_ctx = await self._registry.get(execution_id)
        if exec_ctx is None:
            return prompt, None

        idx = task_index if task_index is not None else exec_ctx.current_task_index
        effective_prompt = prompt
        repo_id: int | None = None

        if idx < len(exec_ctx.tasks):
            effective_prompt = build_task_prompt(exec_ctx, idx)
            await self._registry.update_task(
                execution_id=execution_id,
                task_index=idx,
                status="running",
            )

        if exec_ctx.repo_id is not None:
            repo_id = exec_ctx.repo_id

        return effective_prompt, repo_id

    # ── Repo detection ────────────────────────────────────

    async def detect_repo(self) -> int | None:
        """Auto-detect repository ID from git remote."""
        return await detect_repo_id(self._client, self._repo_cache)

    # ── Lifecycle ─────────────────────────────────────────

    async def create_run(
        self,
        prompt: str,
        *,
        repo_id: int,
        model: str | None = None,
        agent_type: Literal["codegen", "claude_code"] = "claude_code",
        images: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new agent run and return its core fields."""
        run = await self._client.create_run(
            prompt,
            repo_id=repo_id,
            model=model,
            agent_type=agent_type,
            images=images,
        )
        logger.info("Agent run created: id=%d, status=%s", run.id, run.status)
        return {"id": run.id, "status": run.status, "web_url": run.web_url}

    async def track_run_in_execution(
        self,
        run_id: int,
        execution_id: str | None,
        task_index: int | None,
    ) -> None:
        """Associate a run with an execution task."""
        if execution_id is None:
            return
        exec_ctx = await self._registry.get(execution_id)
        if exec_ctx is None:
            return
        idx = task_index if task_index is not None else exec_ctx.current_task_index
        if idx < len(exec_ctx.tasks):
            await self._registry.update_task(
                execution_id=execution_id,
                task_index=idx,
                run_id=run_id,
            )

    async def resume_run(
        self,
        run_id: int,
        prompt: str,
        *,
        model: str | None = None,
        images: list[str] | None = None,
    ) -> dict[str, Any]:
        """Resume a paused agent run with new instructions."""
        run = await self._client.resume_run(
            run_id, prompt, model=model, images=images
        )
        return {"id": run.id, "status": run.status, "web_url": run.web_url}

    async def stop_run(self, run_id: int) -> dict[str, Any]:
        """Stop a running agent."""
        run = await self._client.stop_run(run_id)
        effective_id = getattr(run, "id", None)
        if effective_id is None:
            effective_id = getattr(run, "agent_run_id", None)
        status = getattr(run, "status", None)
        web_url = getattr(run, "web_url", None)
        message = getattr(run, "message", None)
        return {
            "id": effective_id if effective_id is not None else run_id,
            "status": status,
            "web_url": web_url,
            **({"message": message} if message is not None else {}),
        }

    # ── Moderation ────────────────────────────────────────

    async def ban_run(
        self,
        run_id: int,
        *,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Ban all checks for a PR and stop all related agents."""
        result = await self._client.ban_run(
            run_id,
            before_card_order_id=before_card_order_id,
            after_card_order_id=after_card_order_id,
        )
        return {"run_id": run_id, "action": "banned", "message": result.message}

    async def unban_run(
        self,
        run_id: int,
        *,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Unban all checks for a PR."""
        result = await self._client.unban_run(
            run_id,
            before_card_order_id=before_card_order_id,
            after_card_order_id=after_card_order_id,
        )
        return {"run_id": run_id, "action": "unbanned", "message": result.message}

    async def remove_from_pr(
        self,
        run_id: int,
        *,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Remove Codegen from a PR (ban with user-friendly naming)."""
        result = await self._client.remove_from_pr(
            run_id,
            before_card_order_id=before_card_order_id,
            after_card_order_id=after_card_order_id,
        )
        return {
            "run_id": run_id,
            "action": "removed_from_pr",
            "message": result.message,
        }

    # ── Reporting ─────────────────────────────────────────

    async def report_run_result(
        self,
        run_id: int,
        execution_id: str,
        task_index: int | None = None,
    ) -> dict[str, Any]:
        """Report a completed/failed run back to an execution context.

        Fetches the run, parses logs, writes a ``TaskReport``, and
        advances ``current_task_index`` on success.  Non-terminal runs
        return data without mutation.
        """
        run = await self._client.get_run(run_id)
        result, pr_list = build_run_result(run)
        status = normalize_status(run.status)

        # Only report on terminal statuses
        if status not in ("completed", "failed", "error"):
            result["report_skipped"] = f"Run status is '{run.status}', not terminal"
            return result

        exec_ctx = await self._registry.get(execution_id)
        if exec_ctx is None:
            result["report_skipped"] = (
                f"Execution context '{execution_id}' not found"
            )
            return result

        idx = task_index if task_index is not None else exec_ctx.current_task_index
        if idx >= len(exec_ctx.tasks):
            result["report_skipped"] = f"Task index {idx} out of range"
            return result

        # Parse logs for structured data
        parsed = None
        try:
            logs_result = await self._client.get_logs(run_id, limit=100)
            parsed = parse_logs(logs_result.logs)
            result["parsed_logs"] = {
                "files_changed": parsed.files_changed,
                "key_decisions": parsed.key_decisions,
                "test_results": parsed.test_results,
                "commands_run": parsed.commands_run,
                "total_steps": parsed.total_steps,
            }
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("Log parsing failed for run %d: %s", run_id, exc)

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

        task_status: Literal["completed", "failed"] = (
            "completed" if status == "completed" else "failed"
        )
        await self._registry.update_task(
            execution_id=execution_id,
            task_index=idx,
            status=task_status,
            report=report,
        )

        # Advance current_task_index if completed
        if status == "completed":
            exec_ctx.current_task_index = idx + 1
            await self._registry._save(exec_ctx)

        result["reported"] = True
        result["task_index"] = idx
        result["task_status"] = task_status
        return result

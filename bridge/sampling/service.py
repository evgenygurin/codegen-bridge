"""Core sampling service — wraps ``ctx.sample()`` for domain operations.

``SamplingService`` is a stateless facade that composes configuration,
system prompts, and the FastMCP sampling API into high-level operations
(summarise a run, generate a task prompt, analyse logs).

Each public method:
1. Builds a user message from domain data.
2. Picks the right system prompt and temperature from ``SamplingConfig``
   (with per-operation overrides).
3. Calls ``ctx.sample()`` with retry on transient failures.
4. Returns a structured Pydantic schema (with ``__str__`` / ``__len__``
   for backward compatibility with callers that expect plain strings).

The service is intentionally *not* a singleton — tools create it from
DI-injected config + context on every call, keeping it thread-safe and
easy to test.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastmcp.server.context import Context
from pydantic import ValidationError

from bridge.sampling.config import SamplingConfig
from bridge.sampling.prompts import (
    system_prompt_execution_summary,
    system_prompt_log_analysis,
    system_prompt_run_summary,
    system_prompt_task_prompt_generator,
)
from bridge.sampling.schemas import (
    ExecutionSummary,
    LogAnalysis,
    RunSummary,
    TaskPrompt,
    _SamplingResult,
)

logger = logging.getLogger("bridge.sampling.service")

# Exception types considered transient (eligible for retry)
_TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
)


class SamplingService:
    """High-level sampling operations backed by ``ctx.sample()``.

    Args:
        ctx: The FastMCP tool context (carries the sampling transport).
        config: Tuneable parameters for temperature / tokens / models.
    """

    def __init__(self, ctx: Context, config: SamplingConfig | None = None) -> None:
        self._ctx = ctx
        self._cfg = config or SamplingConfig()

    # ── Public API ────────────────────────────────────────────

    async def summarise_run(self, run_data: dict[str, Any]) -> RunSummary:
        """Generate a human-readable summary for a single agent run.

        Args:
            run_data: Dict with keys like ``status``, ``result``, ``summary``,
                ``pull_requests``, ``parsed_logs``, etc.

        Returns:
            Structured ``RunSummary`` with text, key_findings, status_verdict.
        """
        operation = "summarise_run"
        user_msg = _format_run_for_summary(run_data)
        raw = await self._sample(
            user_msg,
            operation=operation,
            system_prompt=self._cfg.resolve_system_prompt(
                operation, system_prompt_run_summary()
            ),
            temperature=self._cfg.resolve_temperature(
                operation, self._cfg.summary_temperature
            ),
            max_tokens=self._cfg.resolve_max_tokens(
                operation, self._cfg.summary_max_tokens
            ),
        )
        return _parse_result(raw, RunSummary)

    async def summarise_execution(self, execution_json: str) -> ExecutionSummary:
        """Generate a summary for a full execution context.

        Args:
            execution_json: JSON-serialised ``ExecutionContext``.

        Returns:
            Structured ``ExecutionSummary`` with text, task counts, next_steps.
        """
        operation = "summarise_execution"
        user_msg = f"Here is the full execution context:\n\n```json\n{execution_json}\n```"
        raw = await self._sample(
            user_msg,
            operation=operation,
            system_prompt=self._cfg.resolve_system_prompt(
                operation, system_prompt_execution_summary()
            ),
            temperature=self._cfg.resolve_temperature(
                operation, self._cfg.summary_temperature
            ),
            max_tokens=self._cfg.resolve_max_tokens(
                operation, self._cfg.summary_max_tokens
            ),
        )
        return _parse_result(raw, ExecutionSummary)

    async def generate_task_prompt(
        self,
        goal: str,
        task_description: str,
        *,
        tech_stack: list[str] | None = None,
        architecture: str | None = None,
        completed_tasks: list[dict[str, Any]] | None = None,
    ) -> TaskPrompt:
        """Use the LLM to generate a detailed agent task prompt.

        Args:
            goal: High-level project goal.
            task_description: What this specific task should accomplish.
            tech_stack: Technologies in use.
            architecture: Architecture overview.
            completed_tasks: Summaries of previously completed tasks.

        Returns:
            Structured ``TaskPrompt`` with text, acceptance_criteria, constraints.
        """
        operation = "generate_task_prompt"
        user_msg = _format_task_generation_input(
            goal=goal,
            task_description=task_description,
            tech_stack=tech_stack,
            architecture=architecture,
            completed_tasks=completed_tasks,
        )
        raw = await self._sample(
            user_msg,
            operation=operation,
            system_prompt=self._cfg.resolve_system_prompt(
                operation, system_prompt_task_prompt_generator()
            ),
            temperature=self._cfg.resolve_temperature(
                operation, self._cfg.creative_temperature
            ),
            max_tokens=self._cfg.resolve_max_tokens(
                operation, self._cfg.prompt_max_tokens
            ),
        )
        return _parse_result(raw, TaskPrompt)

    async def analyse_logs(self, logs: list[dict[str, Any]]) -> LogAnalysis:
        """Analyse agent execution logs and produce insights.

        Args:
            logs: List of log entry dicts (thought, tool_name, tool_output, …).

        Returns:
            Structured ``LogAnalysis`` with text, severity, error_patterns, suggestions.
        """
        operation = "analyse_logs"
        user_msg = _format_logs_for_analysis(logs)
        raw = await self._sample(
            user_msg,
            operation=operation,
            system_prompt=self._cfg.resolve_system_prompt(
                operation, system_prompt_log_analysis()
            ),
            temperature=self._cfg.resolve_temperature(
                operation, self._cfg.summary_temperature
            ),
            max_tokens=self._cfg.resolve_max_tokens(
                operation, self._cfg.analysis_max_tokens
            ),
        )
        return _parse_result(raw, LogAnalysis)

    # ── Private helpers ───────────────────────────────────────

    async def _sample(
        self,
        user_message: str,
        *,
        operation: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Issue ``ctx.sample()`` with retry on transient failures.

        On non-transient failure (e.g. client doesn't support sampling)
        falls back to returning an explanatory placeholder so the tool
        never crashes.
        """
        max_attempts = 1 + self._cfg.retry.max_retries
        last_exc: BaseException | None = None

        for attempt in range(max_attempts):
            try:
                result = await self._ctx.sample(
                    messages=user_message,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model_preferences=self._cfg.model_preferences,
                )
                return result.text or ""
            except _TRANSIENT_ERRORS as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    delay = self._cfg.retry.backoff_base * (2**attempt)
                    logger.warning(
                        "Sampling attempt %d/%d failed (%s: %s), retrying in %.1fs",
                        attempt + 1,
                        max_attempts,
                        type(exc).__name__,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.warning(
                        "Sampling failed after %d attempts: %s", max_attempts, exc
                    )
            except (ValueError, RuntimeError) as exc:
                # Sampling not supported by the client or handler misconfigured
                logger.warning("Sampling unavailable: %s", exc)
                return f"[Sampling unavailable: {exc}]"
            except Exception as exc:
                logger.exception("Unexpected error during sampling")
                return f"[Sampling error: {exc}]"

        # All retries exhausted for transient errors
        return f"[Sampling failed after {max_attempts} attempts: {last_exc}]"


# ── Response parsing ──────────────────────────────────────────────


def _parse_result[T: _SamplingResult](raw: str, model: type[T]) -> T:
    """Attempt to parse LLM output as structured JSON into a schema.

    Falls back to populating only the ``text`` field when the LLM
    returns plain Markdown (the common case).  This makes structured
    fields available *when the LLM cooperates* without ever failing.
    """
    # Try JSON parse (LLM may return a JSON block)
    text_to_try = raw.strip()
    if text_to_try.startswith("```"):
        # Strip fenced code block markers
        lines = text_to_try.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text_to_try = "\n".join(lines).strip()

    if text_to_try.startswith("{"):
        try:
            data = json.loads(text_to_try)
            if isinstance(data, dict):
                # Ensure text field is populated
                if "text" not in data:
                    data["text"] = raw
                return model.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            pass  # Fall through to plain-text fallback

    # Plain text fallback — only populate the text field
    return model(text=raw)


# ── Message formatters (pure functions) ──────────────────────────


def _format_run_for_summary(run_data: dict[str, Any]) -> str:
    """Build the user message for ``summarise_run``."""
    parts: list[str] = ["Summarise the following agent run:\n"]

    for key in ("id", "status", "result", "summary", "web_url"):
        if key in run_data and run_data[key] is not None:
            parts.append(f"- **{key}**: {run_data[key]}")

    prs = run_data.get("pull_requests")
    if prs:
        parts.append("\n**Pull Requests:**")
        for pr in prs:
            parts.append(
                f"  - [{pr.get('title', 'PR')}]({pr.get('url', '')}) "
                f"(#{pr.get('number', '?')}, {pr.get('state', '?')})"
            )

    parsed = run_data.get("parsed_logs")
    if parsed:
        parts.append(f"\n**Parsed Logs:**\n```json\n{json.dumps(parsed, indent=2)}\n```")

    return "\n".join(parts)


def _format_task_generation_input(
    *,
    goal: str,
    task_description: str,
    tech_stack: list[str] | None,
    architecture: str | None,
    completed_tasks: list[dict[str, Any]] | None,
) -> str:
    """Build the user message for ``generate_task_prompt``."""
    parts: list[str] = [
        f"**Goal:** {goal}",
        f"**Task:** {task_description}",
    ]
    if tech_stack:
        parts.append(f"**Tech Stack:** {', '.join(tech_stack)}")
    if architecture:
        parts.append(f"**Architecture:** {architecture}")
    if completed_tasks:
        parts.append("\n**Previously Completed Tasks:**")
        for t in completed_tasks:
            parts.append(f"  - {t.get('title', '?')}: {t.get('summary', 'done')}")
    return "\n".join(parts)


def _format_logs_for_analysis(logs: list[dict[str, Any]]) -> str:
    """Build the user message for ``analyse_logs``."""
    if not logs:
        return "No logs available for analysis."

    parts: list[str] = [f"Analyse the following {len(logs)} agent log entries:\n"]
    for i, log in enumerate(logs[:50], 1):  # cap at 50 entries to stay within limits
        entry_parts: list[str] = [f"### Step {i}"]
        if log.get("thought"):
            entry_parts.append(f"**Thought:** {log['thought']}")
        if log.get("tool_name"):
            entry_parts.append(f"**Tool:** {log['tool_name']}")
        if log.get("tool_output"):
            output = str(log["tool_output"])[:300]
            entry_parts.append(f"**Output:** {output}")
        parts.append("\n".join(entry_parts))

    if len(logs) > 50:
        parts.append(f"\n… and {len(logs) - 50} more entries (truncated).")

    return "\n\n".join(parts)

"""Structured output schemas for sampling operations.

Each schema provides typed access to LLM-generated content while
maintaining backward compatibility via ``__len__`` and ``__str__``
(callers that expect a plain string still work).

The service attempts to parse JSON from the LLM response into these
models.  When parsing fails it falls back to populating only the
``text`` field, so structured fields degrade gracefully to empty
defaults rather than raising exceptions.

Usage::

    result = await service.summarise_run(run_data)
    # As a string (backward compat):
    print(str(result))           # full text
    print(len(result))           # text length
    # Structured access:
    for finding in result.key_findings:
        print(finding)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class _SamplingResult(BaseModel):
    """Base class for all sampling result schemas.

    Provides ``__str__`` and ``__len__`` so callers that previously
    received a plain string continue to work transparently.
    """

    text: str = ""

    def __str__(self) -> str:
        return self.text

    def __len__(self) -> int:
        return len(self.text)


class RunSummary(_SamplingResult):
    """Structured result from ``SamplingService.summarise_run``.

    Fields:
        text: Full Markdown summary text.
        key_findings: Bullet-point highlights extracted from the summary.
        status_verdict: One-sentence status assessment.
    """

    key_findings: list[str] = Field(default_factory=list)
    status_verdict: str = ""


class ExecutionSummary(_SamplingResult):
    """Structured result from ``SamplingService.summarise_execution``.

    Fields:
        text: Full Markdown summary text.
        tasks_completed: Number of completed tasks (if determinable).
        tasks_failed: Number of failed tasks (if determinable).
        next_steps: Suggested next actions.
    """

    tasks_completed: int | None = None
    tasks_failed: int | None = None
    next_steps: list[str] = Field(default_factory=list)


class TaskPrompt(_SamplingResult):
    """Structured result from ``SamplingService.generate_task_prompt``.

    Fields:
        text: Full generated prompt text.
        acceptance_criteria: Extracted acceptance criteria items.
        constraints: Extracted constraints / guardrails.
    """

    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class LogAnalysis(_SamplingResult):
    """Structured result from ``SamplingService.analyse_logs``.

    Fields:
        text: Full Markdown analysis text.
        severity: Overall severity assessment (info/warning/error/critical).
        error_patterns: Identified error patterns.
        suggestions: Improvement suggestions.
    """

    severity: str = "info"
    error_patterns: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)

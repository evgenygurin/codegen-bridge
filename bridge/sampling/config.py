"""Configuration models for the sampling subsystem.

Provides ``SamplingConfig`` (stored in lifespan context, accessed via DI),
``RetryConfig`` for resilient sampling calls, and ``OperationConfig`` for
per-operation parameter overrides.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetryConfig(BaseModel):
    """Retry policy for ``ctx.sample()`` calls.

    When the initial sampling call fails with a transient error (e.g.
    network timeout, rate limit), the service retries up to ``max_retries``
    times with exponential backoff starting at ``backoff_base`` seconds.
    """

    max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum number of retry attempts after the initial call.",
    )
    backoff_base: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Base backoff in seconds (doubles per retry).",
    )


class OperationConfig(BaseModel):
    """Per-operation overrides for sampling parameters.

    Any field set to ``None`` falls through to the parent
    ``SamplingConfig`` default. Useful for tuning one operation
    without affecting others.

    Example::

        SamplingConfig(
            operation_overrides={
                "summarise_run": OperationConfig(temperature=0.1, max_tokens=256),
            }
        )
    """

    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override temperature for this operation.",
    )
    max_tokens: int | None = Field(
        default=None,
        gt=0,
        description="Override max tokens for this operation.",
    )
    system_prompt_override: str | None = Field(
        default=None,
        description="Replace the default system prompt for this operation.",
    )


class SamplingConfig(BaseModel):
    """Tuneable knobs for server-side sampling calls.

    Stored in the lifespan context so every tool can pull it via DI.
    Override at startup via environment or constructor kwargs.
    """

    # LLM generation parameters
    default_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Default temperature for sampling requests.",
    )
    summary_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Lower temperature for factual summaries.",
    )
    creative_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Higher temperature for prompt/task generation.",
    )

    # Token limits
    summary_max_tokens: int = Field(
        default=512,
        gt=0,
        description="Max tokens for summary generation.",
    )
    prompt_max_tokens: int = Field(
        default=1024,
        gt=0,
        description="Max tokens for prompt generation.",
    )
    analysis_max_tokens: int = Field(
        default=768,
        gt=0,
        description="Max tokens for log analysis.",
    )

    # Model preferences (hints — not guaranteed)
    model_preferences: list[str] | None = Field(
        default=None,
        description="Ordered model preference hints, e.g. ['claude-sonnet-4-20250514'].",
    )

    # Retry policy for transient failures
    retry: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Retry configuration for transient sampling failures.",
    )

    # Per-operation overrides (keyed by operation name)
    operation_overrides: dict[str, OperationConfig] = Field(
        default_factory=dict,
        description=(
            "Per-operation config overrides. Keys are operation names: "
            "'summarise_run', 'summarise_execution', 'generate_task_prompt', 'analyse_logs'."
        ),
    )

    def resolve_temperature(self, operation: str, default: float) -> float:
        """Get effective temperature for an operation, applying overrides."""
        override = self.operation_overrides.get(operation)
        if override and override.temperature is not None:
            return override.temperature
        return default

    def resolve_max_tokens(self, operation: str, default: int) -> int:
        """Get effective max tokens for an operation, applying overrides."""
        override = self.operation_overrides.get(operation)
        if override and override.max_tokens is not None:
            return override.max_tokens
        return default

    def resolve_system_prompt(self, operation: str, default: str) -> str:
        """Get effective system prompt for an operation, applying overrides."""
        override = self.operation_overrides.get(operation)
        if override and override.system_prompt_override is not None:
            return override.system_prompt_override
        return default

"""Configuration models for the sampling subsystem."""

from __future__ import annotations

from pydantic import BaseModel, Field


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

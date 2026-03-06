"""Tests for bridge.sampling.config — SamplingConfig, RetryConfig, OperationConfig."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bridge.sampling.config import OperationConfig, RetryConfig, SamplingConfig


class TestSamplingConfigDefaults:
    """Default values are sensible and within bounds."""

    def test_default_construction(self):
        cfg = SamplingConfig()
        assert cfg.default_temperature == 0.3
        assert cfg.summary_temperature == 0.2
        assert cfg.creative_temperature == 0.7
        assert cfg.summary_max_tokens == 512
        assert cfg.prompt_max_tokens == 1024
        assert cfg.analysis_max_tokens == 768
        assert cfg.model_preferences is None

    def test_custom_values(self):
        cfg = SamplingConfig(
            default_temperature=0.5,
            summary_max_tokens=256,
            model_preferences=["claude-sonnet-4-20250514", "gpt-4o"],
        )
        assert cfg.default_temperature == 0.5
        assert cfg.summary_max_tokens == 256
        assert cfg.model_preferences == ["claude-sonnet-4-20250514", "gpt-4o"]


class TestSamplingConfigValidation:
    """Pydantic validation catches bad values."""

    def test_temperature_too_low(self):
        with pytest.raises(ValidationError):
            SamplingConfig(default_temperature=-0.1)

    def test_temperature_too_high(self):
        with pytest.raises(ValidationError):
            SamplingConfig(default_temperature=1.5)

    def test_max_tokens_zero(self):
        with pytest.raises(ValidationError):
            SamplingConfig(summary_max_tokens=0)

    def test_max_tokens_negative(self):
        with pytest.raises(ValidationError):
            SamplingConfig(prompt_max_tokens=-10)

    def test_boundary_temperature_valid(self):
        """Edge cases: 0.0 and 1.0 are both valid."""
        cfg_low = SamplingConfig(default_temperature=0.0)
        cfg_high = SamplingConfig(default_temperature=1.0)
        assert cfg_low.default_temperature == 0.0
        assert cfg_high.default_temperature == 1.0


class TestSamplingConfigSerialization:
    """Model can round-trip through JSON."""

    def test_json_round_trip(self):
        original = SamplingConfig(
            creative_temperature=0.9,
            model_preferences=["claude-opus-4-20250514"],
        )
        json_str = original.model_dump_json()
        restored = SamplingConfig.model_validate_json(json_str)
        assert restored.creative_temperature == original.creative_temperature
        assert restored.model_preferences == original.model_preferences


# ── RetryConfig tests ─────────────────────────────────────


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 2
        assert cfg.backoff_base == 1.0

    def test_custom_values(self):
        cfg = RetryConfig(max_retries=5, backoff_base=0.5)
        assert cfg.max_retries == 5
        assert cfg.backoff_base == 0.5

    def test_zero_retries(self):
        cfg = RetryConfig(max_retries=0)
        assert cfg.max_retries == 0

    def test_negative_retries_invalid(self):
        with pytest.raises(ValidationError):
            RetryConfig(max_retries=-1)

    def test_retries_too_high(self):
        with pytest.raises(ValidationError):
            RetryConfig(max_retries=10)

    def test_backoff_too_low(self):
        with pytest.raises(ValidationError):
            RetryConfig(backoff_base=0.01)

    def test_json_round_trip(self):
        original = RetryConfig(max_retries=3, backoff_base=2.0)
        restored = RetryConfig.model_validate_json(original.model_dump_json())
        assert restored.max_retries == original.max_retries
        assert restored.backoff_base == original.backoff_base


# ── OperationConfig tests ────────────────────────────────


class TestOperationConfig:
    def test_defaults_all_none(self):
        cfg = OperationConfig()
        assert cfg.temperature is None
        assert cfg.max_tokens is None
        assert cfg.system_prompt_override is None

    def test_partial_override(self):
        cfg = OperationConfig(temperature=0.1)
        assert cfg.temperature == 0.1
        assert cfg.max_tokens is None

    def test_full_override(self):
        cfg = OperationConfig(
            temperature=0.5,
            max_tokens=2048,
            system_prompt_override="Custom prompt",
        )
        assert cfg.temperature == 0.5
        assert cfg.max_tokens == 2048
        assert cfg.system_prompt_override == "Custom prompt"

    def test_temperature_validation(self):
        with pytest.raises(ValidationError):
            OperationConfig(temperature=2.0)

    def test_max_tokens_validation(self):
        with pytest.raises(ValidationError):
            OperationConfig(max_tokens=0)


# ── SamplingConfig resolver tests ────────────────────────


class TestSamplingConfigResolvers:
    """Test the resolve_* methods for per-operation overrides."""

    def test_resolve_temperature_with_override(self):
        cfg = SamplingConfig(
            operation_overrides={"op1": OperationConfig(temperature=0.1)}
        )
        assert cfg.resolve_temperature("op1", 0.5) == 0.1

    def test_resolve_temperature_without_override(self):
        cfg = SamplingConfig()
        assert cfg.resolve_temperature("op1", 0.5) == 0.5

    def test_resolve_temperature_none_override(self):
        cfg = SamplingConfig(
            operation_overrides={"op1": OperationConfig(temperature=None)}
        )
        assert cfg.resolve_temperature("op1", 0.5) == 0.5

    def test_resolve_max_tokens_with_override(self):
        cfg = SamplingConfig(
            operation_overrides={"op1": OperationConfig(max_tokens=2048)}
        )
        assert cfg.resolve_max_tokens("op1", 512) == 2048

    def test_resolve_max_tokens_without_override(self):
        cfg = SamplingConfig()
        assert cfg.resolve_max_tokens("op1", 512) == 512

    def test_resolve_system_prompt_with_override(self):
        cfg = SamplingConfig(
            operation_overrides={"op1": OperationConfig(system_prompt_override="custom")}
        )
        assert cfg.resolve_system_prompt("op1", "default") == "custom"

    def test_resolve_system_prompt_without_override(self):
        cfg = SamplingConfig()
        assert cfg.resolve_system_prompt("op1", "default") == "default"


class TestSamplingConfigWithRetryAndOverrides:
    """Integration test: SamplingConfig with retry and operation overrides."""

    def test_full_config_construction(self):
        cfg = SamplingConfig(
            summary_temperature=0.15,
            retry=RetryConfig(max_retries=3, backoff_base=0.5),
            operation_overrides={
                "summarise_run": OperationConfig(temperature=0.05, max_tokens=256),
                "analyse_logs": OperationConfig(max_tokens=2048),
            },
        )
        assert cfg.retry.max_retries == 3
        assert cfg.retry.backoff_base == 0.5
        assert cfg.resolve_temperature("summarise_run", cfg.summary_temperature) == 0.05
        assert cfg.resolve_max_tokens("summarise_run", cfg.summary_max_tokens) == 256
        assert cfg.resolve_max_tokens("analyse_logs", cfg.analysis_max_tokens) == 2048
        assert cfg.resolve_temperature("analyse_logs", cfg.summary_temperature) == 0.15

    def test_json_round_trip_with_all_fields(self):
        original = SamplingConfig(
            retry=RetryConfig(max_retries=1),
            operation_overrides={
                "summarise_run": OperationConfig(temperature=0.1),
            },
        )
        json_str = original.model_dump_json()
        restored = SamplingConfig.model_validate_json(json_str)
        assert restored.retry.max_retries == 1
        assert restored.operation_overrides["summarise_run"].temperature == 0.1

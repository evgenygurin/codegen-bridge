"""Tests for bridge.sampling.config — SamplingConfig model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bridge.sampling.config import SamplingConfig


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

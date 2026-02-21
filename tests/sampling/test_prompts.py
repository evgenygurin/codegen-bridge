"""Tests for bridge.sampling.prompts — system prompt templates."""

from __future__ import annotations

from bridge.sampling.prompts import (
    system_prompt_execution_summary,
    system_prompt_log_analysis,
    system_prompt_run_summary,
    system_prompt_task_prompt_generator,
)


class TestSystemPrompts:
    """Every system prompt is a non-empty string with expected content."""

    def test_run_summary_prompt(self):
        prompt = system_prompt_run_summary()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        assert "summary" in prompt.lower() or "summarise" in prompt.lower()

    def test_execution_summary_prompt(self):
        prompt = system_prompt_execution_summary()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        assert "execution" in prompt.lower() or "task" in prompt.lower()

    def test_task_prompt_generator(self):
        prompt = system_prompt_task_prompt_generator()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        assert "prompt" in prompt.lower()

    def test_log_analysis_prompt(self):
        prompt = system_prompt_log_analysis()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        assert "log" in prompt.lower()

    def test_all_prompts_are_distinct(self):
        """Each prompt template is unique."""
        prompts = [
            system_prompt_run_summary(),
            system_prompt_execution_summary(),
            system_prompt_task_prompt_generator(),
            system_prompt_log_analysis(),
        ]
        assert len(set(prompts)) == len(prompts)

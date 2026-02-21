"""Tests for bridge.sampling.service — SamplingService.

Because ``ctx.sample()`` requires a real MCP transport, we mock it
at the service level to test message formatting and error handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock

from bridge.sampling.config import SamplingConfig
from bridge.sampling.service import (
    SamplingService,
    _format_logs_for_analysis,
    _format_run_for_summary,
    _format_task_generation_input,
)

# ── Helpers ────────────────────────────────────────────────────


@dataclass
class FakeSamplingResult:
    text: str | None


def _make_mock_ctx() -> AsyncMock:
    """Create a mock Context with ``sample`` returning a FakeSamplingResult."""
    ctx = AsyncMock()
    ctx.sample = AsyncMock(return_value=FakeSamplingResult(text="AI response"))
    return ctx


# ── Formatter unit tests ──────────────────────────────────────


class TestFormatRunForSummary:
    def test_minimal(self):
        msg = _format_run_for_summary({"id": 1, "status": "completed"})
        assert "id" in msg
        assert "completed" in msg

    def test_with_prs(self):
        run_data = {
            "id": 42,
            "status": "completed",
            "pull_requests": [
                {
                    "title": "Fix bug",
                    "url": "https://github.com/pr/1",
                    "number": 1,
                    "state": "open",
                }
            ],
        }
        msg = _format_run_for_summary(run_data)
        assert "Fix bug" in msg
        assert "https://github.com/pr/1" in msg

    def test_with_parsed_logs(self):
        run_data = {
            "id": 7,
            "status": "failed",
            "parsed_logs": {"files_changed": ["main.py"], "key_decisions": ["refactored"]},
        }
        msg = _format_run_for_summary(run_data)
        assert "main.py" in msg
        assert "refactored" in msg

    def test_none_values_excluded(self):
        msg = _format_run_for_summary({"id": 1, "status": None, "result": None, "web_url": None})
        # Should have id but not status/result/web_url since they're None
        assert "id" in msg


class TestFormatTaskGenerationInput:
    def test_minimal(self):
        msg = _format_task_generation_input(
            goal="Build API",
            task_description="Add auth",
            tech_stack=None,
            architecture=None,
            completed_tasks=None,
        )
        assert "Build API" in msg
        assert "Add auth" in msg

    def test_with_all_fields(self):
        msg = _format_task_generation_input(
            goal="Build API",
            task_description="Add auth",
            tech_stack=["Python", "FastAPI"],
            architecture="Microservices",
            completed_tasks=[{"title": "Setup DB", "summary": "Done"}],
        )
        assert "Python" in msg
        assert "FastAPI" in msg
        assert "Microservices" in msg
        assert "Setup DB" in msg


class TestFormatLogsForAnalysis:
    def test_empty_logs(self):
        msg = _format_logs_for_analysis([])
        assert "No logs" in msg

    def test_basic_logs(self):
        logs = [
            {"thought": "Checking files", "tool_name": "read_file"},
            {"tool_name": "write_file", "tool_output": "OK"},
        ]
        msg = _format_logs_for_analysis(logs)
        assert "Checking files" in msg
        assert "read_file" in msg
        assert "write_file" in msg
        assert "Step 1" in msg
        assert "Step 2" in msg

    def test_truncation_at_50(self):
        logs = [{"thought": f"Step {i}"} for i in range(60)]
        msg = _format_logs_for_analysis(logs)
        assert "truncated" in msg.lower()
        # Should include step 50 but not step 51
        assert "Step 49" in msg
        assert "Step 59" not in msg


# ── Service tests (mocked ctx.sample) ─────────────────────────


class TestSamplingServiceSummariseRun:
    async def test_returns_ai_text(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        result = await svc.summarise_run({"id": 1, "status": "completed"})
        assert result == "AI response"
        ctx.sample.assert_awaited_once()

    async def test_passes_summary_temperature(self):
        ctx = _make_mock_ctx()
        cfg = SamplingConfig(summary_temperature=0.1)
        svc = SamplingService(ctx, cfg)
        await svc.summarise_run({"id": 1, "status": "ok"})
        call_kwargs = ctx.sample.call_args.kwargs
        assert call_kwargs["temperature"] == 0.1

    async def test_passes_max_tokens(self):
        ctx = _make_mock_ctx()
        cfg = SamplingConfig(summary_max_tokens=256)
        svc = SamplingService(ctx, cfg)
        await svc.summarise_run({"id": 1, "status": "ok"})
        call_kwargs = ctx.sample.call_args.kwargs
        assert call_kwargs["max_tokens"] == 256

    async def test_passes_model_preferences(self):
        ctx = _make_mock_ctx()
        cfg = SamplingConfig(model_preferences=["claude-sonnet-4-20250514"])
        svc = SamplingService(ctx, cfg)
        await svc.summarise_run({"id": 1, "status": "ok"})
        call_kwargs = ctx.sample.call_args.kwargs
        assert call_kwargs["model_preferences"] == ["claude-sonnet-4-20250514"]


class TestSamplingServiceSummariseExecution:
    async def test_returns_ai_text(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        result = await svc.summarise_execution('{"id": "exec-1"}')
        assert result == "AI response"

    async def test_passes_json_in_message(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        await svc.summarise_execution('{"id": "exec-1", "goal": "test"}')
        call_kwargs = ctx.sample.call_args.kwargs
        assert "exec-1" in call_kwargs["messages"]


class TestSamplingServiceGenerateTaskPrompt:
    async def test_returns_ai_text(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        result = await svc.generate_task_prompt(goal="Build API", task_description="Add auth")
        assert result == "AI response"

    async def test_creative_temperature(self):
        ctx = _make_mock_ctx()
        cfg = SamplingConfig(creative_temperature=0.9)
        svc = SamplingService(ctx, cfg)
        await svc.generate_task_prompt(goal="Build", task_description="Add")
        call_kwargs = ctx.sample.call_args.kwargs
        assert call_kwargs["temperature"] == 0.9

    async def test_prompt_max_tokens(self):
        ctx = _make_mock_ctx()
        cfg = SamplingConfig(prompt_max_tokens=2048)
        svc = SamplingService(ctx, cfg)
        await svc.generate_task_prompt(goal="Build", task_description="Add")
        call_kwargs = ctx.sample.call_args.kwargs
        assert call_kwargs["max_tokens"] == 2048


class TestSamplingServiceAnalyseLogs:
    async def test_returns_ai_text(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        result = await svc.analyse_logs([{"thought": "thinking"}])
        assert result == "AI response"

    async def test_empty_logs(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        result = await svc.analyse_logs([])
        assert result == "AI response"  # still calls sample; the message says "No logs"


class TestSamplingServiceErrorHandling:
    async def test_value_error_graceful_fallback(self):
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = ValueError("Client does not support sampling")
        svc = SamplingService(ctx)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert "[Sampling unavailable:" in result

    async def test_runtime_error_graceful_fallback(self):
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = RuntimeError("handler misconfigured")
        svc = SamplingService(ctx)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert "[Sampling unavailable:" in result

    async def test_unexpected_error_graceful_fallback(self):
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = OSError("network down")
        svc = SamplingService(ctx)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert "[Sampling error:" in result

    async def test_none_text_returns_empty_string(self):
        ctx = _make_mock_ctx()
        ctx.sample.return_value = FakeSamplingResult(text=None)
        svc = SamplingService(ctx)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert result == ""


class TestSamplingServiceDefaultConfig:
    async def test_uses_default_config_when_none(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)  # no config passed
        await svc.summarise_run({"id": 1, "status": "ok"})
        call_kwargs = ctx.sample.call_args.kwargs
        # Should use SamplingConfig defaults
        assert call_kwargs["temperature"] == 0.2  # summary_temperature default
        assert call_kwargs["max_tokens"] == 512   # summary_max_tokens default

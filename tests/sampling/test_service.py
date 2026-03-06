"""Tests for bridge.sampling.service — SamplingService.

Because ``ctx.sample()`` requires a real MCP transport, we mock it
at the service level to test message formatting, structured output
parsing, retry logic, and error handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock

from bridge.sampling.config import OperationConfig, RetryConfig, SamplingConfig
from bridge.sampling.schemas import ExecutionSummary, LogAnalysis, RunSummary, TaskPrompt
from bridge.sampling.service import (
    SamplingService,
    _format_logs_for_analysis,
    _format_run_for_summary,
    _format_task_generation_input,
    _parse_result,
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


# ── Structured output parsing tests ──────────────────────────


class TestParseResult:
    """Test the _parse_result function for structured output parsing."""

    def test_plain_text_fallback(self):
        result = _parse_result("Some markdown summary", RunSummary)
        assert isinstance(result, RunSummary)
        assert result.text == "Some markdown summary"
        assert result.key_findings == []
        assert result.status_verdict == ""

    def test_json_parsing(self):
        raw = '{"text": "Summary", "key_findings": ["found A", "found B"], "status_verdict": "ok"}'
        result = _parse_result(raw, RunSummary)
        assert isinstance(result, RunSummary)
        assert result.text == "Summary"
        assert result.key_findings == ["found A", "found B"]
        assert result.status_verdict == "ok"

    def test_json_without_text_field(self):
        raw = '{"key_findings": ["item1"], "status_verdict": "good"}'
        result = _parse_result(raw, RunSummary)
        assert isinstance(result, RunSummary)
        assert result.text == raw  # text populated from raw
        assert result.key_findings == ["item1"]

    def test_fenced_code_block(self):
        raw = '```json\n{"text": "Summary", "severity": "warning"}\n```'
        result = _parse_result(raw, LogAnalysis)
        assert isinstance(result, LogAnalysis)
        assert result.text == "Summary"
        assert result.severity == "warning"

    def test_invalid_json_fallback(self):
        raw = "{not valid json"
        result = _parse_result(raw, TaskPrompt)
        assert isinstance(result, TaskPrompt)
        assert result.text == "{not valid json"
        assert result.acceptance_criteria == []

    def test_execution_summary_parsing(self):
        raw = '{"text": "Done", "tasks_completed": 3, "tasks_failed": 1, "next_steps": ["deploy"]}'
        result = _parse_result(raw, ExecutionSummary)
        assert result.tasks_completed == 3
        assert result.tasks_failed == 1
        assert result.next_steps == ["deploy"]

    def test_log_analysis_parsing(self):
        raw = (
            '{"text": "Analysis", "severity": "error",'
            ' "error_patterns": ["OOM"], "suggestions": ["add memory"]}'
        )
        result = _parse_result(raw, LogAnalysis)
        assert result.severity == "error"
        assert result.error_patterns == ["OOM"]
        assert result.suggestions == ["add memory"]


class TestSamplingResultBackwardCompat:
    """Verify __str__ and __len__ for backward compatibility."""

    def test_str_returns_text(self):
        result = RunSummary(text="hello world")
        assert str(result) == "hello world"

    def test_len_returns_text_length(self):
        result = RunSummary(text="hello")
        assert len(result) == 5

    def test_empty_result(self):
        result = RunSummary()
        assert str(result) == ""
        assert len(result) == 0


# ── Service tests (mocked ctx.sample) ─────────────────────────


class TestSamplingServiceSummariseRun:
    async def test_returns_structured_result(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        result = await svc.summarise_run({"id": 1, "status": "completed"})
        assert isinstance(result, RunSummary)
        assert str(result) == "AI response"
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
    async def test_returns_structured_result(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        result = await svc.summarise_execution('{"id": "exec-1"}')
        assert isinstance(result, ExecutionSummary)
        assert str(result) == "AI response"

    async def test_passes_json_in_message(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        await svc.summarise_execution('{"id": "exec-1", "goal": "test"}')
        call_kwargs = ctx.sample.call_args.kwargs
        assert "exec-1" in call_kwargs["messages"]


class TestSamplingServiceGenerateTaskPrompt:
    async def test_returns_structured_result(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        result = await svc.generate_task_prompt(goal="Build API", task_description="Add auth")
        assert isinstance(result, TaskPrompt)
        assert str(result) == "AI response"

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
    async def test_returns_structured_result(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        result = await svc.analyse_logs([{"thought": "thinking"}])
        assert isinstance(result, LogAnalysis)
        assert str(result) == "AI response"

    async def test_empty_logs(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)
        result = await svc.analyse_logs([])
        assert isinstance(result, LogAnalysis)
        assert str(result) == "AI response"  # still calls sample; the message says "No logs"


class TestSamplingServiceErrorHandling:
    async def test_value_error_graceful_fallback(self):
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = ValueError("Client does not support sampling")
        svc = SamplingService(ctx)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert "[Sampling unavailable:" in str(result)

    async def test_runtime_error_graceful_fallback(self):
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = RuntimeError("handler misconfigured")
        svc = SamplingService(ctx)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert "[Sampling unavailable:" in str(result)

    async def test_unexpected_error_graceful_fallback(self):
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = TypeError("unexpected")
        svc = SamplingService(ctx)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert "[Sampling error:" in str(result)

    async def test_none_text_returns_empty_string(self):
        ctx = _make_mock_ctx()
        ctx.sample.return_value = FakeSamplingResult(text=None)
        svc = SamplingService(ctx)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert str(result) == ""


class TestSamplingServiceDefaultConfig:
    async def test_uses_default_config_when_none(self):
        ctx = _make_mock_ctx()
        svc = SamplingService(ctx)  # no config passed
        await svc.summarise_run({"id": 1, "status": "ok"})
        call_kwargs = ctx.sample.call_args.kwargs
        # Should use SamplingConfig defaults
        assert call_kwargs["temperature"] == 0.2  # summary_temperature default
        assert call_kwargs["max_tokens"] == 512  # summary_max_tokens default


# ── Per-operation override tests ──────────────────────────────


class TestSamplingServiceOperationOverrides:
    """Test that per-operation config overrides are applied."""

    async def test_temperature_override(self):
        ctx = _make_mock_ctx()
        cfg = SamplingConfig(
            summary_temperature=0.2,
            operation_overrides={
                "summarise_run": OperationConfig(temperature=0.05),
            },
        )
        svc = SamplingService(ctx, cfg)
        await svc.summarise_run({"id": 1, "status": "ok"})
        call_kwargs = ctx.sample.call_args.kwargs
        assert call_kwargs["temperature"] == 0.05

    async def test_max_tokens_override(self):
        ctx = _make_mock_ctx()
        cfg = SamplingConfig(
            analysis_max_tokens=768,
            operation_overrides={
                "analyse_logs": OperationConfig(max_tokens=2048),
            },
        )
        svc = SamplingService(ctx, cfg)
        await svc.analyse_logs([{"thought": "test"}])
        call_kwargs = ctx.sample.call_args.kwargs
        assert call_kwargs["max_tokens"] == 2048

    async def test_system_prompt_override(self):
        ctx = _make_mock_ctx()
        custom_prompt = "You are a custom assistant."
        cfg = SamplingConfig(
            operation_overrides={
                "generate_task_prompt": OperationConfig(system_prompt_override=custom_prompt),
            },
        )
        svc = SamplingService(ctx, cfg)
        await svc.generate_task_prompt(goal="Build", task_description="Add")
        call_kwargs = ctx.sample.call_args.kwargs
        assert call_kwargs["system_prompt"] == custom_prompt

    async def test_no_override_uses_default(self):
        ctx = _make_mock_ctx()
        cfg = SamplingConfig(
            creative_temperature=0.7,
            operation_overrides={
                "summarise_run": OperationConfig(temperature=0.1),  # different operation
            },
        )
        svc = SamplingService(ctx, cfg)
        await svc.generate_task_prompt(goal="Build", task_description="Add")
        call_kwargs = ctx.sample.call_args.kwargs
        assert call_kwargs["temperature"] == 0.7  # default creative_temperature


# ── Retry tests ───────────────────────────────────────────────


class TestSamplingServiceRetry:
    """Test retry logic for transient errors."""

    async def test_retries_on_timeout(self):
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = [
            TimeoutError("timeout"),
            FakeSamplingResult(text="Success after retry"),
        ]
        cfg = SamplingConfig(retry=RetryConfig(max_retries=2, backoff_base=0.1))
        svc = SamplingService(ctx, cfg)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert str(result) == "Success after retry"
        assert ctx.sample.await_count == 2

    async def test_retries_on_connection_error(self):
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = [
            ConnectionError("connection refused"),
            FakeSamplingResult(text="Recovered"),
        ]
        cfg = SamplingConfig(retry=RetryConfig(max_retries=1, backoff_base=0.1))
        svc = SamplingService(ctx, cfg)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert str(result) == "Recovered"

    async def test_exhausted_retries(self):
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = TimeoutError("always times out")
        cfg = SamplingConfig(retry=RetryConfig(max_retries=1, backoff_base=0.1))
        svc = SamplingService(ctx, cfg)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert "[Sampling failed after 2 attempts:" in str(result)
        assert ctx.sample.await_count == 2

    async def test_no_retry_on_value_error(self):
        """Non-transient errors should not trigger retries."""
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = ValueError("not supported")
        cfg = SamplingConfig(retry=RetryConfig(max_retries=3, backoff_base=0.1))
        svc = SamplingService(ctx, cfg)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert "[Sampling unavailable:" in str(result)
        assert ctx.sample.await_count == 1  # no retries

    async def test_zero_retries(self):
        ctx = _make_mock_ctx()
        ctx.sample.side_effect = TimeoutError("timeout")
        cfg = SamplingConfig(retry=RetryConfig(max_retries=0, backoff_base=0.1))
        svc = SamplingService(ctx, cfg)
        result = await svc.summarise_run({"id": 1, "status": "ok"})
        assert "[Sampling failed after 1 attempts:" in str(result)
        assert ctx.sample.await_count == 1

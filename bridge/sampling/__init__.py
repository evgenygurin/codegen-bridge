"""Sampling module — server-side LLM calls via FastMCP ctx.sample().

Provides automatic prompt generation and summarisation by requesting
LLM completions through the MCP sampling API.  The client (or a
configured fallback handler) performs the actual inference.

Public API:
    register_sampling_tools — register MCP tools on the server
    SamplingService          — stateless service wrapping ctx.sample()
    SamplingConfig           — Pydantic configuration model
    RetryConfig              — retry policy for transient failures
    OperationConfig          — per-operation parameter overrides
    RunSummary               — structured result from summarise_run
    ExecutionSummary         — structured result from summarise_execution
    TaskPrompt               — structured result from generate_task_prompt
    LogAnalysis              — structured result from analyse_logs
"""

from bridge.sampling.config import OperationConfig, RetryConfig, SamplingConfig
from bridge.sampling.schemas import ExecutionSummary, LogAnalysis, RunSummary, TaskPrompt
from bridge.sampling.service import SamplingService
from bridge.sampling.tools import register_sampling_tools

__all__ = [
    "ExecutionSummary",
    "LogAnalysis",
    "OperationConfig",
    "RetryConfig",
    "RunSummary",
    "SamplingConfig",
    "SamplingService",
    "TaskPrompt",
    "register_sampling_tools",
]

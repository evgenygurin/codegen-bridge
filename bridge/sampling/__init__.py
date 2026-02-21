"""Sampling module — server-side LLM calls via FastMCP ctx.sample().

Provides automatic prompt generation and summarisation by requesting
LLM completions through the MCP sampling API.  The client (or a
configured fallback handler) performs the actual inference.

Public API:
    register_sampling_tools — register MCP tools on the server
    SamplingService          — stateless service wrapping ctx.sample()
    SamplingConfig           — Pydantic configuration model
"""

from bridge.sampling.config import SamplingConfig
from bridge.sampling.service import SamplingService
from bridge.sampling.tools import register_sampling_tools

__all__ = [
    "SamplingConfig",
    "SamplingService",
    "register_sampling_tools",
]

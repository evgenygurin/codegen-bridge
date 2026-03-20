"""End-to-end tests for the configured middleware stack."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
import respx
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from httpx import Response

# Set test env before importing bridge modules.
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "42"
os.environ["CODEGEN_ALLOW_DANGEROUS_TOOLS"] = "true"

from bridge.annotations import DESTRUCTIVE, READ_ONLY
from bridge.middleware.authorization import AuthorizationConfig
from bridge.middleware.config import (
    CachingConfig,
    ErrorHandlingConfig,
    LoggingConfig,
    MiddlewareConfig,
    PingConfig,
    RateLimitingConfig,
    ResponseLimitingConfig,
    TimingConfig,
)
from bridge.middleware.stack import configure_middleware
from bridge.server import mcp as production_mcp
from bridge.telemetry.config import TelemetryConfig

TRUNCATION_SUFFIX = "\n\n[Response truncated due to size limit]"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "42")
    monkeypatch.setenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", "true")


def _build_test_server(
    *,
    allow_dangerous: bool,
    response_limit_max_size: int = 500_000,
) -> tuple[FastMCP, dict[str, int]]:
    """Build a minimal server wired with the real middleware stack."""

    @asynccontextmanager
    async def _lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        yield {}

    server = FastMCP("test-middleware-e2e", lifespan=_lifespan)
    state = {"stop_calls": 0}

    configure_middleware(
        server,
        MiddlewareConfig(
            error_handling=ErrorHandlingConfig(enabled=True, include_traceback=False),
            ping=PingConfig(enabled=False),
            authorization=AuthorizationConfig(enabled=True, allow_dangerous=allow_dangerous),
            logging=LoggingConfig(enabled=False),
            telemetry=TelemetryConfig(enabled=False),
            timing=TimingConfig(enabled=False),
            rate_limiting=RateLimitingConfig(enabled=False),
            caching=CachingConfig(enabled=False),
            response_limiting=ResponseLimitingConfig(
                enabled=True,
                max_size=response_limit_max_size,
                truncation_suffix=TRUNCATION_SUFFIX,
            ),
        ),
    )

    @server.tool(tags={"dangerous"}, annotations=DESTRUCTIVE)
    async def codegen_stop_run(run_id: int, confirmed: bool = False) -> str:
        del confirmed
        state["stop_calls"] += 1
        return json.dumps({"id": run_id, "status": "stopped"})

    @server.tool(annotations=READ_ONLY)
    async def codegen_get_run(run_id: int) -> str:
        return json.dumps({"id": run_id, "status": "completed"})

    @server.tool(annotations=READ_ONLY, output_schema=None)
    async def codegen_large_response() -> str:
        return "X" * 1_000_000

    return server, state


class TestMiddlewareStackE2E:
    async def test_authorization_blocks_dangerous_tools(self) -> None:
        """Blocked dangerous tools raise ToolError and are never executed."""
        server, state = _build_test_server(allow_dangerous=False)

        async with Client(server) as client:
            with pytest.raises(ToolError, match="dangerous operation"):
                await client.call_tool("codegen_stop_run", {"run_id": 42})

        assert state["stop_calls"] == 0

    async def test_response_limiting_truncates_large_output(self) -> None:
        """Oversized tool output is truncated by ResponseLimitingMiddleware."""
        max_size = 1_000
        server, _ = _build_test_server(
            allow_dangerous=True,
            response_limit_max_size=max_size,
        )

        async with Client(server) as client:
            result = await client.call_tool("codegen_large_response", {})

        assert result.is_error is False
        assert len(result.content) == 1
        text = result.content[0].text
        assert text.endswith(TRUNCATION_SUFFIX)
        assert len(text) <= max_size + len(TRUNCATION_SUFFIX)

    async def test_dangerous_tools_are_marked_restricted_in_listing(self) -> None:
        """Blocked dangerous tools should have a [RESTRICTED] description prefix."""
        server, _ = _build_test_server(allow_dangerous=False)

        async with Client(server) as client:
            tools = await client.list_tools()

        by_name = {tool.name: tool for tool in tools}
        stop_tool = by_name["codegen_stop_run"]
        safe_tool = by_name["codegen_get_run"]

        assert "[RESTRICTED]" in (stop_tool.description or "")
        assert "[RESTRICTED]" not in (safe_tool.description or "")

    @respx.mock
    async def test_tool_call_cache_disabled_by_default(self) -> None:
        """With tool_call_enabled=False, repeated reads should hit API every time."""
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/run/99").mock(
            return_value=Response(
                200,
                json={
                    "id": 99,
                    "status": "completed",
                    "web_url": "https://codegen.com/run/99",
                    "result": None,
                    "summary": "Done",
                    "source_type": "mcp",
                    "github_pull_requests": [],
                },
            )
        )

        async with Client(production_mcp) as client:
            first = await client.call_tool("codegen_get_run", {"run_id": 99})
            second = await client.call_tool("codegen_get_run", {"run_id": 99})

        assert first.is_error is False
        assert second.is_error is False
        assert json.loads(first.data)["id"] == 99
        assert json.loads(second.data)["id"] == 99
        assert route.call_count == 2

"""Shared fixtures for all MCP server tests."""

from __future__ import annotations

import os

import pytest
from fastmcp import Client

# Force test env vars before importing server.
# CODEGEN_ALLOW_DANGEROUS_TOOLS enables the full tool suite in integration tests;
# authorization behaviour is tested separately in tests/middleware/test_authorization.py.
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "42"
os.environ["CODEGEN_ALLOW_DANGEROUS_TOOLS"] = "true"

from bridge.server import mcp


@pytest.fixture(autouse=True)
def _force_test_env(monkeypatch):
    """Ensure test env vars override real ones for every test."""
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "42")
    monkeypatch.setenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", "true")


@pytest.fixture(autouse=True)
def _reset_server_lifespan():
    """Reset server lifespan state between tests.

    When task-enabled tools are present (``task=TaskConfig(mode="optional")``),
    the Docket lifecycle may leave ``_lifespan_result_set=True`` after a
    ``Client`` context-manager exits, preventing subsequent test sessions
    from re-entering the lifespan.  Clearing the flag **before and after**
    each test ensures every test gets a fresh lifespan.

    Also removes the ResponseCachingMiddleware to prevent stale cached
    tool responses from leaking between tests.
    """
    mcp._lifespan_result_set = False
    mcp._lifespan_result = None
    # Remove caching middleware to prevent cross-test cache poisoning.
    # The middleware list is shared across all tests via the module-level mcp
    # object.  A cached tool response from test A would be served to test B
    # if the same tool+args pair is called, bypassing respx mocks entirely.
    original_middleware = list(mcp.middleware)
    mcp.middleware[:] = [
        m for m in mcp.middleware if type(m).__name__ != "ResponseCachingMiddleware"
    ]
    yield
    mcp._lifespan_result_set = False
    mcp._lifespan_result = None
    # Restore caching middleware after each test.
    mcp.middleware[:] = original_middleware


@pytest.fixture
async def client():
    """Create in-memory MCP client with lifespan."""
    async with Client(mcp) as c:
        yield c

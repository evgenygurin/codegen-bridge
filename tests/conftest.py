"""Shared fixtures for all MCP server tests."""

from __future__ import annotations

import os

import pytest
from fastmcp import Client

# Force test env vars before importing server
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "42"

from bridge.server import mcp


@pytest.fixture(autouse=True)
def _force_test_env(monkeypatch):
    """Ensure test env vars override real ones for every test."""
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "42")


@pytest.fixture(autouse=True)
def _reset_server_lifespan():
    """Reset server lifespan state between tests.

    When task-enabled tools are present (``task=TaskConfig(mode="optional")``),
    the Docket lifecycle may leave ``_lifespan_result_set=True`` after a
    ``Client`` context-manager exits, preventing subsequent test sessions
    from re-entering the lifespan.  Clearing the flag **before and after**
    each test ensures every test gets a fresh lifespan.
    """
    mcp._lifespan_result_set = False
    mcp._lifespan_result = None
    yield
    mcp._lifespan_result_set = False
    mcp._lifespan_result = None


@pytest.fixture
async def client():
    """Create in-memory MCP client with lifespan."""
    async with Client(mcp) as c:
        yield c

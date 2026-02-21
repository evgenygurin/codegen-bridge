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


@pytest.fixture
async def client():
    """Create in-memory MCP client with lifespan."""
    async with Client(mcp) as c:
        yield c

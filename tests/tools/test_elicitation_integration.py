"""Integration tests for elicitation in MCP tools.

Tests the full end-to-end flow: Client → elicitation_handler → tool → response.
Covers stop_run confirmation, create_run model selection + repo confirmation,
and start_execution repo confirmation.

Each test with a custom elicitation_handler creates its own Client inside
an ``async with respx.MockRouter`` block to ensure proper HTTP mock scoping.

Important: each test uses **unique argument values** (e.g. different ``run_id``)
to avoid false positives from the ``ResponseCachingMiddleware`` that caches
tool responses by arguments.
"""

from __future__ import annotations

import json
import os

import respx
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult
from httpx import Response

os.environ.setdefault("CODEGEN_API_KEY", "test-key")
os.environ.setdefault("CODEGEN_ORG_ID", "42")

from bridge.server import mcp

BAN_URL = "https://api.codegen.com/v1/organizations/42/agent/run/ban"
CREATE_URL = "https://api.codegen.com/v1/organizations/42/agent/run"
REPOS_URL = "https://api.codegen.com/v1/organizations/42/repos"
RULES_URL = "https://api.codegen.com/v1/organizations/42/cli/rules"

EMPTY_REPOS = {"items": [], "total": 0}
EMPTY_RULES = {"organization_rules": "", "user_custom_prompt": ""}


def _banned(run_id: int) -> dict:
    return {"message": "ok", "status_code": 200}


def _queued(run_id: int) -> dict:
    return {"id": run_id, "status": "queued", "web_url": f"https://codegen.com/run/{run_id}"}


# ── Handlers ─────────────────────────────────────────────────


def _accept(content: dict | None = None):
    async def handler(message, response_type, request_params, context):
        return ElicitResult(action="accept", content=content or {"value": True})

    return handler


def _decline():
    async def handler(message, response_type, request_params, context):
        return ElicitResult(action="decline", content=None)

    return handler


def _cancel():
    async def handler(message, response_type, request_params, context):
        return ElicitResult(action="cancel", content=None)

    return handler


def _sequence(responses: list[ElicitResult]):
    call_index = {"i": 0}

    async def handler(message, response_type, request_params, context):
        idx = call_index["i"]
        call_index["i"] += 1
        if idx < len(responses):
            return responses[idx]
        return ElicitResult(action="accept", content={"value": True})

    return handler


# ── Stop Run Elicitation ────────────────────────────────────


class TestStopRunWithElicitation:
    """Tests that create their own Client with an elicitation handler.

    Each test uses a unique ``run_id`` to avoid response caching.
    """

    async def test_stop_proceeds_when_user_confirms(self):
        async with respx.MockRouter(assert_all_called=False) as router:
            router.post(BAN_URL).mock(return_value=Response(200, json=_banned(201)))
            async with Client(mcp, elicitation_handler=_accept()) as c:
                result = await c.call_tool("codegen_stop_run", {"run_id": 201})
                data = json.loads(result.data)
                assert data["run_id"] == 201
                assert data["action"] == "banned"

    async def test_stop_cancelled_when_user_declines(self):
        async with respx.MockRouter(assert_all_called=False), Client(
            mcp, elicitation_handler=_decline()
        ) as c:
            result = await c.call_tool("codegen_stop_run", {"run_id": 202})
            data = json.loads(result.data)
            assert data["action"] == "cancelled"
            assert data["run_id"] == 202

    async def test_stop_cancelled_when_user_cancels(self):
        async with respx.MockRouter(assert_all_called=False), Client(
            mcp, elicitation_handler=_cancel()
        ) as c:
            result = await c.call_tool("codegen_stop_run", {"run_id": 203})
            data = json.loads(result.data)
            assert data["action"] == "cancelled"


class TestStopRunWithoutElicitation:
    """Tests using the shared ``client`` fixture (no elicitation handler)."""

    @respx.mock
    async def test_stop_skips_elicitation_when_confirmed(self, client: Client):
        respx.post(BAN_URL).mock(return_value=Response(200, json=_banned(211)))
        result = await client.call_tool(
            "codegen_stop_run", {"run_id": 211, "confirmed": True}
        )
        data = json.loads(result.data)
        assert data["action"] == "banned"

    @respx.mock
    async def test_stop_graceful_degradation(self, client: Client):
        """Without elicitation handler, stop proceeds (default=True)."""
        respx.post(BAN_URL).mock(return_value=Response(200, json=_banned(212)))
        result = await client.call_tool("codegen_stop_run", {"run_id": 212})
        data = json.loads(result.data)
        assert data["action"] == "banned"


# ── Create Run Elicitation ──────────────────────────────────


class TestCreateRunWithElicitation:
    async def test_model_selection_and_confirmation(self):
        async with respx.MockRouter(assert_all_called=False) as router:
            router.get(REPOS_URL).mock(return_value=Response(200, json=EMPTY_REPOS))
            route = router.post(CREATE_URL).mock(
                return_value=Response(200, json=_queued(301))
            )
            handler = _sequence([
                ElicitResult(action="accept", content={"value": "claude-3-5-sonnet"}),
                ElicitResult(action="accept", content={"value": True}),
            ])
            async with Client(mcp, elicitation_handler=handler) as c:
                result = await c.call_tool(
                    "codegen_create_run",
                    {"prompt": "Fix bug alpha", "repo_id": 10},
                )
                data = json.loads(result.data)
                assert data["id"] == 301
                body = json.loads(route.calls[0].request.content)
                assert body["model"] == "claude-3-5-sonnet"

    async def test_cancelled_on_repo_confirmation_decline(self):
        async with respx.MockRouter(assert_all_called=False) as router:
            router.get(REPOS_URL).mock(return_value=Response(200, json=EMPTY_REPOS))
            handler = _sequence([
                ElicitResult(action="accept", content={"value": "gpt-4o"}),
                ElicitResult(action="decline", content=None),
            ])
            async with Client(mcp, elicitation_handler=handler) as c:
                result = await c.call_tool(
                    "codegen_create_run",
                    {"prompt": "Fix bug beta", "repo_id": 11},
                )
                data = json.loads(result.data)
                assert data["action"] == "cancelled"

    async def test_skips_model_elicitation_when_model_provided(self):
        async with respx.MockRouter(assert_all_called=False) as router:
            router.get(REPOS_URL).mock(return_value=Response(200, json=EMPTY_REPOS))
            route = router.post(CREATE_URL).mock(
                return_value=Response(200, json=_queued(302))
            )
            async with Client(mcp, elicitation_handler=_accept()) as c:
                result = await c.call_tool(
                    "codegen_create_run",
                    {"prompt": "Fix bug gamma", "repo_id": 12, "model": "gpt-4o"},
                )
                data = json.loads(result.data)
                assert data["id"] == 302
                body = json.loads(route.calls[0].request.content)
                assert body["model"] == "gpt-4o"


class TestCreateRunWithoutElicitation:
    @respx.mock
    async def test_skips_elicitation_when_confirmed(self, client: Client):
        respx.get(REPOS_URL).mock(return_value=Response(200, json=EMPTY_REPOS))
        respx.post(CREATE_URL).mock(
            return_value=Response(200, json=_queued(311))
        )
        result = await client.call_tool(
            "codegen_create_run",
            {"prompt": "Fix bug delta", "repo_id": 13, "confirmed": True},
        )
        data = json.loads(result.data)
        assert data["id"] == 311

    @respx.mock
    async def test_graceful_degradation(self, client: Client):
        """Without elicitation handler, create_run proceeds with defaults."""
        respx.get(REPOS_URL).mock(return_value=Response(200, json=EMPTY_REPOS))
        route = respx.post(CREATE_URL).mock(
            return_value=Response(200, json=_queued(312))
        )
        result = await client.call_tool(
            "codegen_create_run",
            {"prompt": "Fix bug epsilon", "repo_id": 14},
        )
        data = json.loads(result.data)
        assert data["id"] == 312
        body = json.loads(route.calls[0].request.content)
        assert "model" not in body or body.get("model") is None


# ── Start Execution Elicitation ─────────────────────────────


class TestStartExecutionElicitation:
    @respx.mock
    async def test_proceeds_when_confirmed(self, client: Client):
        respx.get(RULES_URL).mock(return_value=Response(200, json=EMPTY_RULES))
        respx.get(REPOS_URL).mock(return_value=Response(200, json=EMPTY_REPOS))
        result = await client.call_tool(
            "codegen_start_execution",
            {"execution_id": "e-1", "goal": "Build feature alpha", "confirmed": True},
        )
        data = json.loads(result.data)
        assert data["execution_id"] == "e-1"
        assert data["status"] == "active"

    @respx.mock
    async def test_graceful_degradation(self, client: Client):
        """Without elicitation handler, start_execution proceeds normally."""
        respx.get(RULES_URL).mock(return_value=Response(200, json=EMPTY_RULES))
        respx.get(REPOS_URL).mock(return_value=Response(200, json=EMPTY_REPOS))
        result = await client.call_tool(
            "codegen_start_execution",
            {"execution_id": "e-2", "goal": "Build feature beta"},
        )
        data = json.loads(result.data)
        assert data["execution_id"] == "e-2"
        assert data["status"] == "active"

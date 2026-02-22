"""Integration tests for cursor-based pagination in list tools.

Verifies that codegen_list_runs, codegen_list_repos, and codegen_get_logs
correctly accept cursor parameters and return paginated responses with
``next_cursor`` fields.
"""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response

from bridge.helpers.pagination import cursor_to_offset, offset_to_cursor

# ── codegen_list_runs ────────────────────────────────────


class TestListRunsPagination:
    @respx.mock
    async def test_first_page_returns_next_cursor(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": i,
                            "status": "completed",
                            "created_at": f"2024-01-0{i}",
                            "web_url": f"https://codegen.com/run/{i}",
                            "summary": f"Run {i}",
                        }
                        for i in range(1, 3)
                    ],
                    "total": 5,
                },
            )
        )

        result = await client.call_tool("codegen_list_runs", {"limit": 2})
        data = json.loads(result.data)
        assert len(data["runs"]) == 2
        assert data["total"] == 5
        assert data["next_cursor"] is not None
        # Next cursor should decode to offset 2
        assert cursor_to_offset(data["next_cursor"]) == 2

    @respx.mock
    async def test_cursor_passes_skip_to_api(self, client: Client):
        cursor = offset_to_cursor(4)
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": 5,
                            "status": "completed",
                            "web_url": "https://codegen.com/run/5",
                        }
                    ],
                    "total": 5,
                },
            )
        )

        result = await client.call_tool("codegen_list_runs", {"limit": 2, "cursor": cursor})
        data = json.loads(result.data)
        assert len(data["runs"]) == 1
        # Last page → no next_cursor
        assert data["next_cursor"] is None

        # Verify skip=4 was passed to the API
        request = route.calls[0].request
        assert "skip=4" in str(request.url)

    @respx.mock
    async def test_no_cursor_starts_from_beginning(self, client: Client):
        def handler(request):
            assert "skip=0" in str(request.url)
            return Response(200, json={"items": [], "total": 0})

        respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            side_effect=handler
        )

        # Use a unique limit to avoid cache collisions with other tests
        result = await client.call_tool("codegen_list_runs", {"limit": 7})
        data = json.loads(result.data)
        assert data["runs"] == []
        assert data["next_cursor"] is None

    @respx.mock
    async def test_source_type_filter_preserved_with_cursor(self, client: Client):
        cursor = offset_to_cursor(10)
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            return_value=Response(
                200,
                json={"items": [], "total": 10},
            )
        )

        await client.call_tool(
            "codegen_list_runs",
            {"limit": 5, "cursor": cursor, "source_type": "API"},
        )
        request = route.calls[0].request
        url_str = str(request.url)
        assert "skip=10" in url_str
        assert "source_type=API" in url_str


# ── codegen_list_repos ───────────────────────────────────


class TestListReposPagination:
    @respx.mock
    async def test_first_page_returns_next_cursor(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": 1,
                            "name": "repo1",
                            "full_name": "org/repo1",
                            "language": "Python",
                            "setup_status": "completed",
                        }
                    ],
                    "total": 3,
                },
            )
        )

        result = await client.call_tool("codegen_list_repos", {"limit": 1})
        data = json.loads(result.data)
        assert len(data["repos"]) == 1
        assert data["total"] == 3
        assert data["next_cursor"] is not None
        assert cursor_to_offset(data["next_cursor"]) == 1

    @respx.mock
    async def test_cursor_passes_skip_to_api(self, client: Client):
        cursor = offset_to_cursor(2)
        route = respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": 3,
                            "name": "repo3",
                            "full_name": "org/repo3",
                            "language": "Go",
                            "setup_status": "completed",
                        }
                    ],
                    "total": 3,
                },
            )
        )

        result = await client.call_tool("codegen_list_repos", {"limit": 2, "cursor": cursor})
        data = json.loads(result.data)
        assert data["next_cursor"] is None  # Last page

        request = route.calls[0].request
        assert "skip=2" in str(request.url)

    @respx.mock
    async def test_no_cursor_starts_from_beginning(self, client: Client):
        def handler(request):
            assert "skip=0" in str(request.url)
            return Response(200, json={"items": [], "total": 0})

        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(side_effect=handler)

        # Use a unique limit to avoid cache collisions with other tests
        result = await client.call_tool("codegen_list_repos", {"limit": 7})
        data = json.loads(result.data)
        assert data["repos"] == []
        assert data["next_cursor"] is None


# ── codegen_get_logs ─────────────────────────────────────


class TestGetLogsPagination:
    @respx.mock
    async def test_first_page_returns_next_cursor(self, client: Client):
        respx.get("https://api.codegen.com/v1/alpha/organizations/42/agent/run/99/logs").mock(
            return_value=Response(
                200,
                json={
                    "id": 99,
                    "status": "running",
                    "logs": [{"agent_run_id": 99, "thought": f"Step {i}"} for i in range(3)],
                    "total_logs": 10,
                },
            )
        )

        result = await client.call_tool("codegen_get_logs", {"run_id": 99, "limit": 3})
        data = json.loads(result.data)
        assert len(data["logs"]) == 3
        assert data["total_logs"] == 10
        assert data["next_cursor"] is not None
        assert cursor_to_offset(data["next_cursor"]) == 3

    @respx.mock
    async def test_cursor_passes_skip_to_api(self, client: Client):
        cursor = offset_to_cursor(6)
        route = respx.get(
            "https://api.codegen.com/v1/alpha/organizations/42/agent/run/99/logs"
        ).mock(
            return_value=Response(
                200,
                json={
                    "id": 99,
                    "status": "completed",
                    "logs": [{"agent_run_id": 99, "thought": "Final step"}],
                    "total_logs": 7,
                },
            )
        )

        result = await client.call_tool(
            "codegen_get_logs", {"run_id": 99, "limit": 3, "cursor": cursor}
        )
        data = json.loads(result.data)
        assert data["next_cursor"] is None  # Last page

        request = route.calls[0].request
        assert "skip=6" in str(request.url)

    @respx.mock
    async def test_no_cursor_starts_from_beginning(self, client: Client):
        def handler(request):
            assert "skip=0" in str(request.url)
            return Response(
                200,
                json={
                    "id": 99,
                    "status": "running",
                    "logs": [],
                    "total_logs": 0,
                },
            )

        respx.get("https://api.codegen.com/v1/alpha/organizations/42/agent/run/99/logs").mock(
            side_effect=handler
        )

        # Use a unique limit to avoid cache collisions with other tests
        result = await client.call_tool("codegen_get_logs", {"run_id": 99, "limit": 7})
        data = json.loads(result.data)
        assert data["logs"] == []
        assert data["next_cursor"] is None

    @respx.mock
    async def test_reverse_preserved_with_cursor(self, client: Client):
        cursor = offset_to_cursor(5)
        route = respx.get(
            "https://api.codegen.com/v1/alpha/organizations/42/agent/run/99/logs"
        ).mock(
            return_value=Response(
                200,
                json={
                    "id": 99,
                    "status": "running",
                    "logs": [],
                    "total_logs": 5,
                },
            )
        )

        await client.call_tool(
            "codegen_get_logs",
            {"run_id": 99, "limit": 5, "cursor": cursor, "reverse": False},
        )
        request = route.calls[0].request
        url_str = str(request.url)
        assert "skip=5" in url_str
        assert "reverse=false" in url_str


# ── Multi-page walkthrough ───────────────────────────────


class TestMultiPageWalkthrough:
    """End-to-end test walking through all pages of codegen_list_runs."""

    @respx.mock
    async def test_walk_all_pages(self, client: Client):
        # Total 5 runs, page size 2 → 3 pages (2 + 2 + 1)
        all_runs = [
            {
                "id": i,
                "status": "completed",
                "created_at": f"2024-01-{i:02d}",
                "web_url": f"https://codegen.com/run/{i}",
                "summary": f"Run {i}",
            }
            for i in range(1, 6)
        ]

        def mock_handler(request):
            url = str(request.url)
            # Parse skip and limit from URL
            skip = 0
            limit = 2
            for param in url.split("?")[1].split("&") if "?" in url else []:
                k, v = param.split("=")
                if k == "skip":
                    skip = int(v)
                elif k == "limit":
                    limit = int(v)
            page_items = all_runs[skip : skip + limit]
            return Response(
                200,
                json={"items": page_items, "total": 5},
            )

        respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            side_effect=mock_handler
        )

        collected_ids: list[int] = []
        cursor = None

        for _page_num in range(10):  # Safety limit
            args: dict = {"limit": 2}
            if cursor is not None:
                args["cursor"] = cursor

            result = await client.call_tool("codegen_list_runs", args)
            data = json.loads(result.data)

            for run in data["runs"]:
                collected_ids.append(run["id"])

            cursor = data["next_cursor"]
            if cursor is None:
                break

        assert collected_ids == [1, 2, 3, 4, 5]

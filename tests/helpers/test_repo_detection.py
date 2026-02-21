"""Tests for repository auto-detection helper."""

from __future__ import annotations

from unittest.mock import patch

import respx
from httpx import Response

from bridge.client import CodegenClient
from bridge.helpers.repo_detection import _repo_cache, detect_repo_id


class TestDetectRepoId:
    @respx.mock
    async def test_detects_https_remote(self):
        with patch("bridge.helpers.repo_detection.subprocess") as mock_sub:
            mock_sub.run.return_value = type(
                "Result", (), {"returncode": 0, "stdout": "https://github.com/org/myrepo.git\n"}
            )()

            respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
                return_value=Response(
                    200,
                    json={
                        "items": [
                            {"id": 10, "name": "myrepo", "full_name": "org/myrepo"},
                        ],
                        "total": 1,
                    },
                )
            )

            _repo_cache.clear()
            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client)

            assert repo_id == 10

    @respx.mock
    async def test_detects_ssh_remote(self):
        with patch("bridge.helpers.repo_detection.subprocess") as mock_sub:
            mock_sub.run.return_value = type(
                "Result", (), {"returncode": 0, "stdout": "git@github.com:org/myrepo.git\n"}
            )()

            respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
                return_value=Response(
                    200,
                    json={
                        "items": [
                            {"id": 10, "name": "myrepo", "full_name": "org/myrepo"},
                        ],
                        "total": 1,
                    },
                )
            )

            _repo_cache.clear()
            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client)

            assert repo_id == 10

    async def test_returns_none_when_git_fails(self):
        with patch("bridge.helpers.repo_detection.subprocess") as mock_sub:
            mock_sub.run.return_value = type(
                "Result", (), {"returncode": 1, "stdout": ""}
            )()

            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client)

            assert repo_id is None

    @respx.mock
    async def test_returns_none_when_repo_not_in_org(self):
        with patch("bridge.helpers.repo_detection.subprocess") as mock_sub:
            mock_sub.run.return_value = type(
                "Result", (), {"returncode": 0, "stdout": "https://github.com/org/unknown.git\n"}
            )()

            respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
                return_value=Response(200, json={"items": [], "total": 0})
            )

            _repo_cache.clear()
            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client)

            assert repo_id is None

    @respx.mock
    async def test_uses_cache_on_second_call(self):
        _repo_cache.clear()
        _repo_cache["org/cached"] = 99

        with patch("bridge.helpers.repo_detection.subprocess") as mock_sub:
            mock_sub.run.return_value = type(
                "Result", (), {"returncode": 0, "stdout": "https://github.com/org/cached.git\n"}
            )()

            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client)

            assert repo_id == 99

    async def test_returns_none_for_non_github_url(self):
        with patch("bridge.helpers.repo_detection.subprocess") as mock_sub:
            mock_sub.run.return_value = type(
                "Result",
                (),
                {"returncode": 0, "stdout": "https://gitlab.com/org/repo.git\n"},
            )()

            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client)

            assert repo_id is None

"""Tests for repository auto-detection helper."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import respx
from httpx import Response

from bridge.client import CodegenClient
from bridge.helpers.repo_detection import RepoCache, detect_repo_id


@pytest.fixture
def cache():
    """Provide a fresh RepoCache for each test."""
    return RepoCache()


class TestRepoCache:
    def test_put_and_get(self):
        c = RepoCache()
        c.put("org/repo", 42)
        assert c.get("org/repo") == 42

    def test_get_returns_none_for_missing(self):
        c = RepoCache()
        assert c.get("org/missing") is None

    def test_contains(self):
        c = RepoCache()
        c.put("org/repo", 1)
        assert "org/repo" in c
        assert "org/other" not in c

    def test_len(self):
        c = RepoCache()
        assert len(c) == 0
        c.put("a/b", 1)
        assert len(c) == 1

    def test_clear(self):
        c = RepoCache()
        c.put("a/b", 1)
        c.clear()
        assert len(c) == 0
        assert c.get("a/b") is None


class TestDetectRepoId:
    @respx.mock
    async def test_detects_https_remote(self, cache):
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

            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client, cache)

            assert repo_id == 10

    @respx.mock
    async def test_detects_ssh_remote(self, cache):
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

            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client, cache)

            assert repo_id == 10

    async def test_returns_none_when_git_fails(self, cache):
        with patch("bridge.helpers.repo_detection.subprocess") as mock_sub:
            mock_sub.run.return_value = type("Result", (), {"returncode": 1, "stdout": ""})()

            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client, cache)

            assert repo_id is None

    @respx.mock
    async def test_returns_none_when_repo_not_in_org(self, cache):
        with patch("bridge.helpers.repo_detection.subprocess") as mock_sub:
            mock_sub.run.return_value = type(
                "Result", (), {"returncode": 0, "stdout": "https://github.com/org/unknown.git\n"}
            )()

            respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
                return_value=Response(200, json={"items": [], "total": 0})
            )

            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client, cache)

            assert repo_id is None

    @respx.mock
    async def test_uses_cache_on_second_call(self, cache):
        cache.put("org/cached", 99)

        with patch("bridge.helpers.repo_detection.subprocess") as mock_sub:
            mock_sub.run.return_value = type(
                "Result", (), {"returncode": 0, "stdout": "https://github.com/org/cached.git\n"}
            )()

            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client, cache)

            assert repo_id == 99

    async def test_returns_none_for_non_github_url(self, cache):
        with patch("bridge.helpers.repo_detection.subprocess") as mock_sub:
            mock_sub.run.return_value = type(
                "Result",
                (),
                {"returncode": 0, "stdout": "https://gitlab.com/org/repo.git\n"},
            )()

            async with CodegenClient(api_key="test", org_id=42) as client:
                repo_id = await detect_repo_id(client, cache)

            assert repo_id is None

    @respx.mock
    async def test_populates_cache_after_api_call(self, cache):
        """After a successful API lookup the cache should contain the repo."""
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

            async with CodegenClient(api_key="test", org_id=42) as client:
                await detect_repo_id(client, cache)

            assert cache.get("org/myrepo") == 10

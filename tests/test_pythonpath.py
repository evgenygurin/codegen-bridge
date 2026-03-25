"""Tests for bridge._pythonpath — PYTHONPATH / sys.path sanitisation."""

from __future__ import annotations

import os
import sys

import pytest

from bridge._pythonpath import sanitize_python_path

# Current interpreter version string used throughout tests.
_CUR = f"{sys.version_info.major}.{sys.version_info.minor}"


# ── sys.path cleaning ──────────────────────────────────────────────


class TestSysPathSanitization:
    """sanitize_python_path strips foreign-version entries from sys_path."""

    def test_removes_foreign_version(self) -> None:
        paths: list[str] = [
            "/project/.venv/lib/python3.12/site-packages",
            "/usr/local/lib/python3.13/site-packages",
        ]
        removed = sanitize_python_path(sys_path=paths, env={})
        assert "/usr/local/lib/python3.13/site-packages" in removed
        assert "/project/.venv/lib/python3.12/site-packages" in paths

    def test_preserves_current_version(self) -> None:
        path_cur = f"/some/lib/python{_CUR}/site-packages"
        paths: list[str] = [path_cur, "/plain/dir"]
        removed = sanitize_python_path(sys_path=paths, env={})
        assert removed == []
        assert path_cur in paths
        assert "/plain/dir" in paths

    def test_preserves_non_version_paths(self) -> None:
        paths: list[str] = ["/app", "/usr/lib", ""]
        removed = sanitize_python_path(sys_path=paths, env={})
        assert removed == []
        assert paths == ["/app", "/usr/lib", ""]

    def test_noop_when_no_contamination(self) -> None:
        paths: list[str] = [f"/venv/lib/python{_CUR}/site-packages", "/src"]
        removed = sanitize_python_path(sys_path=paths, env={})
        assert removed == []
        assert len(paths) == 2

    def test_removes_multiple_foreign_versions(self) -> None:
        paths: list[str] = [
            "/usr/local/lib/python3.11/site-packages",
            f"/venv/lib/python{_CUR}/site-packages",
            "/usr/local/lib/python3.13/site-packages",
        ]
        removed = sanitize_python_path(sys_path=paths, env={})
        assert len(removed) == 2
        assert len(paths) == 1
        assert _CUR in paths[0]

    def test_mutates_in_place(self) -> None:
        paths: list[str] = ["/usr/local/lib/python3.99/site-packages"]
        sanitize_python_path(sys_path=paths, env={})
        assert paths == []


# ── sys.path_importer_cache eviction ────────────────────────────────


class TestImporterCacheEviction:
    """sanitize_python_path evicts foreign entries from sys.path_importer_cache."""

    def test_evicts_foreign_cache_entries(self) -> None:
        """Foreign paths removed from sys.path must also be evicted from cache."""
        foreign = "/usr/local/lib/python3.99/site-packages"
        sentinel = object()

        # Seed the cache with a foreign entry.
        sys.path_importer_cache[foreign] = sentinel  # type: ignore[assignment]
        try:
            paths: list[str] = [foreign]
            sanitize_python_path(sys_path=paths, env={})
            assert foreign not in sys.path_importer_cache
        finally:
            # Cleanup in case assertion fails.
            sys.path_importer_cache.pop(foreign, None)

    def test_preserves_current_version_cache(self) -> None:
        """Current-version cache entries must NOT be evicted."""
        cur = f"/venv/lib/python{_CUR}/site-packages"
        sentinel = object()

        sys.path_importer_cache[cur] = sentinel  # type: ignore[assignment]
        try:
            paths: list[str] = [cur]
            sanitize_python_path(sys_path=paths, env={})
            assert sys.path_importer_cache.get(cur) is sentinel
        finally:
            sys.path_importer_cache.pop(cur, None)


# ── PYTHONPATH env var cleaning ─────────────────────────────────────


class TestPythonPathEnvSanitization:
    """sanitize_python_path cleans the PYTHONPATH env variable."""

    def test_removes_foreign_from_env(self) -> None:
        env: dict[str, str] = {"PYTHONPATH": "/usr/local/lib/python3.13/site-packages"}
        sanitize_python_path(sys_path=[], env=env)
        assert "PYTHONPATH" not in env

    def test_preserves_current_version_in_env(self) -> None:
        cur_path = f"/venv/lib/python{_CUR}/site-packages"
        env: dict[str, str] = {"PYTHONPATH": cur_path}
        sanitize_python_path(sys_path=[], env=env)
        assert env["PYTHONPATH"] == cur_path

    def test_partial_cleanup_in_env(self) -> None:
        good = f"/venv/lib/python{_CUR}/site-packages"
        bad = "/usr/local/lib/python3.13/site-packages"
        env: dict[str, str] = {"PYTHONPATH": os.pathsep.join([good, bad])}
        sanitize_python_path(sys_path=[], env=env)
        assert env["PYTHONPATH"] == good

    def test_missing_pythonpath_is_safe(self) -> None:
        env: dict[str, str] = {}
        sanitize_python_path(sys_path=[], env=env)
        assert "PYTHONPATH" not in env

    def test_empty_pythonpath_is_safe(self) -> None:
        env: dict[str, str] = {"PYTHONPATH": ""}
        sanitize_python_path(sys_path=[], env=env)
        # Empty string → no parts to keep → key removed
        assert "PYTHONPATH" not in env


# ── Integration-style ───────────────────────────────────────────────


class TestIntegration:
    """Simulate realistic sandbox contamination."""

    def test_sandbox_scenario(self) -> None:
        """Reproduce the exact sandbox failure mode."""
        paths: list[str] = [
            "/tmp/project/.venv/lib/python3.12/site-packages",
            "/usr/local/lib/python3.13/site-packages",
            "/tmp/project",
        ]
        env: dict[str, str] = {
            "PYTHONPATH": "/usr/local/lib/python3.13/site-packages",
            "HOME": "/root",
        }
        removed = sanitize_python_path(sys_path=paths, env=env)

        # sys.path cleaned
        assert "/usr/local/lib/python3.13/site-packages" not in paths
        assert "/tmp/project/.venv/lib/python3.12/site-packages" in paths
        assert "/tmp/project" in paths

        # PYTHONPATH env cleaned
        assert "PYTHONPATH" not in env
        # Unrelated env vars preserved
        assert env["HOME"] == "/root"

        # Exactly one path was removed
        assert removed == ["/usr/local/lib/python3.13/site-packages"]

    @pytest.mark.skipif(
        "PYTHONPATH" not in os.environ,
        reason="no PYTHONPATH contamination to verify",
    )
    def test_real_env_survives_sanitization(self) -> None:
        """When run in a contaminated env, the real sys.path is already clean.

        The root conftest.py sanitises sys.path at collection time, so by the
        time this test body executes the paths are already fixed.  We just
        verify the invariant: no foreign-version entries remain.
        """
        cur = f"python{_CUR}"
        for p in sys.path:
            if "/python" in p and "site-packages" in p:
                assert cur in p, f"Foreign path still in sys.path: {p}"

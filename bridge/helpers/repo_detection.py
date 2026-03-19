"""Auto-detect repository ID from git remote origin."""

from __future__ import annotations

import subprocess

import httpx

from bridge.client import CodegenClient


class RepoCache:
    """In-memory cache mapping repo full_name to repo ID.

    Eliminates module-level global state by providing a lifecycle-managed
    cache that is created in the server lifespan and injected via DI.
    """

    def __init__(self) -> None:
        self._data: dict[str, int] = {}

    def get(self, full_name: str) -> int | None:
        """Return cached repo ID for *full_name*, or ``None``."""
        return self._data.get(full_name)

    def put(self, full_name: str, repo_id: int) -> None:
        """Store a repo full_name to repo_id mapping."""
        self._data[full_name] = repo_id

    def clear(self) -> None:
        """Remove all cached entries."""
        self._data.clear()

    def __contains__(self, full_name: str) -> bool:
        return full_name in self._data

    def __len__(self) -> int:
        return len(self._data)


def _parse_remote_url() -> str | None:
    """Extract ``org/repo`` full name from git remote origin URL.

    Returns ``None`` if git is unavailable, the remote is unset,
    or the URL is not a GitHub URL.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        url = result.stdout.strip()
        if "github.com" not in url:
            return None

        if url.startswith("git@"):
            return url.split(":")[-1].removesuffix(".git")

        parts = url.rstrip("/").removesuffix(".git").split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"

        return None
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


async def detect_repo_id(
    client: CodegenClient,
    cache: RepoCache,
) -> int | None:
    """Auto-detect repo_id from git remote origin.

    Parses the git remote URL, extracts the org/repo full name,
    then looks it up via the Codegen API.  Results are cached in
    the provided :class:`RepoCache` instance.

    Args:
        client: An already-resolved ``CodegenClient`` instance.
        cache: Injected repo cache (managed by server lifespan).
    """
    try:
        full_name = _parse_remote_url()
        if not full_name:
            return None

        cached = cache.get(full_name)
        if cached is not None:
            return cached

        repos = await client.list_repos(limit=100)
        for repo in repos.items:
            cache.put(repo.full_name, repo.id)
            if repo.full_name == full_name:
                return repo.id

        return None

    except (httpx.HTTPError, OSError, ValueError):
        return None

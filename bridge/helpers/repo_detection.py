"""Auto-detect repository ID from git remote origin."""

from __future__ import annotations

import subprocess

from fastmcp import Context

from bridge.dependencies import get_client

_repo_cache: dict[str, int] = {}


async def detect_repo_id(ctx: Context | None = None) -> int | None:
    """Auto-detect repo_id from git remote origin.

    Parses the git remote URL, extracts the org/repo full name,
    then looks it up via the Codegen API.
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
        full_name = ""
        if "github.com" in url:
            if url.startswith("git@"):
                full_name = url.split(":")[-1].removesuffix(".git")
            else:
                parts = url.rstrip("/").removesuffix(".git").split("/")
                if len(parts) >= 2:
                    full_name = f"{parts[-2]}/{parts[-1]}"

        if not full_name:
            return None

        if full_name in _repo_cache:
            return _repo_cache[full_name]

        client = get_client(ctx)
        repos = await client.list_repos(limit=100)
        for repo in repos.items:
            _repo_cache[repo.full_name] = repo.id
            if repo.full_name == full_name:
                return repo.id

        return None

    except Exception:
        return None

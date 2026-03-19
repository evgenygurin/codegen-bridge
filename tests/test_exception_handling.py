"""Verify that bare ``except Exception`` handlers are limited to intentional error boundaries.

The codebase should have at most 3 bare ``except Exception`` handlers — all in
code paths that intentionally re-raise or serve as final error boundaries:

1. ``bridge/telemetry/middleware.py`` — re-raises after recording span error
2. ``bridge/telemetry/helpers.py`` — re-raises after recording metrics
3. ``bridge/sampling/service.py`` — final error boundary with ``.exception()`` logging
"""

from __future__ import annotations

import ast
from pathlib import Path

MAX_BARE_EXCEPT_EXCEPTION = 3

BRIDGE_ROOT = Path(__file__).resolve().parent.parent / "bridge"


def _count_except_exception(root: Path) -> list[tuple[str, int]]:
    """Return ``(relative_path, line)`` for every ``except Exception`` handler."""
    hits: list[tuple[str, int]] = []
    for py_file in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            # except Exception / except Exception as exc
            if (
                node.type is not None
                and isinstance(node.type, ast.Name)
                and node.type.id == "Exception"
            ):
                rel = py_file.relative_to(root)
                hits.append((str(rel), node.lineno))
    return hits


def test_bare_except_exception_count() -> None:
    """At most MAX_BARE_EXCEPT_EXCEPTION bare ``except Exception`` handlers remain."""
    hits = _count_except_exception(BRIDGE_ROOT)
    locations = "\n".join(f"  {path}:{line}" for path, line in hits)
    assert len(hits) <= MAX_BARE_EXCEPT_EXCEPTION, (
        f"Found {len(hits)} bare `except Exception` handlers "
        f"(max {MAX_BARE_EXCEPT_EXCEPTION}):\n{locations}"
    )


def test_remaining_handlers_are_intentional() -> None:
    """The surviving handlers must be in known intentional locations."""
    allowed = {
        "telemetry/middleware.py",
        "telemetry/helpers.py",
        "sampling/service.py",
    }
    hits = _count_except_exception(BRIDGE_ROOT)
    for path, line in hits:
        assert path in allowed, (
            f"Unexpected bare `except Exception` at bridge/{path}:{line} — "
            f"replace with specific exception types"
        )

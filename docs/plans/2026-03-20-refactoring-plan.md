# Codegen Bridge — Maximum Refactoring Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete redesign of codegen-bridge MCP server, merging existing PR work and implementing all remaining tasks from the original plan.

**Architecture:** Hybrid MCP server (FastMCP 3.x) with 9-layer middleware, 4-stage transforms, 4 providers, background tasks, sampling via `ctx.sample()`, and session state. Manual tools + OpenAPI auto-generated tools.

**Tech Stack:** Python 3.12, FastMCP 3.x, httpx, Pydantic 2.x, py-key-value-aio, OpenTelemetry

---

## Current State Analysis

### Master Branch (baseline)
- **v0.4.0**, 27K LOC, 60 modules, 39 manual + ~21 auto-generated tools
- Tasks 1-3 already merged: CI/CD, HTTP client reliability, SOLID decomposition
- 1,015 tests passing on master

### Open PRs (all failing CI)

| PR | Title | +/- | Tests | Status |
|----|-------|-----|-------|--------|
| #53 | fix(hooks): Stop hook JSON schema | +1/-1 | trivial | CI fail |
| #54 | release: v0.5.0 (6 PRs merged) | +5,394/-167 | 1,355 | CI fail |
| #55 | feat: v0.5 architecture upgrade | +4,069/-824 | 1,107 | CI fail |
| #56 | feat: unlock full potential | +1,953/-94 | 51 | CI fail |

### What PRs Cover (from original plan)
- **PR #54**: Task 4 (monitoring), Task 5 (OpenAPI governance), Task 6 (sampling)
- **PR #55**: Task 2 ext (rate budget), Task 3 ext (service layer), partial Task 8 (annotations)
- **PR #56**: New capabilities (remote proxy, smart caching, elicitation safety)
- **PR #53**: Trivial hooks fix

### What Remains (NOT in any PR)
- Task 7: Bulk operations + analytics tools
- Task 8: Full transforms, versioning, visibility (FastMCP 3.x)
- Task 9: Integration tools (webhooks, Slack, GitHub advanced)
- Task 10: Skills redesign
- Task 11: Plugin structure modernization
- Task 12: Telemetry + storage backends
- Task 13: Documentation

---

## Phase 0: PR Triage & Merge (Foundation)

### Task 0.1: Fix and Merge PR #53 (hooks fix)

**Files:**
- Modify: `hooks/hooks.json`

**Step 1: Review the 1-line change**
```bash
gh pr diff 53
```
Expected: Single line change in hooks.json Stop hook schema

**Step 2: Checkout and verify locally**
```bash
git fetch origin fix/stop-hook-json-schema
git checkout fix/stop-hook-json-schema
uv run pytest tests/test_hooks.py -v
```
Expected: PASS

**Step 3: Fix CI if needed and merge**
```bash
gh pr merge 53 --squash
```

---

### Task 0.2: Evaluate PR #54 (v0.5.0 release)

This PR merges 6 sub-PRs. It adds:
- `bridge/monitoring.py` — BackgroundTaskManager
- `bridge/sampling/config.py`, `schemas.py`, `service.py` — Enhanced sampling
- `scripts/openapi_sync.py` — OpenAPI governance
- `bridge/tools/agent/monitor.py` — codegen_monitor_run
- 46 new test files, 1,355 total tests

**Step 1: Checkout and diagnose CI failures**
```bash
git fetch origin release/v0.5.0
git checkout release/v0.5.0
uv sync --dev
uv run ruff check .
uv run mypy bridge/
uv run pytest -x -v 2>&1 | head -50
```

**Step 2: Fix all lint/type/test failures**
Fix issues found in step 1. Common problems:
- Import sorting (ruff I001)
- Unused imports (ruff F401)
- Missing type annotations (mypy)
- Test assertions mismatched with code changes

**Step 3: Run full quality gate**
```bash
uv run ruff check . && uv run mypy bridge/ && uv run pytest -v
```
Expected: All pass with 1,355+ tests

**Step 4: Merge to master**
```bash
gh pr merge 54 --squash
```

---

### Task 0.3: Evaluate PR #55 (v0.5 architecture)

This is the largest PR (+4,069/-824). Adds:
- `bridge/services/runs.py`, `execution.py` — Service layer
- `bridge/annotations.py` — ToolAnnotations presets
- `bridge/rate_budget.py` — Token-bucket rate limiter
- `bridge/resources/templates.py` — URI resource templates
- `bridge/tools/agent/workflow.py` — create_and_monitor composition

**Step 1: Rebase onto master (after PR #54 merge)**
```bash
git checkout claude/happy-bhaskara
git rebase master
```

**Step 2: Resolve conflicts and fix CI**
Conflicts likely in: `server.py`, `client.py`, `dependencies.py`, tool files.
Priority: keep PR #55 changes when they extend PR #54 work.

**Step 3: Run full quality gate**
```bash
uv run ruff check . && uv run mypy bridge/ && uv run pytest -v
```

**Step 4: Merge to master**
```bash
gh pr merge 55 --squash
```

---

### Task 0.4: Evaluate PR #56 (unlock potential)

Adds remote proxy, smart caching, elicitation safety.

**Step 1: Rebase onto master (after PR #55 merge)**
```bash
git checkout codegen-bot/unlock-full-potential-a3f8e2
git rebase master
```

**Step 2: Resolve conflicts, fix CI, verify**
```bash
uv run ruff check . && uv run mypy bridge/ && uv run pytest -v
```

**Step 3: Merge to master**
```bash
gh pr merge 56 --squash
```

**Step 4: Commit — Tag new baseline**
```bash
git tag v0.5.0-rc1
```

---

## Phase 1: Code Quality & Hardening

### Task 1.1: Decompose `codegen_create_run()` (222 LOC → helpers)

**Files:**
- Modify: `bridge/tools/agent/lifecycle.py`
- Create: `bridge/tools/agent/_helpers.py`
- Create: `tests/tools/agent/test_helpers.py`

**Step 1: Write failing tests for helper functions**
```python
# tests/tools/agent/test_helpers.py
import os
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "12345"

import pytest
from bridge.tools.agent._helpers import (
    enrich_prompt_from_execution,
    detect_or_confirm_repo,
    select_model,
)

async def test_enrich_prompt_no_execution():
    result = await enrich_prompt_from_execution(
        prompt="fix bug", execution_id=None, registry=mock_registry
    )
    assert result == "fix bug"

async def test_enrich_prompt_with_execution():
    registry = make_registry_with_execution("exec-1", task_prompts=["do X"])
    result = await enrich_prompt_from_execution(
        prompt="fix bug", execution_id="exec-1", registry=registry, task_index=0
    )
    assert "do X" in result

async def test_detect_repo_explicit_id():
    result = await detect_or_confirm_repo(repo_id=42, repo_cache=mock_cache, ctx=mock_ctx)
    assert result == 42

async def test_detect_repo_auto_detection():
    cache = make_cache_with_detected_repo(99)
    result = await detect_or_confirm_repo(repo_id=None, repo_cache=cache, ctx=mock_ctx)
    assert result == 99
```

**Step 2: Run tests to verify they fail**
```bash
uv run pytest tests/tools/agent/test_helpers.py -v
```
Expected: FAIL — `_helpers` module doesn't exist

**Step 3: Extract helpers from lifecycle.py**
```python
# bridge/tools/agent/_helpers.py
"""Helper functions extracted from codegen_create_run for testability."""

from __future__ import annotations

import json
from typing import Any

from bridge.context import ContextRegistry
from bridge.helpers.repo_detection import RepoCache

async def enrich_prompt_from_execution(
    prompt: str,
    execution_id: str | None,
    registry: ContextRegistry,
    task_index: int | None = None,
) -> str:
    """Enrich prompt with execution context if available."""
    if not execution_id:
        return prompt
    exec_ctx = await registry.get_context(execution_id)
    if not exec_ctx or not exec_ctx.task_prompts:
        return prompt
    if task_index is not None and task_index < len(exec_ctx.task_prompts):
        return exec_ctx.task_prompts[task_index]
    return prompt

async def detect_or_confirm_repo(
    repo_id: int | None,
    repo_cache: RepoCache,
    ctx: Any,
    client: Any | None = None,
) -> int | None:
    """Detect repo from git remote or use explicit repo_id."""
    if repo_id is not None:
        return repo_id
    detected = await repo_cache.get_repo_id()
    return detected

async def select_model(
    model: str | None,
    ctx: Any,
) -> str | None:
    """Select model, optionally via elicitation."""
    return model  # Default: pass through, elicitation handled by caller
```

**Step 4: Refactor lifecycle.py to use helpers**
Replace inline logic in `codegen_create_run()` with calls to helper functions.
Target: `codegen_create_run()` should be <80 LOC.

**Step 5: Run all tests**
```bash
uv run pytest tests/tools/agent/ -v
uv run pytest -v  # full suite
```
Expected: All pass

**Step 6: Commit**
```bash
git add bridge/tools/agent/_helpers.py tests/tools/agent/test_helpers.py bridge/tools/agent/lifecycle.py
git commit -m "refactor(tools): extract create_run helpers for testability"
```

---

### Task 1.2: Replace Bare Exception Handlers (13 locations)

**Files:**
- Modify: `bridge/server.py` (2 places)
- Modify: `bridge/middleware/authorization.py` (1)
- Modify: `bridge/providers/agents.py`, `commands.py` (2)
- Modify: `bridge/elicitation.py` (3)
- Modify: `bridge/telemetry/helpers.py` (1)
- Modify: `bridge/helpers/repo_detection.py` (1)
- Modify: `bridge/client.py` (1)
- Modify: `bridge/sampling/tools.py` (1)
- Modify: `bridge/openapi_utils.py` (1)

**Step 1: Write test for exception specificity**
```python
# tests/test_exception_handling.py
import ast
import pathlib

def test_no_bare_except_exception():
    """All except clauses should catch specific exceptions, not bare Exception."""
    bridge_dir = pathlib.Path("bridge")
    violations = []
    for py_file in bridge_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type and isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    # Check if there's a comment justifying it
                    violations.append(f"{py_file}:{node.lineno}")
    # Allow max 3 justified bare Exception handlers (e.g., top-level error boundaries)
    assert len(violations) <= 3, f"Too many bare 'except Exception': {violations}"
```

**Step 2: Run test to see current violations**
```bash
uv run pytest tests/test_exception_handling.py -v
```
Expected: FAIL with 13 violations

**Step 3: Fix each violation**

Pattern for provider/middleware (graceful degradation):
```python
# BEFORE
except Exception:
    logger.warning("Provider failed")

# AFTER
except (ImportError, FileNotFoundError, ValueError) as e:
    logger.warning("Provider failed: %s: %s", type(e).__name__, e)
except Exception:
    logger.exception("Unexpected error in provider")  # keeps traceback
```

Pattern for elicitation (client doesn't support it):
```python
# BEFORE
except Exception:
    return default

# AFTER
except (NotImplementedError, AttributeError, RuntimeError) as e:
    logger.debug("Elicitation not supported: %s", e)
    return default
```

**Step 4: Run test to verify ≤3 violations**
```bash
uv run pytest tests/test_exception_handling.py -v
```
Expected: PASS

**Step 5: Run full suite**
```bash
uv run pytest -v
```

**Step 6: Commit**
```bash
git add bridge/ tests/test_exception_handling.py
git commit -m "fix: replace bare except Exception with specific handlers"
```

---

### Task 1.3: Unify HTTP Client Helpers

**Files:**
- Modify: `bridge/client.py`
- Test: `tests/test_client.py`

**Step 1: Write test for unified helper**
```python
# In tests/test_client.py
@respx.mock
async def test_request_json_get():
    respx.get("https://api.codegen.com/api/v1/test").mock(
        return_value=Response(200, json={"ok": True})
    )
    client = CodegenClient(api_key="key", org_id=1)
    result = await client._request_json("GET", "/v1/test")
    assert result == {"ok": True}
    await client.close()
```

**Step 2: Implement unified `_request_json()`**
```python
# In bridge/client.py — replace _get, _post, _put, _patch, _delete
async def _request_json(
    self,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Unified HTTP helper — sends request, returns parsed JSON."""
    resp = await self._request(method, path, json=json_body, params=params)
    return resp.json()  # type: ignore[no-any-return]
```

**Step 3: Replace all _get/_post/_put/_patch/_delete calls**
Use find-replace in client.py:
- `await self._get(path)` → `await self._request_json("GET", path)`
- `await self._post(path, json=data)` → `await self._request_json("POST", path, json_body=data)`
- etc.

**Step 4: Run tests**
```bash
uv run pytest tests/test_client.py -v
uv run pytest -v
```

**Step 5: Commit**
```bash
git add bridge/client.py tests/test_client.py
git commit -m "refactor(client): unify HTTP helpers into _request_json()"
```

---

## Phase 2: New FastMCP 3.x Capabilities

### Task 2.1: Full Transforms Configuration (Task 8)

**Files:**
- Modify: `bridge/transforms/config.py`
- Modify: `bridge/transforms/registry.py`
- Create: `tests/transforms/test_full_config.py`

**Step 1: Write tests for transform configuration**
```python
# tests/transforms/test_full_config.py
from bridge.transforms.config import TransformsConfig, NamespaceConfig, VisibilityConfig
from bridge.transforms.registry import configure_transforms
from fastmcp import FastMCP

async def test_namespace_adds_prefix():
    mcp = FastMCP("test")
    @mcp.tool()
    def my_tool() -> str:
        return "ok"
    configure_transforms(mcp, TransformsConfig(
        namespace=NamespaceConfig(prefix="codegen")
    ))
    tools = await mcp.list_tools()
    assert any(t.name == "codegen_my_tool" for t in tools)

async def test_visibility_hides_internal_tools():
    mcp = FastMCP("test")
    @mcp.tool(tags={"internal"})
    def debug_tool() -> str:
        return "debug"
    @mcp.tool(tags={"public"})
    def public_tool() -> str:
        return "public"
    configure_transforms(mcp, TransformsConfig(
        visibility=VisibilityConfig(hidden_tags={"internal"})
    ))
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert "debug_tool" not in names
    assert "public_tool" in names

async def test_version_filter_gates_experimental():
    mcp = FastMCP("test")
    @mcp.tool(version="1.0")
    def stable_tool() -> str:
        return "stable"
    @mcp.tool(version="2.0")
    def experimental_tool() -> str:
        return "experimental"
    configure_transforms(mcp, TransformsConfig(
        version_filter=VersionFilterConfig(version_lt="2.0")
    ))
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert "stable_tool" in names
    assert "experimental_tool" not in names
```

**Step 2: Run tests — expect failure**
```bash
uv run pytest tests/transforms/test_full_config.py -v
```

**Step 3: Implement transform configuration**
```python
# bridge/transforms/config.py — extend existing
from dataclasses import dataclass, field
from fastmcp.server.transforms import Namespace, VersionFilter

@dataclass
class NamespaceConfig:
    prefix: str = ""
    enabled: bool = False

@dataclass
class VisibilityConfig:
    hidden_tags: set[str] = field(default_factory=set)
    hidden_names: set[str] = field(default_factory=set)
    enabled: bool = False

@dataclass
class VersionFilterConfig:
    version_lt: str | None = None
    version_gte: str | None = None
    include_unversioned: bool = True
    enabled: bool = False

@dataclass
class TransformsConfig:
    namespace: NamespaceConfig = field(default_factory=NamespaceConfig)
    visibility: VisibilityConfig = field(default_factory=VisibilityConfig)
    version_filter: VersionFilterConfig = field(default_factory=VersionFilterConfig)
```

Update `configure_transforms()` in registry.py to apply each enabled transform.

**Step 4: Run tests**
```bash
uv run pytest tests/transforms/ -v
uv run pytest -v
```

**Step 5: Commit**
```bash
git add bridge/transforms/ tests/transforms/
git commit -m "feat(transforms): full Namespace, Visibility, VersionFilter configuration"
```

---

### Task 2.2: Background Tasks with `@mcp.tool(task=True)` (Task 4 upgrade)

**Files:**
- Modify: `bridge/tools/agent/monitor.py` (if exists from PR #54)
- Create: `bridge/tools/agent/background.py` (if not from PR)
- Test: `tests/tools/agent/test_background.py`

**Note:** PR #54 may already have `codegen_monitor_run`. This task upgrades it to use FastMCP native `task=True` + `Progress` dependency instead of manual polling.

**Step 1: Write test for native background task**
```python
# tests/tools/agent/test_background.py
from fastmcp import Client

async def test_monitor_run_returns_task():
    async with Client(mcp) as c:
        # Start monitoring as background task
        task = await c.call_tool(
            "codegen_monitor_run",
            {"run_id": 42},
            task=True,
        )
        assert task.task_id is not None
        # Should return immediately (background)
        assert task.returned_immediately
```

**Step 2: Implement with FastMCP native API**
```python
# bridge/tools/agent/background.py
from fastmcp.dependencies import Progress

@mcp.tool(task=True, tags={"agent", "monitoring"})
async def codegen_monitor_run(
    run_id: int,
    poll_interval: int = 10,
    max_polls: int = 60,
    progress: Progress = Progress(),
    ctx: Context = CurrentContext(),
    client: CodegenClient = Depends(get_client),
) -> str:
    """Monitor an agent run until completion. Runs in background with progress."""
    await progress.set_total(max_polls)
    for i in range(max_polls):
        run = await client.get_run(run_id)
        status = run.get("status", "unknown")
        await progress.set_message(f"Run {run_id}: {status}")
        await progress.increment()
        if status in ("completed", "failed", "cancelled"):
            return json.dumps({"run_id": run_id, "final_status": status, "run": run})
        await asyncio.sleep(poll_interval)
    return json.dumps({"run_id": run_id, "status": "timeout", "polls": max_polls})
```

**Step 3: Run tests**
```bash
uv run pytest tests/tools/agent/test_background.py -v
uv run pytest -v
```

**Step 4: Commit**
```bash
git add bridge/tools/agent/background.py tests/tools/agent/test_background.py
git commit -m "feat(monitoring): native FastMCP background tasks with Progress"
```

---

### Task 2.3: Upgrade Elicitation to Pydantic Schemas (Task 6 ext)

**Files:**
- Modify: `bridge/elicitation.py`
- Create: `tests/test_elicitation_schemas.py`

**Step 1: Write test for Pydantic-based elicitation**
```python
async def test_confirm_with_pydantic_schema():
    from pydantic import BaseModel
    class RepoChoice(BaseModel):
        repo_name: str
        confirm: bool = True
    # Mock ctx.elicit() to return accepted response
    result = await confirm_with_schema(
        mock_ctx, "Select repo", RepoChoice
    )
    assert isinstance(result, RepoChoice)

async def test_select_multiple_choices():
    result = await select_multiple(
        mock_ctx, "Select tools", ["tool-a", "tool-b", "tool-c"]
    )
    assert isinstance(result, list)
```

**Step 2: Implement enhanced elicitation**
```python
# bridge/elicitation.py — extend with Pydantic support
from pydantic import BaseModel
from typing import TypeVar

T = TypeVar("T", bound=BaseModel)

async def confirm_with_schema(
    ctx: Context,
    message: str,
    schema: type[T],
    default: T | None = None,
) -> T | None:
    """Elicit structured input from user using Pydantic model."""
    try:
        result = await ctx.elicit(message, response_type=schema)
        if result.action == "accept":
            return result.data
        return default
    except (NotImplementedError, AttributeError):
        return default

async def select_multiple(
    ctx: Context,
    message: str,
    choices: list[str],
    default: list[str] | None = None,
) -> list[str] | None:
    """Multi-choice elicitation."""
    from dataclasses import dataclass
    @dataclass
    class MultiSelect:
        selected: list[str]
    try:
        result = await ctx.elicit(
            f"{message}\nOptions: {', '.join(choices)}",
            response_type=MultiSelect,
        )
        if result.action == "accept":
            return result.data.selected
        return default
    except (NotImplementedError, AttributeError):
        return default
```

**Step 3: Run tests and commit**
```bash
uv run pytest tests/test_elicitation_schemas.py -v
uv run pytest -v
git add bridge/elicitation.py tests/test_elicitation_schemas.py
git commit -m "feat(elicitation): Pydantic schema support and multi-select"
```

---

## Phase 3: New Capabilities

### Task 3.1: Bulk Operations Tool (Task 7)

**Files:**
- Create: `bridge/tools/agent/bulk.py`
- Create: `tests/tools/agent/test_bulk.py`

**Step 1: Write failing test**
```python
# tests/tools/agent/test_bulk.py
@respx.mock
async def test_bulk_create_runs():
    for i in range(3):
        respx.post(f"https://api.codegen.com/api/v1/organizations/12345/agent/run").mock(
            return_value=Response(200, json={"id": i+1, "status": "running"})
        )
    async with Client(mcp) as c:
        result = await c.call_tool("codegen_bulk_create_runs", {
            "tasks": [
                {"prompt": "Fix bug A"},
                {"prompt": "Fix bug B"},
                {"prompt": "Fix bug C"},
            ]
        })
        data = json.loads(result[0].text)
        assert len(data["runs"]) == 3
        assert data["runs"][0]["status"] == "running"
```

**Step 2: Implement bulk create**
```python
# bridge/tools/agent/bulk.py
@mcp.tool(tags={"agent", "bulk"})
async def codegen_bulk_create_runs(
    tasks: list[dict[str, str]],
    repo_id: int | None = None,
    model: str | None = None,
    ctx: Context = CurrentContext(),
    client: CodegenClient = Depends(get_client),
) -> str:
    """Create multiple agent runs from a list of tasks (batch delegation)."""
    results = []
    total = len(tasks)
    for i, task in enumerate(tasks):
        await ctx.report_progress(i, total, f"Creating run {i+1}/{total}")
        run = await client.create_run(
            prompt=task["prompt"],
            repo_id=repo_id or task.get("repo_id"),
            model=model or task.get("model"),
        )
        results.append(run)
    return json.dumps({"runs": results, "total": total, "created": len(results)})
```

**Step 3: Run tests and commit**
```bash
uv run pytest tests/tools/agent/test_bulk.py -v
git add bridge/tools/agent/bulk.py tests/tools/agent/test_bulk.py
git commit -m "feat(tools): add codegen_bulk_create_runs for batch delegation"
```

---

### Task 3.2: Analytics Tool (Task 7)

**Files:**
- Create: `bridge/tools/analytics.py`
- Create: `tests/tools/test_analytics.py`

**Step 1: Write test**
```python
@respx.mock
async def test_get_run_analytics():
    respx.get("https://api.codegen.com/api/v1/organizations/12345/agent/runs").mock(
        return_value=Response(200, json={
            "items": [
                {"id": 1, "status": "completed", "created_at": "2026-03-01T00:00:00Z"},
                {"id": 2, "status": "failed", "created_at": "2026-03-02T00:00:00Z"},
                {"id": 3, "status": "completed", "created_at": "2026-03-03T00:00:00Z"},
            ],
            "total": 3, "page": 1, "size": 100, "pages": 1,
        })
    )
    async with Client(mcp) as c:
        result = await c.call_tool("codegen_get_run_analytics", {})
        data = json.loads(result[0].text)
        assert data["total_runs"] == 3
        assert data["success_rate"] == pytest.approx(0.667, abs=0.01)
```

**Step 2: Implement analytics tool**
```python
# bridge/tools/analytics.py
@mcp.tool(tags={"analytics"})
async def codegen_get_run_analytics(
    ctx: Context = CurrentContext(),
    client: CodegenClient = Depends(get_client),
    org_id: int = Depends(get_org_id),
) -> str:
    """Aggregate stats: total runs, success rate, status distribution."""
    runs = await client.list_runs(limit=100)
    items = runs.get("items", [])
    statuses = [r.get("status") for r in items]
    completed = statuses.count("completed")
    failed = statuses.count("failed")
    total = len(statuses)
    return json.dumps({
        "total_runs": total,
        "success_rate": completed / total if total > 0 else 0,
        "status_distribution": {s: statuses.count(s) for s in set(statuses)},
        "completed": completed,
        "failed": failed,
    })
```

**Step 3: Test and commit**
```bash
uv run pytest tests/tools/test_analytics.py -v
git add bridge/tools/analytics.py tests/tools/test_analytics.py
git commit -m "feat(tools): add codegen_get_run_analytics for run statistics"
```

---

### Task 3.3: Integration Health Check (Task 9)

**Files:**
- Modify: `bridge/tools/integrations.py`
- Test: `tests/tools/test_integrations.py`

**Step 1: Write test**
```python
@respx.mock
async def test_check_integration_health():
    respx.get("https://api.codegen.com/api/v1/organizations/12345/integrations").mock(
        return_value=Response(200, json={
            "integrations": [
                {"integration_type": "github", "active": True},
                {"integration_type": "slack", "active": False},
            ]
        })
    )
    async with Client(mcp) as c:
        result = await c.call_tool("codegen_check_integration_health", {})
        data = json.loads(result[0].text)
        assert data["github"]["status"] == "active"
        assert data["slack"]["status"] == "inactive"
```

**Step 2: Implement health check**
```python
@mcp.tool(tags={"integrations"})
async def codegen_check_integration_health(
    ctx: Context = CurrentContext(),
    client: CodegenClient = Depends(get_client),
    org_id: int = Depends(get_org_id),
) -> str:
    """Check health of all configured integrations."""
    integrations = await client.get_integrations(org_id)
    health = {}
    for integ in integrations.get("integrations", []):
        name = integ.get("integration_type", "unknown")
        health[name] = {
            "status": "active" if integ.get("active") else "inactive",
            "type": name,
        }
    return json.dumps(health)
```

**Step 3: Test and commit**
```bash
uv run pytest tests/tools/test_integrations.py -v
git add bridge/tools/integrations.py tests/tools/test_integrations.py
git commit -m "feat(integrations): add health check tool"
```

---

## Phase 4: Telemetry & Storage (Task 12)

### Task 4.1: Complete OpenTelemetry Configuration

**Files:**
- Modify: `bridge/telemetry/config.py`
- Modify: `bridge/telemetry/helpers.py`
- Create: `tests/telemetry/test_otel_config.py`

**Step 1: Write test**
```python
async def test_telemetry_span_attributes():
    from bridge.telemetry.helpers import create_tool_span
    span = create_tool_span("codegen_create_run", run_id=42, org_id=12345)
    assert span.attributes["tool.name"] == "codegen_create_run"
    assert span.attributes["run.id"] == 42
    assert span.attributes["org.id"] == 12345
```

**Step 2: Implement span helpers**
Use FastMCP's `server_span()` context manager with custom attributes.
Configure OTLP exporter when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

**Step 3: Test and commit**
```bash
uv run pytest tests/telemetry/ -v
git add bridge/telemetry/ tests/telemetry/
git commit -m "feat(telemetry): complete OpenTelemetry config with tool span attributes"
```

---

### Task 4.2: Storage TTL and Health Check

**Files:**
- Modify: `bridge/storage.py`
- Create: `tests/test_storage_ttl.py`

**Step 1: Write test for TTL expiry**
```python
async def test_storage_ttl_expiry():
    storage = MemoryStorage(ttl_seconds=1)
    await storage.set("key", "value")
    assert await storage.get("key") == "value"
    await asyncio.sleep(1.1)
    assert await storage.get("key") is None
```

**Step 2: Add TTL to MemoryStorage and FileStorage**
**Step 3: Test and commit**

---

## Phase 5: Skills & Plugin (Tasks 10-11)

### Task 5.1: Update Executing-via-Codegen Skill

**Files:**
- Modify: `skills/executing-via-codegen/SKILL.md`

Add references to:
- `codegen_monitor_run` (background task monitoring from Task 2.2)
- `codegen_bulk_create_runs` (batch delegation from Task 3.1)
- `codegen_get_run_analytics` (analytics from Task 3.2)
- Model selection via `codegen_get_models`

---

### Task 5.2: New Bulk Delegation Skill

**Files:**
- Create: `skills/bulk-delegation/SKILL.md`

Content: Step-by-step guide for using `codegen_bulk_create_runs` to delegate multiple tasks.

---

### Task 5.3: New Run Analytics Skill

**Files:**
- Create: `skills/run-analytics/SKILL.md`

Content: How to use `codegen_get_run_analytics` for insights.

---

### Task 5.4: Plugin Structure Update

**Files:**
- Modify: `plugin.json` — version bump, add new skills
- Modify: `hooks/hooks.json` — add new hook events if applicable
- Consider adding `${CLAUDE_PLUGIN_DATA}` for persistent storage

---

## Phase 6: Documentation (Task 13)

### Task 6.1: Architecture Documentation
**File:** `docs/architecture.md`

### Task 6.2: API Reference
**File:** `docs/api-reference.md`

### Task 6.3: Development Guide
**File:** `docs/development.md`

### Task 6.4: Operational Runbooks
**Files:** `docs/runbooks/rate-limiting.md`, `auth-failure.md`, `openapi-drift.md`

### Task 6.5: Update README
**File:** `README.md`

### Task 6.6: Changelog
**File:** `CHANGELOG.md`

---

## Execution Plan

```text
Phase 0: PR Triage (sequential)
  Task 0.1: Merge PR #53 (trivial)
  Task 0.2: Fix & merge PR #54 (v0.5.0 release)
  Task 0.3: Rebase & merge PR #55 (architecture)
  Task 0.4: Rebase & merge PR #56 (unlock potential)
    ↓ (new baseline: v0.5.0-rc1)

Phase 1: Code Quality (parallel after Phase 0)
  Task 1.1: Decompose create_run helpers
  Task 1.2: Fix bare exception handlers
  Task 1.3: Unify HTTP client helpers
    ↓

Phase 2: FastMCP 3.x Features (parallel)
  Task 2.1: Full transforms config
  Task 2.2: Native background tasks
  Task 2.3: Pydantic elicitation
    ↓

Phase 3: New Capabilities (parallel)
  Task 3.1: Bulk operations
  Task 3.2: Analytics
  Task 3.3: Integration health
    ↓

Phase 4: Telemetry & Storage (parallel)
  Task 4.1: OpenTelemetry config
  Task 4.2: Storage TTL
    ↓

Phase 5: Skills & Plugin (sequential)
  Tasks 5.1–5.4
    ↓

Phase 6: Documentation (sequential)
  Tasks 6.1–6.6
```

## Quality Gates (per task)

Before committing:
1. `uv run pytest -q` — all tests pass
2. `uv run ruff check .` — no lint errors
3. `uv run mypy bridge/` — no type errors
4. New code has test coverage

## Constraints

- **Always** use `uv run` (never bare python/pytest)
- **Never** break existing tests
- **Conventional commits** format
- **One commit per logical change**

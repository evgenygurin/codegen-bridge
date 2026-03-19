# AGENTS.md

Rules for Codegen cloud agents working on this repository. Read this file completely before taking any action.

---

## Setup (FIRST step in every sandbox session)

```bash
uv sync --dev
```

Never `pip install`. Never bare `python`, `pytest`, `ruff`, `mypy`. Always `uv run <command>`.

**If you see `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`:**
```bash
uv sync --dev --reinstall
```

---

## Commands

```bash
uv sync --dev                          # Install deps (ALWAYS first)
uv run pytest -v                       # All tests
uv run pytest tests/test_server.py -v  # Single file
uv run ruff check .                    # Lint
uv run ruff check . --fix              # Lint + auto-fix
uv run ruff format .                   # Format
uv run mypy bridge/                    # Type check (strict)
```

**Full CI check before every PR:**
```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy bridge/ && uv run pytest -v
```

---

## Required Env Vars (for tests: mock these, don't need real values)

| Var | Required | Description |
|-----|----------|-------------|
| `CODEGEN_API_KEY` | Yes | Bearer token from codegen.com |
| `CODEGEN_ORG_ID` | Yes | Organization ID (integer) |
| `CODEGEN_ALLOW_DANGEROUS_TOOLS` | No | `"true"` to skip dangerous tool guard |

**In tests — set BEFORE any bridge import:**
```python
import os
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "12345"
# Only NOW import bridge modules:
from bridge.server import mcp
```

Never `os.environ.setdefault()` — use direct assignment.

---

## Architecture

```text
bridge/
├── server.py         — FastMCP instance, lifespan, registration order
├── client.py         — Async httpx REST client → Codegen API v1
├── models.py         — Pydantic response types (NOT types.py — stdlib shadow)
├── annotations.py    — 6 ToolAnnotations presets (READ_ONLY, CREATES, MUTATES, DESTRUCTIVE)
├── rate_budget.py    — OutboundRateBudget — token-bucket for API calls
├── dependencies.py   — DI: get_client, get_org_id, get_registry, get_repo_cache, get_sampling_config, get_run_service, get_execution_service, get_session_state
├── context.py        — ExecutionContext, TaskContext, ContextRegistry
├── elicitation.py    — confirm_action, confirm_with_schema, select_choice, select_multiple (Pydantic)
├── storage.py        — MemoryStorage / FileStorage (Strategy, py-key-value-aio, TTL support)
├── openapi_utils.py  — Load openapi_spec.json, patch {org_id}, build OpenAPIProvider
├── prompt_builder.py — Static prompt assembly for agent tasks
├── log_parser.py     — Structured parsing of agent execution logs
├── settings.py       — App configuration (reads env vars at import time)
├── services/         — RunService (runs.py), ExecutionService (execution.py)
├── tools/            — 8 modules, 49 manual tools total
│   ├── agent/        — 13 tools (create, get, list, resume, stop, ban, unban, remove, logs, monitor, bulk, workflow, report)
│   ├── execution.py  — 3 tools (start, get_context, get_rules)
│   ├── pr.py         — 2 tools (edit_pr, edit_pr_simple)
│   ├── setup/        — 13 tools (users, orgs, repos, oauth, check_suite, models, setup_commands)
│   ├── integrations.py — 8 tools (integrations, webhooks, sandbox, slack, health_check)
│   ├── analytics.py  — 1 tool (get_run_analytics)
│   ├── settings.py   — 2 tools (get, update)
│   └── session.py    — 3 tools (set, get, clear preferences)
├── sampling/         — 4 tools via ctx.sample(), SamplingService
├── middleware/       — 9-layer stack (error→ping→auth→log→telemetry→timing→ratelimit→cache→limit)
├── transforms/       — 4 stages (Namespace→ToolTransform→Visibility→VersionFilter)
├── providers/        — OpenAPIProvider, SkillsDir, Commands, Agents, Remote proxy
├── resources/        — 8 resources: config(3) + platform(2) + templates(3)
├── prompts/          — 8 prompt templates for workflows
├── helpers/          — formatting, pagination, repo_detection
└── telemetry/        — OpenTelemetry OTLP config, span helpers, middleware
```

**Data flow:**
```text
Claude Code → FastMCP → Middleware (9 layers) → Tool Function → CodegenClient → Codegen API
                      → Transforms (4 stages) ↗
```

---

## Tool Writing Pattern

```python
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.models import CodegenClient

def register_example_tools(mcp: FastMCP) -> None:
    @mcp.tool(tags={"example"})
    async def codegen_example_action(
        run_id: int,                                           # visible to MCP client
        ctx: Context = CurrentContext(),                       # injected by FastMCP
        client: CodegenClient = Depends(get_client),          # type: ignore[arg-type]
    ) -> str:                                                  # ALWAYS return json.dumps(...)
        result = await client.get_run(run_id)
        return json.dumps({"id": result.id, "status": result.status})
```

**Rules:**
- Tool names: `codegen_<verb>_<noun>` — verbs: `create`, `get`, `list`, `update`, `delete`, `set`, `start`, `stop`, `resume`, `ban`, `unban`, `edit`, `generate`, `analyse`, `summarise`
- Return type is ALWAYS `str` with `json.dumps(...)` — never raw dicts
- `# type: ignore[arg-type]` after every `Depends()` call (mypy limitation)
- B008 suppressed in `pyproject.toml` for `bridge/tools/*.py`, `bridge/dependencies.py`, `bridge/resources/*.py`, `bridge/sampling/tools.py`

---

## Dangerous Tool Pattern

Three-layer protection for destructive ops:

```python
from bridge.elicitation import confirm_action

@mcp.tool(tags={"dangerous"})
async def codegen_stop_run(
    run_id: int,
    confirmed: bool = False,
    ctx: Context = CurrentContext(),
    client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
) -> str:
    if not confirmed:
        if not await confirm_action(ctx, f"Stop agent run {run_id}?"):
            return json.dumps({"cancelled": True})
    result = await client.stop_run(run_id)
    return json.dumps(result)
```

---

## Pagination Pattern

```python
@mcp.tool()
async def codegen_list_runs(
    cursor: str | None = None,
    limit: int = 10,
    ctx: Context = CurrentContext(),
    client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
) -> str:
    result = await client.list_runs(cursor=cursor, limit=limit)
    return json.dumps({
        "runs": [r.model_dump() for r in result.items],
        "next_cursor": result.next_cursor,
        "has_more": result.has_more,
    })
```

---

## Testing Patterns

- `respx` for HTTP mocking (not httpx built-in)
- In-memory MCP client: `async with Client(mcp) as c:` — full lifespan runs
- `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed
- Test structure mirrors `bridge/` exactly (e.g. `tests/tools/test_agent.py` mirrors `bridge/tools/agent.py`)

```python
# Standard integration test
import os
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "12345"

import pytest
import respx
import httpx
from fastmcp import Client
from bridge.server import mcp

async def test_list_runs():
    with respx.mock:
        respx.get("https://api.codegen.com/v1/organizations/12345/agent-runs").mock(
            return_value=httpx.Response(200, json={"items": [], "next_cursor": None})
        )
        async with Client(mcp) as client:
            result = await client.call_tool("codegen_list_runs", {})
            assert not result.is_error

# Storage: use MemoryStorage in tests, FileStorage in production
storage = MemoryStorage()   # tests
storage = FileStorage()     # production
registry = ContextRegistry(storage=storage)
```

---

## Scope Rules

1. Only touch files relevant to the task — read the task description carefully
2. Do NOT modify: `AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md` (unless explicitly asked)
3. Do NOT add OpenTelemetry/telemetry unless explicitly asked
4. Do NOT modify unrelated test files
5. Run tests after every change — if they passed before, they must pass after
6. PR targets `master` branch

---

## Registration Order in server.py

```python
configure_middleware(mcp)          # 1. Middleware stack (outermost first)
register_agent_tools(mcp)          # 2. Tool groups
register_execution_tools(mcp)
register_pr_tools(mcp)
register_setup_tools(mcp)
register_integration_tools(mcp)
register_analytics_tools(mcp)
register_settings_tools(mcp)
register_session_tools(mcp)
register_resources(mcp)            # 3. Resources
register_prompts(mcp)              # 4. Prompts
register_sampling_tools(mcp)       # 5. Sampling
configure_transforms(mcp)          # 6. Transforms
# In lifespan:
server.add_provider(openapi_provider)    # 7. Providers
server.add_provider(skills_provider)
server.add_provider(commands_provider)
server.add_provider(agents_provider)
# Optional: server.mount(remote_proxy)  # 8. Remote proxy (CODEGEN_ENABLE_REMOTE_PROXY=true)
```

## Adding New Code

| Task | Location | Pattern |
|------|----------|---------|
| New tool | `bridge/tools/<module>.py` | `register_*_tools(mcp)` function |
| New resource | `bridge/resources/` | `register_resources(mcp)` |
| New provider | `bridge/providers/` | `server.add_provider()` in lifespan |
| New middleware | `bridge/middleware/` | Add to `configure_middleware()` |
| New command | `commands/<name>.md` | Auto-discovered by `CommandsProvider` |
| New agent | `agents/<name>.md` | Auto-discovered by `AgentsProvider` |
| New skill | `skills/<name>/SKILL.md` | Auto-discovered by `SkillsDirectoryProvider` |

---

## PR Checklist

Before creating a PR, ALL of these must pass:

```bash
uv run ruff check .             # zero errors
uv run ruff format --check .    # no formatting issues
uv run mypy bridge/             # zero type errors
uv run pytest -v                # all tests pass
```

- PR title: `feat:`, `fix:`, `chore:`, `test:`, `docs:` format
- PR base branch: `master`
- Do not include unrelated files in the diff

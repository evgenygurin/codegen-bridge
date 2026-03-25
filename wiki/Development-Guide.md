# Development Guide

Guide for contributing to Codegen Bridge — setup, testing, adding new components, and coding patterns.

## Development Setup

### Prerequisites

- Python 3.12+ (pinned in `.python-version`)
- [uv](https://docs.astral.sh/uv/) package manager
- Git

### Install Dependencies

```bash
cd codegen-bridge
uv sync --dev
```

### Common Commands

```bash
# Run all tests (1382 tests, parallel via xdist)
uv run pytest -v

# Run a single test file
uv run pytest tests/test_server.py -v

# Run a single test
uv run pytest tests/test_server.py::test_lifespan_yields_client -v

# Lint
uv run ruff check .

# Lint + auto-fix
uv run ruff check . --fix

# Format
uv run ruff format .

# Type checking (strict mode)
uv run mypy bridge/

# Run MCP server directly (for debugging)
uv run python -m bridge.server

# Full CI check before PR
uv run ruff check . && uv run ruff format --check . && uv run mypy bridge/ && uv run pytest -v
```

> **Critical:** Always use `uv run` — never bare `python`, `pytest`, `ruff`, or `mypy`. The sandbox may have Python 3.13 system-wide, but the project requires 3.12.

---

## Code Style

| Setting | Value |
|---------|-------|
| Line length | 99 |
| Target | Python 3.12 |
| Linter | Ruff: `E, F, W, I, N, UP, B, SIM, RUF` |
| Type checker | mypy strict mode |
| Entry point | `python -m bridge.server` (not `python bridge/server.py`) |

### B008 Suppression

`Depends()` and `CurrentContext()` in default args triggers ruff B008. Suppressed in `pyproject.toml`:

```toml
[tool.ruff.lint.per-file-ignores]
"bridge/dependencies.py" = ["B008"]
"bridge/tools/*.py" = ["B008"]
"bridge/tools/**/*.py" = ["B008"]
"bridge/resources/*.py" = ["B008"]
"bridge/sampling/tools.py" = ["B008"]
```

### mypy Configuration

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unreachable = true
show_error_codes = true
```

---

## Testing

### Structure

Tests mirror the `bridge/` directory structure:

```
tests/
├── conftest.py                 # Shared fixtures
├── test_server.py              # Server + lifespan tests
├── test_client.py              # CodegenClient tests
├── test_context.py             # ContextRegistry tests
├── test_dependencies.py        # DI provider tests
├── tools/                      # Tool tests (one per module)
│   ├── test_agent.py
│   ├── test_execution.py
│   ├── test_pr.py
│   ├── test_setup.py
│   ├── test_integrations.py
│   └── test_settings.py
├── middleware/                  # Middleware tests
├── transforms/                 # Transform tests
├── providers/                  # Provider tests
├── resources/                  # Resource tests
├── sampling/                   # Sampling tests
├── helpers/                    # Helper tests
├── prompts/                    # Prompt tests
└── telemetry/                  # Telemetry tests
```

### Critical: Environment Variables Before Import

The server reads env vars at **module level** (import time). Tests **must** set them before importing:

```python
# tests/test_server.py — TOP OF FILE, before any bridge imports
import os
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "12345"

# Now safe to import
from bridge.server import mcp
```

Then **also** use `monkeypatch.setenv()` in an autouse fixture for isolation:

```python
@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "12345")
```

> **Never use `os.environ.setdefault()`** — the user may have real env vars that must be overridden.

### HTTP Mocking with respx

Use **respx** (not httpx's built-in mock):

```python
import respx
from httpx import Response

@respx.mock
async def test_creates_run():
    respx.post("https://api.codegen.com/api/v1/organizations/12345/agent/run").mock(
        return_value=Response(200, json={"id": 1, "status": "running"})
    )
    ...
```

### In-Memory MCP Client

Test tools with full lifespan support:

```python
from fastmcp import Client

async def test_tool_via_mcp():
    async with Client(mcp) as c:
        result = await c.call_tool("codegen_get_run", {"run_id": 42})
        assert "status" in result[0].text
```

### Async Testing

`asyncio_mode = "auto"` in `pyproject.toml` — no `@pytest.mark.asyncio` decorator needed. All `async def test_*` run automatically.

---

## Adding New Components

### Adding a New Tool

1. Choose the right module in `bridge/tools/` (or create new)
2. Define inside a `register_*_tools(mcp: FastMCP)` function
3. Use `@mcp.tool()` decorator with `tags` and annotation
4. Add DI parameters with `# type: ignore[arg-type]`
5. Return `json.dumps(...)` — never raw dicts
6. If dangerous: add `tags={"dangerous"}` and use `confirm_action()`
7. Register in `server.py` if new module
8. Add tests in `tests/tools/`

```python
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.annotations import READ_ONLY

def register_example_tools(mcp: FastMCP) -> None:
    @mcp.tool(tags={"example"}, annotations=READ_ONLY)
    async def codegen_example_action(
        run_id: int,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        result = await client.get_run(run_id)
        return json.dumps({"id": result.id, "status": result.status})
```

### Adding a New Resource

1. Create in `bridge/resources/`
2. Register via `register_resources(mcp)` function
3. Add corresponding tests

### Adding a New Skill

1. Create `skills/<name>/SKILL.md`
2. Add YAML frontmatter: `name`, `description`, `user-invocable`
3. `SkillsDirectoryProvider` auto-discovers it

### Adding a New Command

1. Create `commands/<name>.md`
2. Add YAML frontmatter: `description`
3. `CommandsProvider` auto-discovers it

### Adding a New Agent

1. Create `agents/<name>.md`
2. Add YAML frontmatter: `name`, `description`
3. `AgentsProvider` auto-discovers it

### Adding a New Hook

1. Add entry to `hooks/hooks.json` under appropriate event type
2. Create script in `hooks/scripts/` if needed
3. Use `mcp__.*tool_name` regex matcher pattern
4. Test with `uv run pytest tests/test_hooks.py -v`

### Adding a New Middleware

1. Create in `bridge/middleware/`
2. Add to `configure_middleware()` in the correct position
3. Add tests in `tests/middleware/`

### Adding a New Provider

1. Create in `bridge/providers/`
2. Register via `server.add_provider()` in lifespan
3. Handle failures gracefully (log and skip)

---

## Key Design Patterns

### Lifespan + DI

Server lifespan creates resources → yields dict → tools access via `Depends()`:

```python
@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    client = CodegenClient(api_key=api_key, org_id=org_id)
    yield {"client": client, "org_id": org_id, ...}
```

### Service Layer

Business logic in `bridge/services/`, tools are thin wrappers:

```python
# Service owns the logic
class RunService:
    async def get_run(self, run_id: int) -> RunResult: ...

# Tool is a thin wrapper
@mcp.tool()
async def codegen_get_run(run_id: int, ...,
    service: RunService = Depends(get_run_service),  # type: ignore[arg-type]
) -> str:
    result = await service.get_run(run_id)
    return json.dumps(result)
```

### Elicitation for Dangerous Tools

Three-layer protection:

```python
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
    ...
```

### Storage Strategy

```python
storage = MemoryStorage()    # tests
storage = FileStorage()      # production
registry = ContextRegistry(storage=storage)
```

### Pagination

```python
@mcp.tool()
async def codegen_list_runs(
    cursor: str | None = None,
    limit: int = 10,
    ...
) -> str:
    result = await client.list_runs(cursor=cursor, limit=limit)
    return json.dumps({
        "runs": [...],
        "next_cursor": result.next_cursor,
        "has_more": result.has_more,
    })
```

---

## PR Checklist

Before creating a PR, **all** of these must pass:

```bash
uv run ruff check .             # zero errors
uv run ruff format --check .    # no formatting issues
uv run mypy bridge/             # zero type errors
uv run pytest -v                # all tests pass
```

- PR title: `feat:`, `fix:`, `chore:`, `test:`, `docs:` format
- PR base branch: `master`
- Do not include unrelated files in the diff

---

## See Also

- **[[Architecture]]** — System architecture and module map
- **[[Tools-Reference]]** — Complete tool documentation
- **[[Configuration]]** — Environment and settings reference

---
paths:
  - tests/**
---

# Testing

## Structure

Tests mirror `bridge/` structure:

```text
tests/
├── conftest.py                 # Shared fixtures
├── test_server.py              # Server + lifespan tests
├── test_client.py              # CodegenClient tests
├── test_context.py             # ContextRegistry tests
├── test_dependencies.py        # DI provider tests
├── test_elicitation.py         # Elicitation helper tests
├── test_storage.py             # Storage backend tests
├── test_hooks.py               # Hook scripts tests
├── test_models.py              # Pydantic model tests
├── test_openapi_utils.py       # OpenAPI spec + provider tests
├── test_settings.py            # Settings tests
├── test_log_parser.py          # Log parser tests
├── test_prompt_builder.py      # Prompt builder tests
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

## Critical: Environment Variables Before Import

Server reads env vars at **module level** (import time). Tests MUST set them before importing:

```python
# tests/test_server.py — TOP OF FILE, before any bridge imports
import os
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "12345"

# Now it's safe to import
from bridge.server import mcp
```

Then **also** use `monkeypatch.setenv()` in an autouse fixture for isolation:

```python
@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "12345")
```

**Never use `os.environ.setdefault()`** — the user has real env vars that must be overridden.

## HTTP Mocking with respx

Use **respx** (not httpx's built-in mock):

```python
import respx
from httpx import Response

@respx.mock
async def test_creates_run():
    respx.post("https://api.codegen.com/api/v1/organizations/12345/agent/run").mock(
        return_value=Response(200, json={"id": 1, "status": "running", ...})
    )
    ...
```

## In-Memory MCP Client

Test tools with full lifespan support:

```python
from fastmcp import Client

async def test_tool_via_mcp():
    async with Client(mcp) as c:
        result = await c.call_tool("codegen_get_run", {"run_id": 42})
        assert "status" in result[0].text
```

## Async Testing

`asyncio_mode = "auto"` in `pyproject.toml` — no need for `@pytest.mark.asyncio` decorator. All `async def test_*` functions run automatically.

## Lifespan Reset

When testing tools that depend on lifespan context, the in-memory client handles setup/teardown. For unit tests that mock at a lower level, ensure the lifespan dict keys match:

```python
{"client": mock_client, "org_id": 12345, "registry": mock_registry,
 "repo_cache": RepoCache(), "sampling_config": SamplingConfig()}
```

## Rules When Adding Tests

1. Mirror the source path: `bridge/tools/agent.py` → `tests/tools/test_agent.py`
2. Set env vars at module level AND in autouse fixture
3. Use `respx` for all HTTP mocking — mock exact URLs including org_id
4. Test both success and error paths
5. For tool tests: prefer in-memory client (`Client(mcp)`) over direct function calls
6. Run the full suite before committing: `uv run pytest -v`

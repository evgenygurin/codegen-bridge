---
paths:
  - pyproject.toml
  - .python-version
---

# Environment

## Python Version

- `.python-version` pinned to `3.12`
- `requires-python = ">=3.12"` in pyproject.toml
- mypy targets `python_version = "3.12"`

## Sandbox Pitfall: Python 3.13 vs 3.12

Codegen sandbox runs Python 3.13 system-wide, but the project requires 3.12. When `uv` creates a venv with 3.12, but something runs with system 3.13, **pydantic_core** compiled for 3.12 fails to load:

```text
ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'
```

**Fix:** Always use `uv run` (never bare `python`). If issues persist: `uv sync --reinstall`.

## Always Use `uv run`

```bash
uv run pytest -v          # not: pytest -v
uv run ruff check .       # not: ruff check .
uv run mypy bridge/       # not: mypy bridge/
uv run python -m bridge.server  # not: python -m bridge.server
```

## Dependencies

### Core (pyproject.toml `[project.dependencies]`)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastmcp[tasks]` | >=3.0.0 | MCP server framework + background tasks |
| `httpx` | >=0.27.0 | Async HTTP client for Codegen API |
| `pydantic` | >=2.0.0 | Data validation and serialization |
| `py-key-value-aio` | >=0.4.0 | Storage backend (FileTreeStore, MemoryStore) |

### Optional: Telemetry (`[project.optional-dependencies]`)

| Package | Purpose |
|---------|---------|
| `opentelemetry-sdk` | Tracing SDK |
| `opentelemetry-exporter-otlp` | OTLP exporter |

### Dev (`[dependency-groups] dev`)

| Package | Purpose |
|---------|---------|
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `respx` | HTTP mocking for httpx |
| `ruff` | Linter + formatter |
| `mypy` | Static type checker |
| `opentelemetry-sdk` | For telemetry tests |

## mypy Configuration

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
warn_unreachable = true
show_error_codes = true
enable_error_code = ["ignore-without-code", "redundant-cast", "truthy-bool"]
```

Ignored imports (no stubs available):
- `key_value.*`, `opentelemetry.*`, `mcp.*`, `fastmcp.*`, `respx.*`

## Storage Directory

`FileStorage` uses `.codegen-bridge/storage/` in the project root (via py-key-value-aio `FileTreeStore`). This directory is ephemeral — stores execution contexts that survive server restarts but are not committed.

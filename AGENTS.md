# AGENTS.md — Codegen Agent Rules

This file is read by Codegen cloud agents before any action. Follow every rule here exactly.

## Repository

**codegen-bridge** v0.4.0 — Claude Code plugin (MCP server) that bridges to the [Codegen](https://codegen.com) AI agent platform.

- Language: Python 3.12+
- Framework: FastMCP 3.0 (MCP server)
- Test runner: pytest + pytest-asyncio
- Linter: ruff (line-length 99)
- Type checker: mypy (strict mode)

## Setup (MANDATORY first step in sandbox)

```bash
uv sync --dev
```

Never use `pip install`. Never use `pip`. Always `uv sync --dev`.

## Commands

```bash
# Install dependencies (ALWAYS first)
uv sync --dev

# Run all tests
uv run pytest -v

# Run a single test file
uv run pytest tests/test_server.py -v

# Lint (check only)
uv run ruff check .

# Lint + auto-fix
uv run ruff check . --fix

# Format check
uv run ruff format --check .

# Auto-format
uv run ruff format .

# Type checking (strict mode)
uv run mypy bridge/

# Run all checks (CI equivalent)
uv run ruff check . && uv run ruff format --check . && uv run mypy bridge/ && uv run pytest -v
```

## CRITICAL: Always Use `uv run`

**NEVER** use bare commands:
- BAD: `python`, `pytest`, `ruff`, `mypy`
- GOOD: `uv run python`, `uv run pytest`, `uv run ruff`, `uv run mypy`

**Why**: The sandbox has Python 3.13 system-wide, but the project requires 3.12. `uv run` creates and uses an isolated 3.12 venv. Bare `python` will fail with pydantic_core import errors.

If you see `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`, run:
```bash
uv sync --dev --reinstall
```

## Environment Variables

Required at runtime (NOT needed for tests — tests mock these):

| Variable | Required | Description |
|----------|----------|-------------|
| `CODEGEN_API_KEY` | Yes | Bearer token from codegen.com |
| `CODEGEN_ORG_ID` | Yes | Organization ID (integer) |
| `CODEGEN_ALLOW_DANGEROUS_TOOLS` | No | `"true"` to bypass dangerous tool guard |

**In tests**: Set env vars at module level BEFORE any bridge imports:
```python
import os
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "12345"
# Only THEN import bridge modules
from bridge.server import mcp
```

**NEVER use `os.environ.setdefault()`** — always use direct assignment `os.environ["KEY"] = "value"`.

## Architecture

```text
bridge/
├── server.py          — FastMCP server, lifespan, component registration
├── client.py          — Async httpx client for Codegen REST API v1
├── models.py          — Pydantic models (NOT types.py — avoids stdlib shadow)
├── dependencies.py    — DI: get_client, get_org_id, get_registry, get_repo_cache, get_sampling_config
├── context.py         — ExecutionContext, TaskContext, TaskReport, ContextRegistry
├── elicitation.py     — confirm_action, confirm_with_schema, select_choice
├── storage.py         — MemoryStorage / FileStorage (Strategy pattern)
├── openapi_utils.py   — Loads openapi_spec.json, patches {org_id}, builds OpenAPIProvider
├── prompt_builder.py  — Static prompt assembly for agent tasks
├── log_parser.py      — Structured parsing of agent execution logs
├── settings.py        — Application configuration
├── tools/             — 6 modules: agent(9), execution(3), pr(2), setup(12), integrations(7), settings(2)
├── sampling/          — Server-side LLM sampling: 4 tools via ctx.sample()
├── middleware/        — 9-layer middleware stack
├── transforms/        — 4 transforms: Namespace, ToolTransform, Visibility, VersionFilter
├── providers/         — OpenAPIProvider, SkillsDirectoryProvider, CommandsProvider, AgentsProvider
├── resources/         — Config state + platform docs resources
├── prompts/           — 4 prompt templates for workflows
├── helpers/           — formatting, pagination, repo_detection
└── telemetry/         — OpenTelemetry config, helpers, middleware
```

## Code Style

- Python 3.12+, type hints everywhere (mypy strict)
- Ruff: line-length 99, rules `E, F, W, I, N, UP, B, SIM, RUF`
- B008 suppressed in `bridge/tools/*.py`, `bridge/dependencies.py`, `bridge/resources/*.py`, `bridge/sampling/tools.py` (FastMCP DI pattern uses `Depends()` as default arg)
- Module named `models.py` NOT `types.py` — avoids shadowing Python stdlib `types`
- Entry point: `python -m bridge.server` (not `python bridge/server.py`) — sys.path isolation

## Testing Patterns

- **respx** for HTTP mocking (not httpx's built-in mock)
- In-memory MCP client: `async with Client(mcp) as c:` — runs with full lifespan
- `asyncio_mode = "auto"` in pyproject.toml — no `@pytest.mark.asyncio` decorator needed
- Test structure mirrors `bridge/` (e.g., `tests/tools/`, `tests/middleware/`)

```python
# Standard test pattern
import pytest
from fastmcp import Client
from bridge.server import mcp

async def test_something():
    async with Client(mcp) as client:
        result = await client.call_tool("codegen_list_runs", {"limit": 5})
        assert not result.is_error
```

## Git Workflow

- Branch naming: `feat/<description>`, `fix/<description>`, `chore/<description>`
- Commit messages: conventional commits format (`feat:`, `fix:`, `chore:`, `test:`, `docs:`)
- Create PR to `master` branch
- All tests must pass before PR creation
- Run full check: `uv run ruff check . && uv run mypy bridge/ && uv run pytest -v`

## Scope Rules (CRITICAL for agents)

When given a task:
1. Only modify files relevant to the task scope
2. Do NOT modify `CHANGELOG.md`, `AGENTS.md`, or `CLAUDE.md` unless explicitly asked
3. Do NOT modify unrelated test files
4. Do NOT add telemetry or OpenTelemetry unless explicitly asked
5. Always run tests after changes to verify nothing is broken
6. If tests were passing before your changes, they must pass after

## PR Creation Checklist

Before creating a PR:
- [ ] `uv run ruff check .` — zero errors
- [ ] `uv run ruff format --check .` — no formatting issues
- [ ] `uv run mypy bridge/` — zero type errors
- [ ] `uv run pytest -v` — all tests pass
- [ ] PR title follows: `feat:`, `fix:`, `chore:`, `test:`, `docs:` format
- [ ] PR targets `master` branch (NOT `main`)

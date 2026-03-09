# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is this

Claude Code plugin (v0.5.0) that bridges to the [Codegen](https://codegen.com) cloud AI agent platform. Hybrid MCP server: **41 manual tools** (6 tool modules + 4 sampling) + **5 auto-generated** from OpenAPI spec, 2 services, 9-layer middleware stack, transform chain, 4 providers, 8 resources (3 config + 2 platform + 3 templates), prompts, and sampling via `ctx.sample()`.

## Commands

```bash
# Install dependencies
uv sync --dev

# Run all tests (60 test files)
uv run pytest -v

# Run a single test file / single test
uv run pytest tests/test_server.py -v
uv run pytest tests/test_server.py::test_lifespan_yields_client -v

# Lint + auto-fix
uv run ruff check .
uv run ruff check . --fix

# Type checking (strict mode)
uv run mypy bridge/

# Run MCP server directly (for debugging)
uv run python -m bridge.server
```

## Architecture Quick Reference

| Module | Purpose |
|--------|---------|
| `bridge/server.py` | FastMCP server, lifespan, component registration |
| `bridge/client.py` | Async httpx client for Codegen REST API v1 |
| `bridge/models.py` | Pydantic models (**not** `types.py` — avoids stdlib shadow) |
| `bridge/annotations.py` | 6 `ToolAnnotations` presets: `READ_ONLY`, `READ_ONLY_LOCAL`, `CREATES`, `MUTATES`, `MUTATES_LOCAL`, `DESTRUCTIVE` |
| `bridge/dependencies.py` | DI providers: `get_client`, `get_org_id`, `get_registry`, `get_repo_cache`, `get_sampling_config`, `get_run_service`, `get_execution_service` |
| `bridge/context.py` | `ExecutionContext`, `TaskContext`, `TaskReport`, `ContextRegistry` |
| `bridge/elicitation.py` | `confirm_action`, `confirm_with_schema`, `select_choice` |
| `bridge/storage.py` | `MemoryStorage` / `FileStorage` (Strategy pattern) |
| `bridge/openapi_utils.py` | Loads `openapi_spec.json`, patches `{org_id}`, builds `OpenAPIProvider` |
| `bridge/prompt_builder.py` | Static prompt assembly for agent tasks |
| `bridge/log_parser.py` | Structured parsing of agent execution logs |
| `bridge/settings.py` | Application configuration |
| `bridge/icons.py` | Tool icon constants |
| `bridge/services/` | Business logic: `RunService` (runs.py), `ExecutionService` (execution.py) |
| `bridge/tools/` | 6 tool modules: agent(11), execution(3), pr(2), setup(12), integrations(7), settings(2) |
| `bridge/sampling/` | Server-side LLM sampling: 4 tools via `ctx.sample()` |
| `bridge/middleware/` | 9-layer middleware stack (error → ping → auth → logging → telemetry → timing → rate limit → cache → response limit) |
| `bridge/transforms/` | 4 transforms: Namespace → ToolTransform → Visibility → VersionFilter |
| `bridge/providers/` | `OpenAPIProvider`, `SkillsDirectoryProvider`, `CommandsProvider`, `AgentsProvider` |
| `bridge/resources/` | 8 resources: config (3) + platform docs (2) + parameterized templates (3) |
| `bridge/prompts/` | 4 prompt templates for workflows |
| `bridge/helpers/` | `formatting`, `pagination`, `repo_detection` |
| `bridge/telemetry/` | OpenTelemetry config, helpers, middleware |

@.claude/rules/architecture.md
@.claude/rules/tools.md
@.claude/rules/testing.md
@.claude/rules/environment.md
@.claude/rules/plugin.md
@.claude/rules/patterns.md

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CODEGEN_API_KEY` | Yes | Bearer token from codegen.com |
| `CODEGEN_ORG_ID` | Yes | Organization ID (integer) |
| `CODEGEN_ALLOW_DANGEROUS_TOOLS` | No | Set `"true"` to bypass dangerous tool guard middleware |

## Style

- Python 3.12+, `.python-version` file pinned to `3.12`
- Ruff: line-length 99, rules `E, F, W, I, N, UP, B, SIM, RUF`
- B008 suppressed in `bridge/tools/*.py`, `bridge/dependencies.py`, `bridge/resources/*.py`, `bridge/sampling/tools.py` (FastMCP DI pattern)
- mypy: strict mode, `warn_unreachable`, `show_error_codes`
- Entry point: `python -m bridge.server` (not `python bridge/server.py`) to avoid sys.path issues
- Module named `models.py` not `types.py` — avoids shadowing Python's stdlib `types`

## Critical Constraints

- **Always use `uv run`** — never bare `python` or `pytest` (virtual env isolation)
- **Env vars before import** in tests: `os.environ["KEY"] = "value"` at module level, then `monkeypatch.setenv()` in autouse fixture
- **Never use `setdefault`** for env vars — user has real values that must be overridden in tests

## Key Patterns

**Lifespan + DI:** Server lifespan creates `CodegenClient`, `ContextRegistry`, `RepoCache`, `SamplingConfig` → yields dict → tools access via `Depends(get_client)` etc.

**Service Layer:** `RunService` and `ExecutionService` in `bridge/services/` own business logic. Tools are thin wrappers calling services via `Depends(get_run_service)`. Resources delegate to the same services for data consistency.

**Annotations:** 6 `ToolAnnotations` presets in `bridge/annotations.py` (`READ_ONLY`, `CREATES`, `MUTATES`, `DESTRUCTIVE`, etc.). Every manual tool has an explicit annotation.

**OpenAPI Provider:** Auto-generated tools (5) added via `server.add_provider(provider)` in lifespan. Optional — if it fails, manual tools still work. `TOOL_NAMES` dict maps operationIds to clean `codegen_*` names.

**Repo auto-detection:** `RepoCache` in `bridge/helpers/repo_detection.py` runs `git remote get-url origin`, parses GitHub URL, matches against `client.list_repos()`.

**Middleware + Transforms:** Configured at module level via `configure_middleware(mcp)` and `configure_transforms(mcp)`. Both follow Chain of Responsibility — first-added is outermost.

## Testing Patterns

- **respx** for HTTP mocking (not httpx's built-in mock)
- In-memory MCP client: `async with Client(mcp) as c:` — runs with full lifespan
- `asyncio_mode = "auto"` in pyproject.toml — no `@pytest.mark.asyncio` needed
- Test structure mirrors `bridge/` (e.g., `tests/tools/`, `tests/middleware/`)

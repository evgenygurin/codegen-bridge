# Architecture

Codegen Bridge is a hybrid MCP server built on [FastMCP](https://github.com/jlowin/fastmcp) with a layered architecture: middleware → tools/resources → services → API client.

## High-Level Data Flow

```
Claude Code ──MCP──▶ FastMCP Server (bridge/server.py)
                         │
                    ┌────┴────┐
                    ▼         ▼
              Middleware   Transforms
              (9 layers)  (4 stages)
                    │         │
                    └────┬────┘
                         ▼
                   Tool Functions        Resources
                   (bridge/tools/)    (bridge/resources/)
                         │                  │
                         └────────┬─────────┘
                                  ▼
                            Service Layer
                         (bridge/services/)
                                  │
                    ┌─────────────┼──────────────┐
                    ▼             ▼              ▼
              CodegenClient    Storage       Sampling
              (httpx→API)    (FileTree)    (ctx.sample)
```

## Module Map

| Layer | Module(s) | Purpose |
|-------|-----------|---------|
| **Entry** | `server.py` | FastMCP instance, lifespan, component registration |
| **Client** | `client.py` | Async httpx REST client (unified `_request_json`) |
| **Models** | `models.py` | Pydantic API response types (named `models` not `types` — avoids stdlib shadow) |
| **Annotations** | `annotations.py` | 6 `ToolAnnotations` presets |
| **Rate Budget** | `rate_budget.py` | Outbound token-bucket rate limiter for API calls |
| **DI** | `dependencies.py` | 8 DI providers for lifespan resources and services |
| **Context** | `context.py` | `ExecutionContext`, `TaskContext`, `TaskReport`, `ContextRegistry` |
| **Elicitation** | `elicitation.py` | Interactive user prompts with Pydantic schema support |
| **Storage** | `storage.py` | `MemoryStorage` / `FileStorage` (Strategy pattern, TTL) |
| **Services** | `services/` | `RunService` (runs.py), `ExecutionService` (execution.py) |
| **Tools** | `tools/` | 8 modules with 49 manual tools |
| **Sampling** | `sampling/` | 4 tools via `ctx.sample()`, `SamplingService` |
| **Resources** | `resources/` | Config, platform, templates (33 total with providers) |
| **Prompts** | `prompts/` | 8 prompt templates for workflows |
| **Providers** | `providers/` | OpenAPI, Skills, Commands, Agents, Remote proxy |
| **Middleware** | `middleware/` | 9-layer request pipeline |
| **Transforms** | `transforms/` | 4-stage component transformation |
| **Helpers** | `helpers/` | Formatting, pagination, repo detection |
| **Telemetry** | `telemetry/` | OpenTelemetry integration |
| **OpenAPI** | `openapi_utils.py` | Auto-generates tools from `openapi_spec.json` |

## Source Tree

```
bridge/
├── server.py         — FastMCP instance, lifespan, registration order
├── client.py         — Async httpx REST client → Codegen API v1
├── models.py         — Pydantic response types (NOT types.py)
├── annotations.py    — 6 ToolAnnotations presets
├── rate_budget.py    — OutboundRateBudget (token-bucket)
├── dependencies.py   — DI providers
├── context.py        — ExecutionContext, TaskContext, ContextRegistry
├── elicitation.py    — confirm_action, confirm_with_schema, select_choice
├── storage.py        — MemoryStorage / FileStorage
├── openapi_utils.py  — OpenAPI spec loader + provider builder
├── prompt_builder.py — Static prompt assembly
├── log_parser.py     — Structured log parsing
├── settings.py       — App configuration
├── icons.py          — Tool icon constants
├── services/
│   ├── runs.py       — RunService (business logic)
│   └── execution.py  — ExecutionService (business logic)
├── tools/
│   ├── agent/        — 13 tools (lifecycle, queries, moderation, logs, workflow, background, bulk)
│   ├── execution.py  — 3 tools
│   ├── pr.py         — 2 tools
│   ├── setup/        — 13 tools (users, organizations, oauth, check_suite, models)
│   ├── integrations.py — 8 tools
│   ├── analytics.py  — 1 tool
│   ├── settings.py   — 2 tools
│   └── session.py    — 3 tools
├── sampling/         — 4 tools via ctx.sample()
├── middleware/        — 9-layer stack
├── transforms/       — 4-stage chain
├── providers/        — OpenAPI, Skills, Commands, Agents, Remote
├── resources/        — Config, platform, templates
├── prompts/          — Workflow prompt templates
├── helpers/          — Formatting, pagination, repo detection
└── telemetry/        — OpenTelemetry OTLP
```

## Lifespan and Dependency Injection

The server uses FastMCP's lifespan pattern to create shared resources:

```python
@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    client = CodegenClient(api_key=api_key, org_id=org_id)
    registry = ContextRegistry(storage=FileStorage())
    ...
    yield {
        "client": client,
        "org_id": org_id,
        "registry": registry,
        "repo_cache": repo_cache,
        "sampling_config": sampling_config,
        "session_state": session_state,
    }
```

Tools access these via `Depends()`:

```python
@mcp.tool()
async def codegen_get_run(
    run_id: int,
    ctx: Context = CurrentContext(),
    client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
) -> str:
    ...
```

### Lifespan Context Keys

| Key | Type | DI Provider |
|-----|------|-------------|
| `"client"` | `CodegenClient` | `get_client()` |
| `"org_id"` | `int` | `get_org_id()` |
| `"registry"` | `ContextRegistry` | `get_registry()` |
| `"repo_cache"` | `RepoCache` | `get_repo_cache()` |
| `"sampling_config"` | `SamplingConfig` | `get_sampling_config()` |
| `"session_state"` | `dict[str, str]` | `get_session_state()` |

## Registration Order

Components are registered in a specific order in `server.py`:

```python
configure_middleware(mcp)          # 1. Middleware stack
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
register_sampling_tools(mcp)       # 5. Sampling tools
configure_transforms(mcp)          # 6. Transform chain
# In lifespan:
server.add_provider(openapi)       # 7. Providers (OpenAPI + filesystem)
server.mount(remote, namespace="remote")  # 8. Remote proxy (optional)
```

## Service Layer

Business logic lives in `bridge/services/`, not in tools:

| Service | Module | Methods | Consumers |
|---------|--------|---------|-----------|
| `RunService` | `services/runs.py` | `get_run`, `list_runs`, `report_run_result`, `create_run`, `detect_repo` | Agent tools, workflow tools, resource templates |
| `ExecutionService` | `services/execution.py` | `get_execution_context` | Execution tools, resource templates |

Tools are thin wrappers that call services via DI:

```python
@mcp.tool()
async def codegen_get_run(run_id: int, ...,
    service: RunService = Depends(get_run_service),  # type: ignore[arg-type]
) -> str:
    result = await service.get_run(run_id)
    return json.dumps(result)
```

## Storage

Two storage backends follow the Strategy pattern:

- **`MemoryStorage`** — in-memory, for tests and ephemeral sessions
- **`FileStorage`** — filesystem-based (`py-key-value-aio` `FileTreeStore`), stores to `.codegen-bridge/storage/`

Both support TTL for automatic expiration. The `ContextRegistry` is injected with a storage backend at construction.

## Repo Auto-Detection

`RepoCache` in `bridge/helpers/repo_detection.py`:
1. Runs `git remote get-url origin`
2. Parses the GitHub URL to extract owner/repo
3. Matches against `client.list_repos()` for the `repo_id`
4. Caches the result for the session

## See Also

- **[[Middleware-and-Transforms]]** — Deep dive into the 9-layer middleware and 4-stage transforms
- **[[Providers]]** — How OpenAPI, Skills, Commands, and Agents providers work
- **[[Tools-Reference]]** — Complete tool documentation
- **[[Development-Guide]]** — How to extend the architecture

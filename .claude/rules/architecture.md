---
paths:
  - bridge/**
---

# Architecture

## Data Flow

```text
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

| Layer | Modules | Purpose |
|-------|---------|---------|
| Entry | `server.py` | FastMCP instance, lifespan, registration |
| Client | `client.py` | Async httpx REST client (unified `_request_json`) |
| Models | `models.py` | API response types (named `models` not `types` — stdlib shadow) |
| Annotations | `annotations.py` | 6 `ToolAnnotations` presets (READ_ONLY, CREATES, MUTATES, etc.) |
| Rate Budget | `rate_budget.py` | Outbound token-bucket rate limiter for API calls |
| DI | `dependencies.py` | 8 DI providers for lifespan resources, services, session state |
| Context | `context.py` | Execution/task tracking with `ContextRegistry` |
| Storage | `storage.py` | `MemoryStorage`/`FileStorage` (Strategy pattern, TTL support) |
| Elicitation | `elicitation.py` | Interactive user prompts with Pydantic schema support |
| Services | `services/` | `RunService` (runs.py), `ExecutionService` (execution.py) |
| Tools | `tools/` | 8 modules, 45 manual tools + 4 sampling = 49 total |
| Sampling | `sampling/` | 4 tools via `ctx.sample()`, `SamplingService` |
| Resources | `resources/` | 8 resources: config (3) + platform (2) + templates (3) |
| Prompts | `prompts/` | 4 workflow templates |
| Providers | `providers/` | OpenAPI, Skills, Commands, Agents, remote proxy |
| Middleware | `middleware/` | 9-layer request pipeline |
| Transforms | `transforms/` | 4-stage component transformation |
| Helpers | `helpers/` | Formatting, pagination, repo detection |
| Telemetry | `telemetry/` | OpenTelemetry integration |
| OpenAPI | `openapi_utils.py` + `openapi_spec.json` | Auto-generate 5 tools from spec |

## Middleware Stack (outermost → innermost)

Defined in `bridge/middleware/stack.py`. All configurable via `MiddlewareConfig`.

| # | Middleware | Source | Purpose |
|---|-----------|--------|---------|
| 1 | `ErrorHandlingMiddleware` | FastMCP | Catch exceptions, transform errors |
| 2 | `PingMiddleware` | FastMCP | Keep connections alive |
| 3 | `DangerousToolGuardMiddleware` | `bridge/middleware/authorization.py` | Block dangerous tools unless `CODEGEN_ALLOW_DANGEROUS_TOOLS=true` |
| 4 | `LoggingMiddleware` | FastMCP | Structured request/response logging |
| 5 | `TelemetryMiddleware` | `bridge/telemetry/middleware.py` | OpenTelemetry tracing and metrics |
| 6 | `TimingMiddleware` | FastMCP | Execution duration per operation |
| 7 | `RateLimitingMiddleware` | FastMCP | Token-bucket throttling |
| 8 | `ResponseCachingMiddleware` | FastMCP | TTL-based response caching |
| 9 | `ResponseLimitingMiddleware` | FastMCP | Truncate oversized tool output |

## Transform Chain (innermost → outermost)

Defined in `bridge/transforms/registry.py`. Fully configured in v0.6.0.

| # | Transform | Purpose |
|---|-----------|---------|
| 1 | `Namespace` | Prefix component names |
| 2 | `ToolTransform` | Rename, re-describe, hide tools |
| 3 | `Visibility` | Show/hide by name, tag, type |
| 4 | `VersionFilter` | Gate by semantic version range |

## Providers

Registered during lifespan in `server.py`.

| Provider | Source | What it provides |
|----------|--------|-----------------|
| `OpenAPIProvider` | `openapi_utils.py` | 5 auto-generated tools from REST API spec |
| `SkillsDirectoryProvider` | `providers/agents.py` | Skill resources from `skills/` directory |
| `CommandsProvider` | `providers/commands.py` | Command resources from `commands/` directory |
| `AgentsProvider` | `providers/agents.py` | Agent resources from `agents/` directory |
| Remote Proxy | `providers/remote.py` | Mounted Codegen MCP server (`namespace="remote"`) |

## Lifespan Context Keys

The lifespan yields a dict accessible via `ctx.lifespan_context`:

| Key | Type | DI Provider |
|-----|------|-------------|
| `"client"` | `CodegenClient` | `get_client()` |
| `"org_id"` | `int` | `get_org_id()` |
| `"registry"` | `ContextRegistry` | `get_registry()` |
| `"repo_cache"` | `RepoCache` | `get_repo_cache()` |
| `"sampling_config"` | `SamplingConfig` | `get_sampling_config()` |
| `"session_state"` | `dict[str, str]` | `get_session_state()` |

## Registration Order (in `server.py`)

```python
configure_middleware(mcp)         # 1. Middleware stack
register_agent_tools(mcp)         # 2. Tool groups
register_execution_tools(mcp)
register_pr_tools(mcp)
register_setup_tools(mcp)
register_integration_tools(mcp)
register_analytics_tools(mcp)
register_settings_tools(mcp)
register_session_tools(mcp)
register_resources(mcp)           # 3. Resources
register_prompts(mcp)             # 4. Prompts
register_sampling_tools(mcp)      # 5. Sampling tools
configure_transforms(mcp)         # 6. Transform chain
# Providers added in lifespan:    # 7. OpenAPI + Skills + Commands + Agents + Remote proxy
```

## Adding New Modules

1. Create module in appropriate `bridge/` subdirectory
2. Follow existing patterns (DI via `Depends`, `CurrentContext`)
3. Add `register_*` function that takes `FastMCP` instance
4. Call it from `server.py` in the correct position
5. Add corresponding test file mirroring the path in `tests/`
6. Update `bridge/__init__.py` exports if needed

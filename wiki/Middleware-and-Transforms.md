# Middleware and Transforms

Codegen Bridge uses a **9-layer middleware stack** for request processing and a **4-stage transform chain** for component transformation.

## Middleware Stack

Middleware layers are configured in `bridge/middleware/stack.py` via `configure_middleware(mcp)`. They process requests from outermost (first) to innermost (last).

### Layer Order

| # | Middleware | Source | Purpose |
|---|-----------|--------|---------|
| 1 | `ErrorHandlingMiddleware` | FastMCP | Catch exceptions, transform into structured error responses |
| 2 | `PingMiddleware` | FastMCP | Keep MCP connections alive during long operations |
| 3 | `DangerousToolGuardMiddleware` | `bridge/middleware/authorization.py` | Block dangerous tools unless explicitly allowed |
| 4 | `LoggingMiddleware` | FastMCP | Structured request/response logging |
| 5 | `TelemetryMiddleware` | `bridge/telemetry/middleware.py` | OpenTelemetry tracing and metrics |
| 6 | `TimingMiddleware` | FastMCP | Execution duration per operation |
| 7 | `RateLimitingMiddleware` | FastMCP | Token-bucket throttling for inbound requests |
| 8 | `ResponseCachingMiddleware` | FastMCP | TTL-based response caching (tool calls disabled by default) |
| 9 | `ResponseLimitingMiddleware` | FastMCP | Truncate oversized tool output |

### Configuration

Middleware is configured via `MiddlewareConfig` dataclass:

```python
from bridge.middleware import configure_middleware, MiddlewareConfig, CachingConfig

# Default configuration
configure_middleware(mcp)

# Custom configuration
configure_middleware(mcp, MiddlewareConfig(
    caching=CachingConfig(enabled=False),
))
```

### Dangerous Tool Guard (Layer 3)

The `DangerousToolGuardMiddleware` protects against accidental destructive operations.

**Guard Strategy:** A tool is blocked when **either**:
1. Tool name is in `DEFAULT_DANGEROUS_TOOLS`, OR
2. Tool has the `"dangerous"` tag

**Unless:**
- `CODEGEN_ALLOW_DANGEROUS_TOOLS=true` environment variable is set, OR
- The tool receives `confirmed=True` parameter

**Default dangerous tools:**

```python
DEFAULT_DANGEROUS_TOOLS = frozenset({
    "codegen_stop_run",
    "codegen_edit_pr",
    "codegen_edit_pr_simple",
    "codegen_delete_webhook_config",
    "codegen_set_webhook_config",
    "codegen_revoke_oauth_token",
})
```

### Response Caching (Layer 8)

**Default: Tool call caching is DISABLED** (`tool_call_enabled=False`). This prevents stale data for polling tools like `codegen_get_run`.

### Rate Limiting (Layer 7)

Token-bucket rate limiting for inbound requests. This is separate from the `OutboundRateBudget` that throttles outgoing API calls to Codegen.

### Outbound Rate Budget

`OutboundRateBudget` in `bridge/rate_budget.py` is a token-bucket rate limiter for outgoing API calls. It prevents 429 errors from the Codegen API:

- Used by `CodegenClient` for all API calls
- `codegen_create_and_monitor` respects it during polling
- Orthogonal to the inbound `RateLimitingMiddleware`

---

## Transform Chain

Transforms are configured in `bridge/transforms/registry.py` via `configure_transforms(mcp)`. They modify how MCP components (tools, resources, prompts) are presented to clients.

### Transform Order

Transforms apply from innermost to outermost:

| # | Transform | Purpose |
|---|-----------|---------|
| 1 | `Namespace` | Prefix component names (e.g., `codegen_` prefix) |
| 2 | `ToolTransform` | Rename, re-describe, or hide specific tools |
| 3 | `Visibility` | Show/hide components by name, tag, or type |
| 4 | `VersionFilter` | Gate components by semantic version range |

### Configuration

```python
from bridge.transforms import configure_transforms, TransformsConfig, NamespaceConfig

# Default: passthrough (no transforms applied)
configure_transforms(mcp)

# Custom configuration
configure_transforms(mcp, TransformsConfig(
    namespace=NamespaceConfig(prefix="cg"),
))
```

### Default Configuration

In the current version, transforms are configured as **passthrough** — no transformations are applied. The infrastructure is in place for future customization.

---

## Design Patterns

### Chain of Responsibility

Both middleware and transforms follow the Chain of Responsibility pattern:
- First-added is outermost (middleware) or innermost (transforms)
- Each layer can modify, pass through, or short-circuit the request

### Configuration Pattern

Both use the same structure:
1. Config dataclass (`MiddlewareConfig` / `TransformsConfig`)
2. Private `_build_*` function
3. Public `configure_*` API

### Module-Level Configuration

Both are configured at module level in `server.py`:

```python
configure_middleware(mcp)    # Before tool registration
# ... register tools, resources, prompts ...
configure_transforms(mcp)   # After all registrations
```

---

## See Also

- **[[Architecture]]** — Overall system architecture
- **[[Tools-Reference]]** — Tools protected by middleware
- **[[Configuration]]** — Environment variables that affect middleware behavior

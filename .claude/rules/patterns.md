---
paths:
  - bridge/server.py
  - bridge/dependencies.py
  - bridge/context.py
  - bridge/elicitation.py
  - bridge/providers/**
  - bridge/middleware/**
---

# Patterns

## FastMCP Dependency Injection

Tools receive dependencies via `Depends()` and `CurrentContext()` in default args:

```python
from bridge.dependencies import CurrentContext, Depends, get_client, get_registry

@mcp.tool()
async def my_tool(
    run_id: int,
    ctx: Context = CurrentContext(),
    client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    registry: ContextRegistry = Depends(get_registry),  # type: ignore[arg-type]
) -> str:
    ...
```

- `# type: ignore[arg-type]` is required — mypy can't infer `Depends()` return types
- B008 suppressed in ruff for these files (function call in default arg)
- DI providers defined in `bridge/dependencies.py`, all resolve from `ctx.lifespan_context`

## Lifespan Pattern

Server lifespan creates resources and yields them as a dict:

```python
@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    client = CodegenClient(api_key=api_key, org_id=org_id)
    ...
    try:
        yield {"client": client, "org_id": org_id, "registry": registry, ...}
    finally:
        await client.close()
```

Tools never create their own clients — everything comes through DI from lifespan.

## Provider Pattern

Custom providers extend filesystem discovery:

```python
from fastmcp.server.providers.base import BaseProvider

class CommandsProvider(BaseProvider):
    async def _list_resources(self) -> list[Resource]:
        # Discover .md files in commands/ directory
        ...
```

Registered in lifespan via `server.add_provider(provider)`. If a provider fails, it's logged and skipped — other providers and manual tools still work.

## Elicitation Pattern

Interactive user confirmations with graceful degradation:

```python
from bridge.elicitation import confirm_action, select_choice

# Boolean confirmation
if not await confirm_action(ctx, "Stop agent run 42?"):
    return json.dumps({"cancelled": True})

# Choice selection
choice = await select_choice(ctx, "Which repo?", ["repo-a", "repo-b"])
```

Falls through silently when client doesn't support elicitation (returns configurable default). Three helpers:
- `confirm_action(ctx, message, default=True)` → `bool`
- `confirm_with_schema(ctx, message, schema)` → `T | None`
- `select_choice(ctx, message, choices, default=None)` → `str | None`

## Registration Pattern

Each subsystem has a `register_*` or `configure_*` function that takes `FastMCP`:

```python
# In bridge/tools/agent.py
def register_agent_tools(mcp: FastMCP) -> None:
    @mcp.tool(tags={"agent"})
    async def codegen_create_run(...) -> str:
        ...

# In bridge/server.py
register_agent_tools(mcp)
```

Order in `server.py`: middleware → tools → resources → prompts → sampling → transforms. Providers added separately in lifespan.

## Dangerous Tool Pattern

Three-layer protection for destructive operations:

1. **Tag:** `@mcp.tool(tags={"dangerous"})` marks the tool
2. **Parameter:** `confirmed: bool = False` allows explicit bypass
3. **Elicitation:** `confirm_action()` asks user interactively
4. **Middleware:** `DangerousToolGuardMiddleware` blocks unless `CODEGEN_ALLOW_DANGEROUS_TOOLS=true`

## Storage Strategy Pattern

`StorageBackend` protocol with two implementations:

- **`MemoryStorage`** — in-memory, for tests and ephemeral sessions
- **`FileStorage`** — filesystem-based (py-key-value-aio `FileTreeStore`), survives restarts

Injected into `ContextRegistry` at construction — callers never depend on concrete backend:

```python
storage = FileStorage()       # production
storage = MemoryStorage()     # tests
registry = ContextRegistry(storage=storage)
```

## Middleware/Transform Configuration Pattern

Both follow the same structure: config dataclass → `_build_*` function → `configure_*` public API:

```python
# Middleware
configure_middleware(mcp)                     # uses default MiddlewareConfig
configure_middleware(mcp, MiddlewareConfig(    # custom config
    caching=CachingConfig(enabled=False),
))

# Transforms
configure_transforms(mcp)                    # passthrough (no transforms)
configure_transforms(mcp, TransformsConfig(  # custom
    namespace=NamespaceConfig(prefix="cg"),
))
```

# Providers

Codegen Bridge uses **4+ MCP providers** to extend its surface beyond manually registered tools and resources. Providers are registered during the server lifespan in `server.py`.

## Provider Overview

| Provider | Source | What it Provides | Registration |
|----------|--------|-----------------|-------------|
| `OpenAPIProvider` | `openapi_utils.py` | 5 auto-generated tools from REST API spec | Lifespan |
| `SkillsDirectoryProvider` | `providers/agents.py` | Skill resources from `skills/` directory | Lifespan |
| `CommandsProvider` | `providers/commands.py` | Command resources from `commands/` directory | Lifespan |
| `AgentsProvider` | `providers/agents.py` | Agent resources from `agents/` directory | Lifespan |
| Remote Proxy | `providers/remote.py` | Mounted Codegen MCP server | Lifespan (optional) |

## Graceful Degradation

All providers are **optional**. If a provider fails to register (import error, missing files, network issues), it's logged and skipped. Manual tools still work.

```python
# From server.py lifespan
for fs_provider in create_all_providers():
    try:
        server.add_provider(fs_provider)
    except (ImportError, ValueError, OSError):
        logger.warning("Failed to register provider", exc_info=True)
```

---

## OpenAPI Provider

**Module:** `bridge/openapi_utils.py`

Auto-generates MCP tools from the Codegen REST API OpenAPI specification.

### How It Works

1. `load_and_patch_spec(org_id)` — Loads `bridge/openapi_spec.json`, replaces `{org_id}` with real value
2. `build_route_maps()` — Whitelists specific endpoints, excludes the rest
3. `TOOL_NAMES` — Maps raw operationIds to human-readable `codegen_*` names
4. `create_openapi_provider(http_client, org_id)` — Returns the provider instance

### Generated Tools

| Raw operationId | Tool Name | Unique? |
|-----------------|-----------|---------|
| `get_current_user_info_v1_users_me_get` | `codegen_get_current_user` | No (manual exists) |
| `get_available_models_v1_organizations__org_id__models_get` | `codegen_get_models` | **Yes** |
| `revoke_oauth_token_v1_oauth_tokens_revoke_post` | `codegen_revoke_oauth_token` | **Yes** (manual has elicitation) |
| `get_oauth_token_status_v1_oauth_tokens_status_get` | `codegen_get_oauth_status` | No (manual exists) |
| `get_mcp_providers_v1_mcp_providers_get` | `codegen_get_mcp_providers` | No (manual exists) |

**5 total, 2 unique** — 3 overlap with manual tools. Prefer manual tools for interactive use (they have annotations, elicitation, and progress reporting).

---

## Skills Directory Provider

**Module:** `bridge/providers/agents.py`

Discovers and serves skill resources from the `skills/` directory. Each skill is a subdirectory containing a `SKILL.md` file.

### Discovery

```
skills/
├── using-codegen-bridge/SKILL.md    → Resource
├── codegen-delegation/SKILL.md      → Resource
├── executing-via-codegen/SKILL.md   → Resource
├── agent-monitoring/SKILL.md        → Resource
├── pr-management/SKILL.md           → Resource
├── bulk-delegation/SKILL.md         → Resource
├── run-analytics/SKILL.md           → Resource
├── debugging-failed-runs/SKILL.md   → Resource
├── prompt-crafting/SKILL.md         → Resource
└── reviewing-agent-output/SKILL.md  → Resource
```

### Adding a New Skill

1. Create `skills/<name>/SKILL.md`
2. Add YAML frontmatter with `name`, `description`, `user-invocable`
3. The provider auto-discovers it on next server start

---

## Commands Provider

**Module:** `bridge/providers/commands.py`

Discovers and serves command resources from the `commands/` directory.

### Discovery

```
commands/
├── codegen.md      → /codegen command
├── cg-status.md    → /cg-status command
├── cg-logs.md      → /cg-logs command
├── cg-merge.md     → /cg-merge command
└── cg-settings.md  → /cg-settings command
```

### Adding a New Command

1. Create `commands/<name>.md`
2. Add YAML frontmatter with `description`
3. The provider auto-discovers it on next server start

---

## Agents Provider

**Module:** `bridge/providers/agents.py`

Discovers and serves agent resources from the `agents/` directory.

### Discovery

```
agents/
├── codegen-delegator.md  → codegen-delegator agent
└── pr-reviewer.md        → pr-reviewer agent
```

### Adding a New Agent

1. Create `agents/<name>.md`
2. Add YAML frontmatter with `name` and `description`
3. The provider auto-discovers it on next server start

---

## Remote Proxy

**Module:** `bridge/providers/remote.py`

Mounts the hosted Codegen MCP server as a proxy, doubling the tool surface with server-side tools.

### Configuration

**Disabled by default.** Enable with:

```bash
export CODEGEN_ENABLE_REMOTE_PROXY=true
```

### How It Works

```python
remote_proxy = create_remote_proxy(api_key=api_key)
server.mount(remote_proxy, namespace="remote")
```

All remote tools are namespaced under `remote_*` to avoid conflicts with local tools.

### Caveats

- Blocks lifespan shutdown if the remote server is slow to respond
- Requires network connectivity to Codegen servers
- Remote tools don't benefit from local middleware (annotations, elicitation, etc.)

---

## Resource Counts

| Source | Resources |
|--------|-----------|
| Manual (`bridge/resources/`) | 8 (3 config + 2 platform + 3 templates) |
| `SkillsDirectoryProvider` | 20 (10 skills × ~2 resources each) |
| `CommandsProvider` | 5 commands |
| `AgentsProvider` | 2 agents |
| **Total** | **~33** |

---

## See Also

- **[[Architecture]]** — How providers fit into the system
- **[[Tools-Reference]]** — Both manual and auto-generated tools
- **[[Skills-Guide]]** — Skills served by the SkillsDirectoryProvider
- **[[Development-Guide]]** — How to add new providers

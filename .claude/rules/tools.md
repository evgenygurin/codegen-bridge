---
paths:
  - bridge/tools/**
  - bridge/sampling/tools.py
  - bridge/openapi_utils.py
---

# Tools

## Tool Modules

| Module | Count | Tools |
|--------|-------|-------|
| `tools/agent/` | 13 | `create_run`, `get_run`, `report_run_result`, `list_runs`, `resume_run`, `stop_run`, `ban_run`, `unban_run`, `remove_from_pr`, `get_logs`, `create_and_monitor`, `monitor_run_background`, `bulk_create_runs` |
| `tools/execution.py` | 3 | `start_execution`, `get_execution_context`, `get_agent_rules` |
| `tools/pr.py` | 2 | `edit_pr`, `edit_pr_simple` |
| `tools/setup/` | 13 | `list_users`, `list_orgs`, `get_user`, `list_repos`, `get_organization_settings`, `get_current_user`, `get_mcp_providers`, `get_oauth_status`, `revoke_oauth`, `get_check_suite_settings`, `update_check_suite_settings`, `generate_setup_commands`, `list_models` |
| `tools/integrations.py` | 8 | `get_integrations`, `get_webhook_config`, `set_webhook_config`, `delete_webhook_config`, `test_webhook`, `analyze_sandbox_logs`, `generate_slack_token`, `check_integration_health` |
| `tools/analytics.py` | 1 | `get_run_analytics` |
| `tools/session.py` | 3 | `set_session_preference`, `get_session_preferences`, `clear_session_preferences` |
| `tools/settings.py` | 2 | `get_settings`, `update_settings` |
| `sampling/tools.py` | 4 | `summarise_run`, `summarise_execution`, `generate_task_prompt`, `analyse_run_logs` |
| **Total manual** | **49** | |
| Auto-generated (OpenAPI) | 5 | Via `OpenAPIProvider` from `openapi_spec.json` |

## Naming Convention

All tools follow: `codegen_<verb>_<noun>`

- Verbs: `create`, `get`, `list`, `update`, `delete`, `set`, `start`, `stop`, `ban`, `unban`, `resume`, `remove`, `edit`, `test`, `generate`, `analyse`, `summarise`
- Auto-generated tools mapped via `TOOL_NAMES` dict in `openapi_utils.py`

## Adding a New Tool

1. Choose the right module in `bridge/tools/` (or create new one)
2. Define tool function inside a `register_*_tools(mcp: FastMCP)` function
3. Use `@mcp.tool()` decorator with appropriate `tags` and `icons`
4. Add DI parameters: `ctx: Context = CurrentContext()`, `client: CodegenClient = Depends(get_client)`
5. Add `# type: ignore[arg-type]` after each `Depends()` call (mypy limitation)
6. Return JSON string (`json.dumps(...)`) — never raw dicts
7. If tool is dangerous: add `tags={"dangerous"}` and use `confirm_action()` from `bridge/elicitation`
8. If tool needs pagination: use `cursor` and `limit` params, follow pattern in `list_runs`
9. Register in `server.py` if creating new module
10. Add tests in corresponding `tests/tools/` file

## B008 Suppression

`Depends()` and `CurrentContext()` in default args triggers ruff B008 (function call in default). Suppressed in `pyproject.toml`:

```toml
[tool.ruff.lint.per-file-ignores]
"bridge/dependencies.py" = ["B008"]
"bridge/tools/*.py" = ["B008"]
"bridge/resources/*.py" = ["B008"]
"bridge/sampling/tools.py" = ["B008"]
```

## Elicitation Pattern for Dangerous Tools

```python
from bridge.elicitation import confirm_action

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

The `DangerousToolGuardMiddleware` also gates tools tagged `"dangerous"` — requires `CODEGEN_ALLOW_DANGEROUS_TOOLS=true` or explicit `confirmed=True`.

## Pagination Pattern

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

## OpenAPI Auto-Generated Tools

`openapi_utils.py` flow:
1. `load_and_patch_spec(org_id)` — load `bridge/openapi_spec.json`, replace `{org_id}` with real value
2. `build_route_maps()` — whitelist endpoints, catch-all `MCPType.EXCLUDE` for rest
3. `TOOL_NAMES` — map operationIds to human names (e.g. `get_users_v1_organizations__org_id__users_get` → `codegen_list_users`)
4. `create_openapi_provider(http_client, org_id)` — returns `OpenAPIProvider`
5. Provider added in lifespan; if it fails, manual tools still work

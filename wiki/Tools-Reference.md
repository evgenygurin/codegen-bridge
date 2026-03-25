# Tools Reference

Codegen Bridge provides **51 unique MCP tools**: 49 manual tools across 8 tool modules + 4 sampling tools, plus 2 unique auto-generated tools from the OpenAPI spec.

## Tool Naming Convention

All tools follow: `codegen_<verb>_<noun>`

**Verbs:** `create`, `get`, `list`, `update`, `delete`, `set`, `start`, `stop`, `ban`, `unban`, `resume`, `remove`, `edit`, `test`, `generate`, `analyse`, `summarise`

## Tool Annotations

Every manual tool has an explicit annotation from 6 presets:

| Preset | Read-Only | Destructive | Idempotent | Open World | Usage |
|--------|-----------|-------------|------------|------------|-------|
| `READ_ONLY` | Yes | No | Yes | Yes | External API reads |
| `READ_ONLY_LOCAL` | Yes | No | Yes | No | Local state reads |
| `CREATES` | No | No | No | Yes | New external resources |
| `MUTATES` | No | No | Yes | Yes | Idempotent updates |
| `MUTATES_LOCAL` | No | No | Yes | No | Local-only updates |
| `DESTRUCTIVE` | No | Yes | No | Yes | Irreversible operations |

---

## 1. Agent Tools (13 tools) — `bridge/tools/agent/`

Core tools for managing Codegen agent run lifecycle.

### Lifecycle (`lifecycle.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_create_run` | `CREATES` | Create a new cloud agent run. Enriches prompt from ExecutionContext; auto-detects repo; elicits model selection + repo confirmation. |
| `codegen_resume_run` | `MUTATES` | Resume a paused agent run with new instructions. |
| `codegen_stop_run` | `DESTRUCTIVE` | Stop a running agent (irreversible). Requires confirmation. |

### Queries (`queries.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_get_run` | `READ_ONLY` | Get status, results, and PR links for a specific run. Pure read via `RunService`. |
| `codegen_list_runs` | `READ_ONLY` | List recent agent runs with pagination (`cursor` + `limit`). |
| `codegen_report_run_result` | `MUTATES` | Write a TaskReport to ContextRegistry; advances execution task index. |

### Moderation (`moderation.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_ban_run` | `DESTRUCTIVE` | Permanently ban an agent. Requires confirmation. |
| `codegen_unban_run` | `MUTATES` | Lift ban on an agent. |
| `codegen_remove_from_pr` | `DESTRUCTIVE` | Remove agent from a PR on GitHub. Requires confirmation. |

### Logs (`logs.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_get_logs` | `READ_ONLY` | Fetch step-by-step execution logs with pagination. Supports `limit` and `reverse` parameters. |

### Workflow (`workflow.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_create_and_monitor` | `CREATES` | Fire-and-wait: creates a run then auto-polls until terminal status. Exponential backoff, max 60 polls. |

### Background (`background.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_monitor_run_background` | `READ_ONLY` | Start background monitoring of an existing run via FastMCP background tasks. |

### Bulk (`bulk.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_bulk_create_runs` | `CREATES` | Create multiple agent runs in a single batch call. Returns all run IDs at once. |

---

## 2. Execution Tools (3 tools) — `bridge/tools/execution.py`

Multi-task execution context management.

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_start_execution` | `CREATES` | Initialize an execution context with goal, tasks, tech stack, and architecture. Supports `mode="adhoc"` or `mode="plan"`. |
| `codegen_get_execution_context` | `READ_ONLY` | Read the current execution state from ContextRegistry. |
| `codegen_get_agent_rules` | `READ_ONLY` | Fetch organization-specific agent rules from the API. |

---

## 3. PR Tools (2 tools) — `bridge/tools/pr.py`

Pull request state management.

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_edit_pr` | `DESTRUCTIVE` | Change PR state (`open`, `closed`, `draft`, `ready_for_review`). Requires `repo_id` and `pr_id`. |
| `codegen_edit_pr_simple` | `DESTRUCTIVE` | Same as above but only requires `pr_id`. |

---

## 4. Setup Tools (13 tools) — `bridge/tools/setup/`

Organization, repository, and user management.

### Organizations (`organizations.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_list_orgs` | `READ_ONLY` | List all organizations. |
| `codegen_get_organization_settings` | `READ_ONLY` | Get org settings. |
| `codegen_list_repos` | `READ_ONLY` | List repositories in the organization. |
| `codegen_generate_setup_commands` | `CREATES` | Generate setup commands. **Note:** Creates an agent run under the hood. |

### Users (`users.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_get_current_user` | `READ_ONLY` | Get the authenticated user. |
| `codegen_list_users` | `READ_ONLY` | List users in the organization. |
| `codegen_get_user` | `READ_ONLY` | Get a specific user by ID. |

### OAuth (`oauth.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_get_mcp_providers` | `READ_ONLY` | List available MCP providers. |
| `codegen_get_oauth_status` | `READ_ONLY` | Check OAuth token status. |
| `codegen_revoke_oauth` | `DESTRUCTIVE` | Revoke OAuth token permanently. Requires confirmation. |

### Check Suite (`check_suite.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_get_check_suite_settings` | `READ_ONLY` | Get CI/CD check suite configuration. |
| `codegen_update_check_suite_settings` | `MUTATES` | Update check suite configuration. |

### Models (`models.py`)

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_list_models` | `READ_ONLY` | List available AI models and providers. |

---

## 5. Integration Tools (8 tools) — `bridge/tools/integrations.py`

Webhooks, sandbox, Slack, and integration health.

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_get_integrations` | `READ_ONLY` | List configured integrations. |
| `codegen_get_webhook_config` | `READ_ONLY` | Get webhook configuration. |
| `codegen_set_webhook_config` | `MUTATES` | Create or update a webhook. |
| `codegen_delete_webhook_config` | `DESTRUCTIVE` | Permanently delete a webhook. Requires confirmation. |
| `codegen_test_webhook` | `CREATES` | Send a test HTTP request to a webhook URL. |
| `codegen_analyze_sandbox_logs` | `CREATES` | AI-powered sandbox log analysis. **Note:** Creates an agent run. |
| `codegen_generate_slack_token` | `CREATES` | Generate a new Slack integration token. |
| `codegen_check_integration_health` | `READ_ONLY` | Verify webhook/integration connectivity and health. |

---

## 6. Analytics Tools (1 tool) — `bridge/tools/analytics.py`

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_get_run_analytics` | `READ_ONLY` | Aggregate statistics: totals, success rate, status distribution, duration metrics. |

---

## 7. Session Tools (3 tools) — `bridge/tools/session.py`

Per-session in-memory key/value storage.

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_set_session_preference` | `MUTATES_LOCAL` | Set a session-scoped key/value preference. |
| `codegen_get_session_preferences` | `READ_ONLY_LOCAL` | Get all session preferences. |
| `codegen_clear_session_preferences` | `MUTATES_LOCAL` | Clear all session preferences. |

---

## 8. Settings Tools (2 tools) — `bridge/tools/settings.py`

Plugin settings stored in `.claude-plugin/settings.json`.

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_get_settings` | `READ_ONLY_LOCAL` | Read current plugin settings. |
| `codegen_update_settings` | `MUTATES_LOCAL` | Update plugin settings (model, auto_monitor, poll_interval). |

---

## 9. Sampling Tools (4 tools) — `bridge/sampling/tools.py`

Server-side LLM sampling via `ctx.sample()`.

| Tool | Annotation | Description |
|------|-----------|-------------|
| `codegen_summarise_run` | `READ_ONLY` | Summarize a run by reading its data and logs, then invoking LLM sampling. |
| `codegen_summarise_execution` | `READ_ONLY` | Summarize an entire execution context via LLM sampling. |
| `codegen_generate_task_prompt` | `READ_ONLY` | Generate an optimized task prompt from execution context via LLM. |
| `codegen_analyse_run_logs` | `READ_ONLY` | Analyze run logs for patterns and issues via LLM sampling. |

---

## 10. Auto-Generated Tools (OpenAPI)

5 tools generated from `openapi_spec.json` via `OpenAPIProvider`. 3 overlap with manual tools, yielding 2 unique additions:

| Auto-Generated Tool | Unique? | Manual Equivalent |
|---------------------|---------|-------------------|
| `codegen_get_current_user` | No | `tools/setup/users.py` |
| `codegen_get_models` | **Yes** | — |
| `codegen_revoke_oauth_token` | **Yes** | Partial overlap with `codegen_revoke_oauth` (no elicitation) |
| `codegen_get_oauth_status` | No | `tools/setup/oauth.py` |
| `codegen_get_mcp_providers` | No | `tools/setup/oauth.py` |

**Note:** Auto-generated tools have no annotations, no elicitation, and no progress reporting. Prefer manual tools for interactive use.

---

## Dangerous Tools

Tools that require confirmation before execution:

| Tool | Protection |
|------|-----------|
| `codegen_stop_run` | Elicitation + dangerous tag + guard middleware |
| `codegen_ban_run` | Elicitation + dangerous tag + guard middleware |
| `codegen_remove_from_pr` | Elicitation + dangerous tag + guard middleware |
| `codegen_edit_pr` | Dangerous tag + guard middleware |
| `codegen_edit_pr_simple` | Dangerous tag + guard middleware |
| `codegen_delete_webhook_config` | Dangerous tag + guard middleware |
| `codegen_revoke_oauth` | Elicitation + dangerous tag + guard middleware |

The `DangerousToolGuardMiddleware` blocks these unless `CODEGEN_ALLOW_DANGEROUS_TOOLS=true` or `confirmed=True` is passed.

## Pagination Pattern

Tools that return lists support cursor-based pagination:

```python
codegen_list_runs(cursor=None, limit=10)
# Returns: {"runs": [...], "next_cursor": "abc123", "has_more": true}

codegen_list_runs(cursor="abc123", limit=10)
# Returns the next page
```

## See Also

- **[[Skills-Guide]]** — Skills that orchestrate tool usage
- **[[Middleware-and-Transforms]]** — How tools are protected and transformed
- **[[Development-Guide]]** — How to add new tools

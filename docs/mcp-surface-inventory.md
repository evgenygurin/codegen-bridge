# MCP Surface Inventory — codegen-bridge v0.5.0

> Semantic classification of every MCP component based on **actual source code audit**.
> Updated after v0.5 architecture upgrade (service extraction, annotations, resource templates, P0 safety fixes).

---

## Legend

| Column | Meaning |
|--------|---------|
| **RO** | `readOnlyHint` — safe to retry, no mutations |
| **DH** | `destructiveHint` — irreversible external state change |
| **IH** | `idempotentHint` — same input = same result, safe to retry |
| **OW** | `openWorldHint` — affects state beyond MCP (API calls, webhooks, PRs) |
| **Annotation** | `ToolAnnotations` preset from `bridge/annotations.py` |
| **Side Effects** | Hidden mutations not obvious from name/docstring |
| **Resource?** | Could this be a static MCP Resource instead of a tool? |

---

## 1. Agent Tools (11 tools) — `bridge/tools/agent/`

### 1.1 Lifecycle (`lifecycle.py`)

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_create_run` | `CREATES` | `execution` | Creates cloud agent run; enriches prompt from ExecutionContext; updates task status; auto-detects repo; elicits model selection + repo confirmation | No |
| `codegen_resume_run` | `MUTATES` | `execution` | Resumes paused agent run on remote platform | No |
| `codegen_stop_run` | `DESTRUCTIVE` | `execution, dangerous` | Stops running agent (irreversible); elicits confirmation | No |

### 1.2 Queries (`queries.py`)

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_get_run` | `READ_ONLY` | `execution` | **None** — pure read via `RunService.get_run()` | Yes (resource template exists) |
| `codegen_report_run_result` | `MUTATES` | `execution` | Writes TaskReport to ContextRegistry; advances `current_task_index` | No |
| `codegen_list_runs` | `READ_ONLY` | `execution` | None — pure paginated list via `RunService.list_runs()` | Yes |

> **v0.5 FIX:** The v0.4 `codegen_get_run` had conditional side effects (writes to ContextRegistry when `execution_id` was provided and status was terminal). This was **split** into pure-read `codegen_get_run` + explicit-mutation `codegen_report_run_result`. The critical finding from v0.4 audit is now resolved.

### 1.3 Moderation (`moderation.py`)

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_ban_run` | `DESTRUCTIVE` | `execution, dangerous` | Bans agent permanently; elicits confirmation | No |
| `codegen_unban_run` | `MUTATES` | `execution` | Lifts ban on agent | No |
| `codegen_remove_from_pr` | `DESTRUCTIVE` | `execution, dangerous` | Removes agent from PR on GitHub; elicits confirmation | No |

### 1.4 Logs (`logs.py`)

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_get_logs` | `READ_ONLY` | `execution` | None — pure read with progress reporting | Yes (resource template exists) |

### 1.5 Workflow (`workflow.py`) — **NEW in v0.5**

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_create_and_monitor` | `CREATES` | `execution, workflow` | Creates run + auto-polls until terminal status; uses `RunService.get_run()` for side-effect-free polling; exponential backoff with jitter | No |

**`codegen_create_and_monitor` details:**
- Combines `create_run` + `get_run` polling into fire-and-wait
- Elicits model selection + confirmation when `confirmed=False`
- Rate-budget-controlled via `CodegenClient`
- `max_polls=60`, `poll_interval=10s`, exponential backoff (doubles every 10 polls, capped 4x)
- Runs as background task via `task=MONITOR_TASK`

---

## 2. Execution Tools (3 tools) — `bridge/tools/execution.py`

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_start_execution` | `CREATES` | `execution` | Creates ExecutionContext in ContextRegistry; loads agent rules from API; detects repo | No |
| `codegen_get_execution_context` | `READ_ONLY` | `execution` | None — reads from ContextRegistry | Yes (resource template exists) |
| `codegen_get_agent_rules` | `READ_ONLY` | `execution` | None — reads from API | Yes |

---

## 3. PR Tools (2 tools) — `bridge/tools/pr.py`

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_edit_pr` | `DESTRUCTIVE` | `pull-requests, dangerous` | Mutates PR state on GitHub (open, closed, draft, ready_for_review) | No |
| `codegen_edit_pr_simple` | `DESTRUCTIVE` | `pull-requests, dangerous` | Same as above, requires only `pr_id` (no `repo_id`) | No |

---

## 4. Setup Tools (12 tools) — `bridge/tools/setup/`

### 4.1 Organizations (`organizations.py`)

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_list_orgs` | `READ_ONLY` | `setup` | None | Yes |
| `codegen_get_organization_settings` | `READ_ONLY` | `setup` | None | Yes |
| `codegen_list_repos` | `READ_ONLY` | `setup` | None | Yes |
| `codegen_generate_setup_commands` | `CREATES` | `setup` | **CREATES AN AGENT RUN** on remote platform — despite name suggesting it only generates commands | No |

> **TRAP: `codegen_generate_setup_commands`** calls `client.create_run()` under the hood.

### 4.2 Users (`users.py`)

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_get_current_user` | `READ_ONLY` | `setup` | None | Yes |
| `codegen_list_users` | `READ_ONLY` | `setup` | None | Yes |
| `codegen_get_user` | `READ_ONLY` | `setup` | None | Yes |

### 4.3 OAuth (`oauth.py`)

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_get_mcp_providers` | `READ_ONLY` | `setup` | None | Yes |
| `codegen_get_oauth_status` | `READ_ONLY` | `setup` | None | Yes |
| `codegen_revoke_oauth` | `DESTRUCTIVE` | `setup, dangerous` | Revokes OAuth token permanently; elicits confirmation | No |

### 4.4 Check Suite (`check_suite.py`)

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_get_check_suite_settings` | `READ_ONLY` | `setup` | None | Yes |
| `codegen_update_check_suite_settings` | `MUTATES` | `setup` | Mutates remote check suite configuration | No |

---

## 5. Integration Tools (7 tools) — `bridge/tools/integrations.py`

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_get_integrations` | `READ_ONLY` | `integrations` | None | Yes |
| `codegen_get_webhook_config` | `READ_ONLY` | `integrations` | None | Yes |
| `codegen_set_webhook_config` | `MUTATES` | `integrations` | Creates/updates webhook on remote platform | No |
| `codegen_delete_webhook_config` | `DESTRUCTIVE` | `integrations, dangerous` | Permanently deletes webhook | No |
| `codegen_test_webhook` | `CREATES` | `integrations` | **Sends HTTP request to external URL** — looks read-only but has external side effects | No |
| `codegen_analyze_sandbox_logs` | `CREATES` | `integrations` | **CREATES AN AGENT RUN** for AI analysis — name suggests read-only log analysis | No |
| `codegen_generate_slack_token` | `CREATES` | `integrations` | Creates a new Slack integration token | No |

> **TRAP: `codegen_analyze_sandbox_logs`** calls `client.create_run()` to delegate analysis to an AI agent.

> **TRAP: `codegen_test_webhook`** sends a real HTTP POST to the configured webhook URL.

---

## 6. Settings Tools (2 tools) — `bridge/tools/settings.py`

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_get_settings` | `READ_ONLY_LOCAL` | `settings` | None — reads local `.claude-plugin/settings.json` | Yes |
| `codegen_update_settings` | `MUTATES_LOCAL` | `settings` | Writes to local settings file (no remote side effects) | No |

---

## 7. Sampling Tools (4 tools) — `bridge/sampling/tools.py`

All use `ctx.sample()` (server-side LLM invocation).

| Tool | Annotation | Tags | Side Effects | Resource? |
|------|-----------|------|-------------|-----------|
| `codegen_summarise_run` | `READ_ONLY` | `sampling` | Reads run + logs, invokes LLM sampling — no persistent writes | No |
| `codegen_summarise_execution` | `READ_ONLY` | `sampling` | Reads execution context, invokes LLM sampling | No |
| `codegen_generate_task_prompt` | `READ_ONLY` | `sampling` | Reads execution context, invokes LLM sampling | No |
| `codegen_analyse_run_logs` | `READ_ONLY` | `sampling` | Reads run logs, invokes LLM sampling | No |

---

## 8. Services Layer — **NEW in v0.5** — `bridge/services/`

Business logic extracted from tools into testable service classes.

| Service | Module | Methods | Consumers |
|---------|--------|---------|-----------|
| `RunService` | `services/runs.py` | `get_run`, `list_runs`, `report_run_result`, `create_run`, `detect_repo` | `tools/agent/queries.py`, `tools/agent/workflow.py`, `resources/templates.py` |
| `ExecutionService` | `services/execution.py` | `get_execution_context` | `tools/execution.py`, `resources/templates.py` |

**DI access:** Both services injected via `Depends(get_run_service)` / `Depends(get_execution_service)` from `bridge/dependencies.py`.

---

## 9. Resources (8) — `bridge/resources/`

### 9.1 Config Resources (`config.py`) — 3 resources

| URI | Type | Content |
|-----|------|---------|
| `codegen://config` | Static | Org ID, API base, has_api_key flag |
| `codegen://execution/current` | Dynamic | Active ExecutionContext from ContextRegistry (or `no_active_execution`) |
| `codegen://prompts/best-practices` | Static | Best practices text from `build_best_practices()` |

### 9.2 Platform Resources (`platform.py`) — 2 resources — **NEW in v0.5**

| URI | Type | Content |
|-----|------|---------|
| `codegen://platform/integrations-guide` | Static | Comprehensive reference for all supported integrations (GitHub, Linear, Slack, Jira, Figma, Notion, Sentry) |
| `codegen://platform/cli-sdk` | Static | CLI commands, SDK quick-start, environment variables, key classes |

### 9.3 Resource Templates (`templates.py`) — 3 templates — **NEW in v0.5**

| URI Template | Type | Content | Delegates to |
|-------------|------|---------|-------------|
| `codegen://runs/{run_id}` | Parameterized | Run status, result, summary, PRs | `RunService.get_run()` |
| `codegen://runs/{run_id}/logs` | Parameterized | Step-by-step execution logs (last 20) | `RunService.get_logs()` |
| `codegen://execution/{execution_id}` | Parameterized | Execution context state | `ExecutionService.get_execution_context()` |

Resource templates delegate to the **same service layer** as tools, ensuring data format consistency.

---

## 10. Prompts (4) — `bridge/prompts/templates.py`

| Name | Purpose | Executable? |
|------|---------|-------------|
| `delegate_task` | Prompt template for task delegation workflow | No — decorative text |
| `monitor_runs` | Prompt template for run monitoring workflow | No — decorative text |
| `build_task_prompt_template` | Template for constructing agent task prompts | No — decorative text |
| `execution_summary` | Template for summarizing execution results | No — decorative text |

---

## 11. Annotations (6 presets) — **NEW in v0.5** — `bridge/annotations.py`

| Preset | RO | DH | IH | OW | Usage |
|--------|----|----|----|----|-------|
| `READ_ONLY` | yes | no | yes | yes | External API reads (get_run, list_runs, etc.) |
| `READ_ONLY_LOCAL` | yes | no | yes | no | Local state reads (get_settings) |
| `CREATES` | no | no | no | yes | New external resources (create_run, create_and_monitor) |
| `MUTATES` | no | no | yes | yes | Idempotent updates (resume_run, edit settings) |
| `MUTATES_LOCAL` | no | no | yes | no | Local-only updates (update_settings) |
| `DESTRUCTIVE` | no | yes | no | yes | Irreversible (stop_run, ban_run, edit_pr, delete_webhook) |

---

## 12. Auto-Generated Tools (5) — `bridge/openapi_utils.py`

Generated from `openapi_spec.json` via `OpenAPIProvider`. **Reduced from ~21 to 5** in P0-C to eliminate conflicts with manual tools.

| operationId (raw) | Tool Name | Overlap with Manual? |
|--------------------|-----------|---------------------|
| `get_current_user_info_v1_users_me_get` | `codegen_get_current_user` | Yes — mirrors `tools/setup/users.py` |
| `get_available_models_v1_organizations__org_id__models_get` | `codegen_get_models` | No — unique endpoint |
| `revoke_oauth_token_v1_oauth_tokens_revoke_post` | `codegen_revoke_oauth_token` | Partial — manual tool uses elicitation |
| `get_oauth_token_status_v1_oauth_tokens_status_get` | `codegen_get_oauth_status` | Yes — mirrors `tools/setup/oauth.py` |
| `get_mcp_providers_v1_mcp_providers_get` | `codegen_get_mcp_providers` | Yes — mirrors `tools/setup/oauth.py` |

**Note:** Auto-generated tools have no annotations, no elicitation, no progress reporting. Prefer manual tools for interactive use.

---

## 13. Dangerous Tool Guard — `bridge/middleware/authorization.py`

### 13.1 DEFAULT_DANGEROUS_TOOLS (6 names)

```python
DEFAULT_DANGEROUS_TOOLS = frozenset({
    "codegen_stop_run",
    "codegen_edit_pr",
    "codegen_edit_repo_pr",
    "codegen_delete_webhook",
    "codegen_set_webhook",
    "codegen_revoke_oauth_token",
})
```

### 13.2 Guard Strategy

The `DangerousToolGuardMiddleware` blocks a tool when **either**:
1. Tool name is in `DEFAULT_DANGEROUS_TOOLS`, OR
2. Tool has the `"dangerous"` tag

Unless `CODEGEN_ALLOW_DANGEROUS_TOOLS=true` or the tool receives `confirmed=True`.

### 13.3 Known Discrepancy

| Guard Name | Actual Tool | Status |
|-----------|-------------|--------|
| `codegen_edit_repo_pr` | `codegen_edit_pr_simple` | **Mismatch** — guard references non-existent name |
| `codegen_delete_webhook` | `codegen_delete_webhook_config` | **Mismatch** — guard references non-existent name |
| `codegen_set_webhook` | `codegen_set_webhook_config` | **Mismatch** — guard references non-existent name |

These tools are **still protected** by the `"dangerous"` tag check (fallback path). The name-based check is a belt-and-suspenders layer that currently has stale names.

---

## 14. Safety Configuration — **NEW in v0.5 (P0)**

### 14.1 Tool Call Caching (P0-A)

`ResponseCachingMiddleware` now passes `CallToolSettings(enabled=config.caching.tool_call_enabled)`.

**Default: `tool_call_enabled=False`** — tool call results are NOT cached. This prevents stale data from being served for polling tools like `get_run`.

### 14.2 Rate Limiting

`RateLimitingMiddleware` with default token-bucket configuration. Additionally, `CodegenClient` has its own rate budget that `codegen_create_and_monitor` respects during polling.

---

## 15. Middleware Stack (9 layers) — `bridge/middleware/stack.py`

| # | Middleware | Source | Purpose |
|---|-----------|--------|---------|
| 1 | `ErrorHandlingMiddleware` | FastMCP | Catch exceptions, transform errors |
| 2 | `PingMiddleware` | FastMCP | Keep connections alive |
| 3 | `DangerousToolGuardMiddleware` | `bridge/middleware/authorization.py` | Block dangerous tools (name + tag strategy) |
| 4 | `LoggingMiddleware` | FastMCP | Structured request/response logging |
| 5 | `TelemetryMiddleware` | `bridge/telemetry/middleware.py` | OpenTelemetry tracing and metrics |
| 6 | `TimingMiddleware` | FastMCP | Execution duration per operation |
| 7 | `RateLimitingMiddleware` | FastMCP | Token-bucket throttling |
| 8 | `ResponseCachingMiddleware` | FastMCP | TTL-based caching (`tool_call_enabled=False`) |
| 9 | `ResponseLimitingMiddleware` | FastMCP | Truncate oversized tool output |

---

## 16. Summary Statistics

| Category | Count | Read-Only | Mutating | Destructive | Has Hidden Side Effects |
|----------|-------|-----------|----------|-------------|------------------------|
| Agent tools | 11 | 3 (get_run, list_runs, get_logs) | 4 | 3 (stop, ban, remove_from_pr) | 0 |
| Execution tools | 3 | 2 | 1 | 0 | 0 |
| PR tools | 2 | 0 | 0 | 2 | 0 |
| Setup tools | 12 | 10 | 2 | 1 (revoke_oauth) | 1 (generate_setup_commands) |
| Integration tools | 7 | 2 | 1 | 1 (delete_webhook) | 2 (analyze_sandbox_logs, test_webhook) |
| Settings tools | 2 | 1 | 1 | 0 | 0 |
| Sampling tools | 4 | 4 | 0 | 0 | 0 |
| **Total manual** | **41** | **22** | **9** | **7** | **3** |
| Services | 2 | — | — | — | — |
| Resources | 8 | 8 | — | — | 0 |
| Resource templates | 3 | 3 | — | — | 0 |
| Prompts | 4 | 4 | — | — | 0 |
| Annotations presets | 6 | — | — | — | — |
| Auto-generated | 5 | 4 | 0 | 1 (revoke_oauth_token) | 0 |

### v0.5 Changes from v0.4

| Metric | v0.4 | v0.5 | Change |
|--------|------|------|--------|
| Manual tools | 39 | 41 | +2 (report_run_result, create_and_monitor) |
| Auto-generated tools | ~21 | 5 | −16 (P0-C conflict cleanup) |
| Resources | 3 | 8 | +5 (2 platform, 3 templates) |
| Services | 0 | 2 | +2 (RunService, ExecutionService) |
| Tools with hidden side effects | 4 | 3 | −1 (get_run split resolved the worst one) |
| Dangerous tool names | 4 | 6 | +2 (set_webhook, revoke_oauth_token) |
| Annotation presets | 0 | 6 | +6 (new annotations module) |
| Tool call caching | enabled | **disabled** | P0-A safety fix |

### Remaining Issues for Future Phases

1. **Dangerous tool name mismatches** — 3 names in guard don't match actual tool names (Section 13.3). Protected by tag fallback, but names should be corrected.
2. **`codegen_generate_setup_commands`** still has a misleading name (creates agent run).
3. **`codegen_analyze_sandbox_logs`** still has a misleading name (creates agent run).
4. **Service extraction incomplete** — PR, integrations, setup tools still call `CodegenClient` directly instead of through services.

# MCP Surface Inventory — codegen-bridge v0.4.0

> Semantic classification of every MCP component based on **actual source code audit**, not names or docstrings.
> Created for v0.5 architecture planning.

---

## Legend

| Column | Meaning |
|--------|---------|
| **RO** | `readOnlyHint` — safe to retry, no mutations |
| **DH** | `destructiveHint` — irreversible external state change |
| **IH** | `idempotentHint` — same input = same result, safe to retry |
| **OW** | `openWorldHint` — affects state beyond MCP (API calls, webhooks, PRs) |
| **Side Effects** | Hidden mutations not obvious from name/docstring |
| **Resource?** | Could this be a static MCP Resource instead of a tool? |

---

## 1. Agent Tools (9 tools) — `bridge/tools/agent/`

### 1.1 Lifecycle (`lifecycle.py`)

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_create_run` | no | no | no | **yes** | `execution` | Creates cloud agent run; enriches prompt from ExecutionContext; updates task status to "running"; auto-detects repo; elicits model selection + repo confirmation | No |
| `codegen_resume_run` | no | no | no | **yes** | `execution` | Resumes paused agent run on remote platform | No |
| `codegen_stop_run` | no | **yes** | yes | **yes** | `execution, dangerous` | Stops running agent (irreversible); elicits confirmation | No |

**`codegen_create_run` complexity:**
- 5-step progress reporting via `report(ctx, step, total, msg)`
- `execution_id` triggers: prompt enrichment via `build_task_prompt()`, task status update to "running", repo_id inheritance from ExecutionContext
- Model selection via `select_choice()` when `model=None` and `confirmed=False`
- Repo confirmation via `confirm_action()` when `confirmed=False`

### 1.2 Queries (`queries.py`)

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_get_run` | **CONDITIONAL** | no | no | no | `execution` | **When `execution_id` is provided AND status is terminal**: writes TaskReport to ContextRegistry, advances `current_task_index`, parses logs for structured data | Yes (for read-only variant) |
| `codegen_list_runs` | yes | no | yes | no | `execution` | None — pure paginated list | Yes |

> **CRITICAL: `codegen_get_run` is NOT read-only.** Lines 84-140 contain conditional writes:
> ```python
> if execution_id is not None and run.status in ("completed", "failed"):
>     await registry.update_task(...)       # WRITES to storage
>     exec_ctx.current_task_index = idx + 1
>     await registry._save(exec_ctx)        # WRITES to storage
> ```
> Annotating this as `readOnlyHint=True` would be **incorrect**. It needs splitting into:
> 1. Pure `get_run` (resource or read-only tool)
> 2. `report_run_completion` (explicit mutation tool)

### 1.3 Moderation (`moderation.py`)

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_ban_run` | no | **yes** | yes | **yes** | `execution, dangerous` | Bans agent permanently; elicits confirmation | No |
| `codegen_unban_run` | no | no | yes | **yes** | `execution` | Lifts ban on agent | No |
| `codegen_remove_from_pr` | no | **yes** | yes | **yes** | `execution, dangerous` | Removes agent from PR on GitHub; elicits confirmation | No |

### 1.4 Logs (`logs.py`)

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_get_logs` | yes | no | yes | no | `execution` | None — pure read with progress reporting | Yes |

**Note:** Uses `task=GET_LOGS_TASK` for background execution support.

---

## 2. Execution Tools (3 tools) — `bridge/tools/execution.py`

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_start_execution` | no | no | no | no | `execution` | Creates ExecutionContext in ContextRegistry; loads agent rules from API; detects repo | No |
| `codegen_get_execution_context` | yes | no | yes | no | `execution` | None — reads from ContextRegistry | Yes |
| `codegen_get_agent_rules` | yes | no | yes | no | `execution` | None — reads from API | Yes |

---

## 3. PR Tools (2 tools) — `bridge/tools/pr.py`

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_edit_pr` | no | **yes** | no | **yes** | `execution, dangerous` | Mutates PR state on GitHub (title, description, labels, reviewers, merge, close) | No |
| `codegen_edit_pr_simple` | no | **yes** | no | **yes** | `execution, dangerous` | Same as above, simplified parameters | No |

---

## 4. Setup Tools (12 tools) — `bridge/tools/setup/`

### 4.1 Organizations (`organizations.py`)

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_list_orgs` | yes | no | yes | no | `setup` | None | Yes |
| `codegen_get_organization_settings` | yes | no | yes | no | `setup` | None | Yes |
| `codegen_list_repos` | yes | no | yes | no | `setup` | None | Yes |
| `codegen_generate_setup_commands` | **no** | no | no | **yes** | `setup` | **CREATES AN AGENT RUN** on remote platform — despite name suggesting it only generates commands | No |

> **TRAP: `codegen_generate_setup_commands`** calls `client.create_run()` under the hood.
> Name suggests read-only command generation, but it actually launches a cloud agent.

### 4.2 Users (`users.py`)

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_get_current_user` | yes | no | yes | no | `setup` | None | Yes |
| `codegen_list_users` | yes | no | yes | no | `setup` | None | Yes |
| `codegen_get_user` | yes | no | yes | no | `setup` | None | Yes |

**Note:** Contains `_user_to_dict()` helper — serialization duplication candidate (see Section 10).

### 4.3 OAuth (`oauth.py`)

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_get_mcp_providers` | yes | no | yes | no | `setup` | None | Yes |
| `codegen_get_oauth_status` | yes | no | yes | no | `setup` | None | Yes |
| `codegen_revoke_oauth` | no | **yes** | yes | **yes** | `setup, dangerous` | Revokes OAuth token permanently; elicits confirmation | No |

### 4.4 Check Suite (`check_suite.py`)

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_get_check_suite_settings` | yes | no | yes | no | `setup` | None | Yes |
| `codegen_update_check_suite_settings` | no | no | yes | **yes** | `setup` | Mutates remote check suite configuration | No |

---

## 5. Integration Tools (7 tools) — `bridge/tools/integrations.py`

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_get_integrations` | yes | no | yes | no | `integrations` | None | Yes |
| `codegen_get_webhook_config` | yes | no | yes | no | `integrations` | None | Yes |
| `codegen_set_webhook_config` | no | no | yes | **yes** | `integrations` | Creates/updates webhook on remote platform | No |
| `codegen_delete_webhook_config` | no | **yes** | yes | **yes** | `integrations, dangerous` | Permanently deletes webhook | No |
| `codegen_test_webhook` | **no** | no | no | **yes** | `integrations` | **Sends HTTP request to external URL** — looks read-only but has external side effects | No |
| `codegen_analyze_sandbox_logs` | **no** | no | no | **yes** | `integrations` | **CREATES AN AGENT RUN** for AI analysis — name suggests read-only log analysis | No |
| `codegen_generate_slack_token` | no | no | no | **yes** | `integrations` | Creates a new Slack integration token | No |

> **TRAP: `codegen_analyze_sandbox_logs`** calls `client.create_run()` to delegate analysis to an AI agent.
> Name implies passive log reading, actual behavior is active agent creation.

> **TRAP: `codegen_test_webhook`** sends a real HTTP POST to the configured webhook URL.
> Not idempotent — the target system processes the test payload.

---

## 6. Settings Tools (2 tools) — `bridge/tools/settings.py`

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_get_settings` | yes | no | yes | no | `settings` | None — reads local `.claude-plugin/settings.json` | Yes |
| `codegen_update_settings` | no | no | yes | no | `settings` | Writes to local settings file (no remote side effects) | No |

**Note:** These are LOCAL plugin settings, not Codegen platform settings.

---

## 7. Sampling Tools (4 tools) — `bridge/sampling/tools.py`

All use `ctx.sample()` (server-side LLM invocation).

| Tool | RO | DH | IH | OW | Tags | Side Effects | Resource? |
|------|----|----|----|----|------|-------------|-----------|
| `codegen_summarise_run` | yes | no | no | no | `sampling` | Reads run + logs, invokes LLM sampling — no persistent writes | No |
| `codegen_summarise_execution` | yes | no | no | no | `sampling` | Reads execution context, invokes LLM sampling | No |
| `codegen_generate_task_prompt` | yes | no | no | no | `sampling` | Reads execution context, invokes LLM sampling | No |
| `codegen_analyse_run_logs` | yes | no | no | no | `sampling` | Reads run logs, invokes LLM sampling | No |

**Note:** These tools contain **duplicate log formatting logic** that parallels `bridge/helpers/formatting.py` and `bridge/tools/agent/logs.py`. See Section 10.

---

## 8. Resources (3) — `bridge/resources/config.py`

| URI | Type | Content |
|-----|------|---------|
| `codegen://config` | Static | Org ID, API base, has_api_key flag |
| `codegen://execution/current` | Dynamic | Active ExecutionContext from ContextRegistry (or `no_active_execution`) |
| `codegen://prompts/best-practices` | Static | Best practices text from `build_best_practices()` |

**No resource templates exist.** The plan to add `codegen://runs/{run_id}` requires careful design — see Section 11.

---

## 9. Prompts (4) — `bridge/prompts/templates.py`

| Name | Purpose | Executable? |
|------|---------|-------------|
| `delegate_task` | Prompt template for task delegation workflow | No — decorative text |
| `monitor_runs` | Prompt template for run monitoring workflow | No — decorative text |
| `build_task_prompt_template` | Template for constructing agent task prompts | No — decorative text |
| `execution_summary` | Template for summarizing execution results | No — decorative text |

**These are purely decorative.** They generate formatted text but contain no workflow logic, tool composition, or orchestration.

---

## 10. Identified Duplication

### 10.1 Serialization Duplication

| Location | What it serializes | Pattern |
|----------|--------------------|---------|
| `helpers/formatting.py:format_run()` | AgentRun → dict (id, status, web_url, result, summary) | Dict comprehension |
| `helpers/formatting.py:format_run_basic()` | AgentRun → JSON (id, status, web_url) | `json.dumps()` |
| `tools/agent/queries.py:codegen_get_run` L54-82 | AgentRun → dict with PRs, source_type, parsed_logs | Inline dict building |
| `tools/setup/users.py:_user_to_dict()` | User → dict | Helper function |
| `sampling/tools.py` (multiple) | Logs → formatted string | Inline list comprehension |
| `helpers/formatting.py:format_logs()` | AgentRunWithLogs → JSON with truncated output | `json.dumps()` |

**Problem:** `codegen_get_run` does NOT use `format_run()` from helpers — it builds its own dict inline with additional fields (PRs, source_type, parsed_logs). This means any schema change requires updating BOTH locations.

### 10.2 Pagination Duplication

`cursor_to_offset()` + `build_paginated_response()` from `helpers/pagination.py` used in 5+ tools. Well-factored, no duplication here.

### 10.3 Progress Reporting Duplication

`_progress.py` in agent tools defines `report()` + step constants. Used only in `lifecycle.py` and `logs.py`. Localized, acceptable.

---

## 11. Resource Template Candidacy Analysis

Tools that could become MCP Resources (read-only, cacheable, addressable by URI):

| Current Tool | Proposed Resource URI | Cacheable? | Notes |
|-------------|-----------------------|------------|-------|
| `codegen_list_runs` | `codegen://runs?limit={n}&cursor={c}` | 30s TTL | Pure read, paginated |
| `codegen_get_run` (read path only) | `codegen://runs/{run_id}` | 10s TTL | **ONLY if side-effect logic is extracted** |
| `codegen_get_logs` | `codegen://runs/{run_id}/logs` | 30s TTL | Pure read |
| `codegen_get_execution_context` | `codegen://execution/{id}` | 5s TTL | Reads from local registry |
| `codegen_get_agent_rules` | `codegen://agent-rules` | 5min TTL | Rarely changes |
| `codegen_list_orgs` | `codegen://organizations` | 5min TTL | Rarely changes |
| `codegen_list_repos` | `codegen://repos` | 1min TTL | Semi-static |
| `codegen_get_organization_settings` | `codegen://organization/settings` | 1min TTL | Semi-static |
| `codegen_get_current_user` | `codegen://user/me` | 5min TTL | Static per session |
| `codegen_list_users` | `codegen://users` | 5min TTL | Rarely changes |
| `codegen_get_settings` | `codegen://settings` | Instant | Local file |
| `codegen_get_integrations` | `codegen://integrations` | 1min TTL | Semi-static |
| `codegen_get_webhook_config` | `codegen://integrations/webhooks` | 1min TTL | Semi-static |
| `codegen_get_check_suite_settings` | `codegen://check-suite/settings` | 1min TTL | Semi-static |
| `codegen_get_mcp_providers` | `codegen://mcp-providers` | 1min TTL | Semi-static |
| `codegen_get_oauth_status` | `codegen://oauth/status` | 1min TTL | Semi-static |

**16 out of 35 manual tools are resource candidates** — but this does NOT mean they should all be resources. Priority:

1. **High value:** `codegen://runs/{run_id}` (most polled), `codegen://execution/{id}` (orchestration state)
2. **Medium value:** `codegen://runs` (list), `codegen://runs/{run_id}/logs` (debugging)
3. **Low value:** Setup/config resources (called once per session)

---

## 12. Workflow Composition Candidates

Tools that naturally compose into multi-step workflows:

### 12.1 Create-and-Monitor (proposed new tool)

```text
codegen_create_run → poll codegen_get_run → return final result
```

**Requirements:**
- Outbound rate budget (separate from middleware rate limiting)
- Exponential backoff with jitter
- Timeout/max-polls guard
- Progress reporting via `report()`
- Must NOT use `execution_id` variant of `get_run` (avoids side effects during polling)

### 12.2 Execute-Plan (existing: `codegen_start_execution`)

```bash
codegen_start_execution → [for each task: codegen_create_run → poll → report]
```

Already partially implemented. The execution context tracks tasks, but orchestration is manual (Claude calls tools in sequence).

### 12.3 PR-Review-and-Merge

```text
codegen_get_run (get PR info) → review PR → codegen_edit_pr (merge/close)
```

Currently fully manual. Could be a sampling-backed workflow.

---

## 13. Tools with Misleading Names

| Tool | Name Suggests | Actual Behavior |
|------|--------------|-----------------|
| `codegen_get_run` | Pure read | Conditional writes to ContextRegistry when `execution_id` provided |
| `codegen_generate_setup_commands` | Generates text commands | **Creates a cloud agent run** |
| `codegen_analyze_sandbox_logs` | Reads and parses logs | **Creates a cloud agent run** for AI analysis |
| `codegen_test_webhook` | Validates config | **Sends HTTP POST** to external URL |
| `codegen_stop_run` | Pauses a run | Actually **bans** the run (calls `client.stop_run` which hits `/ban` endpoint) |

---

## 14. Auto-Generated Tools (~21) — `bridge/openapi_utils.py`

Generated from `openapi_spec.json` via `OpenAPIProvider`. Key characteristics:

- Names mapped via `TOOL_NAMES` dict (raw operationIds are unusable)
- `{org_id}` patched at spec load time
- Optional — if provider fails, all 35 manual tools still work
- No annotations, no elicitation, no progress reporting
- Subset of manual tool functionality with raw API access

These tools are a **fallback layer** — prefer manual tools which have proper error handling, elicitation, and context integration.

---

## 15. Summary Statistics

| Category | Count | Read-Only | Mutating | Destructive | Has Hidden Side Effects |
|----------|-------|-----------|----------|-------------|------------------------|
| Agent tools | 9 | 1 (list_runs) | 7 | 3 (stop, ban, remove_from_pr) | 1 (get_run) |
| Execution tools | 3 | 2 | 1 | 0 | 0 |
| PR tools | 2 | 0 | 2 | 2 | 0 |
| Setup tools | 12 | 10 | 2 | 1 (revoke_oauth) | 1 (generate_setup_commands) |
| Integration tools | 7 | 2 | 5 | 1 (delete_webhook) | 2 (analyze_sandbox_logs, test_webhook) |
| Settings tools | 2 | 1 | 1 | 0 | 0 |
| Sampling tools | 4 | 4 | 0 | 0 | 0 |
| **Total manual** | **39** | **20** | **18** | **7** | **4** |
| Resources | 3 | 3 | — | — | 0 |
| Prompts | 4 | 4 | — | — | 0 |
| Auto-generated | ~21 | ~12 | ~9 | ~3 | 0 |

### Critical Finding for v0.5 Planning

**4 tools have hidden side effects** that any annotation or refactoring plan MUST account for:

1. **`codegen_get_run`** — conditional writes to ContextRegistry (needs splitting)
2. **`codegen_generate_setup_commands`** — creates agent run (needs renaming or re-tagging)
3. **`codegen_analyze_sandbox_logs`** — creates agent run (needs renaming or re-tagging)
4. **`codegen_test_webhook`** — sends external HTTP (needs `openWorldHint=True`)

Any plan that applies `readOnlyHint=True` to these tools based on their names will **introduce incorrect MCP metadata that misleads clients**.

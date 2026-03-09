# MCP Surface Inventory — codegen-bridge v0.4.0

Complete inventory of all MCP components with semantic classification.

---

## Manual Tools (35)

### Agent Lifecycle (`bridge/tools/agent/lifecycle.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_create_run` | POST | mutating, non-idempotent, open-world | `readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True` |
| `codegen_resume_run` | POST | mutating, non-idempotent, open-world | `readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True` |
| `codegen_stop_run` | POST | mutating, destructive, non-idempotent | `readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True` |

### Agent Queries (`bridge/tools/agent/queries.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_get_run` | GET | read-only, idempotent, open-world | `readOnlyHint=True, openWorldHint=True` |
| `codegen_list_runs` | GET | read-only, idempotent, open-world | `readOnlyHint=True, openWorldHint=True` |

### Agent Logs (`bridge/tools/agent/logs.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_get_logs` | GET | read-only, idempotent, open-world | `readOnlyHint=True, openWorldHint=True` |

### Agent Moderation (`bridge/tools/agent/moderation.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_ban_run` | POST | mutating, destructive, non-idempotent | `readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True` |
| `codegen_unban_run` | POST | mutating, recovery, idempotent | `readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True` |
| `codegen_remove_from_pr` | POST | mutating, destructive, non-idempotent | `readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True` |

### Execution Context (`bridge/tools/execution.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_start_execution` | POST+GET | mutating (local+remote), non-idempotent | `readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True` |
| `codegen_get_execution_context` | local | read-only, idempotent, local-only | `readOnlyHint=True, openWorldHint=False` |
| `codegen_get_agent_rules` | GET | read-only, idempotent, open-world | `readOnlyHint=True, openWorldHint=True` |

### Pull Requests (`bridge/tools/pr.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_edit_pr` | PATCH | mutating, conditionally destructive | `readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True` |
| `codegen_edit_pr_simple` | PATCH | mutating, conditionally destructive | `readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True` |

### Integrations (`bridge/tools/integrations.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_get_integrations` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |
| `codegen_get_webhook_config` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |
| `codegen_set_webhook_config` | POST | mutating, idempotent | `readOnlyHint=False, idempotentHint=True, openWorldHint=True` |
| `codegen_delete_webhook_config` | DELETE | destructive, idempotent | `readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True` |
| `codegen_test_webhook` | POST | mutating, open-world side effects | `readOnlyHint=False, destructiveHint=False, openWorldHint=True` |
| `codegen_analyze_sandbox_logs` | POST | mutating (creates async run) | `readOnlyHint=False, destructiveHint=False, openWorldHint=True` |
| `codegen_generate_slack_token` | POST | mutating (generates token) | `readOnlyHint=False, destructiveHint=False, openWorldHint=True` |

### Settings (`bridge/tools/settings.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_get_settings` | local | read-only, local | `readOnlyHint=True, openWorldHint=False` |
| `codegen_update_settings` | local | mutating, idempotent, local | `readOnlyHint=False, idempotentHint=True, openWorldHint=False` |

### Organizations (`bridge/tools/setup/organizations.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_list_orgs` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |
| `codegen_get_organization_settings` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |
| `codegen_list_repos` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |
| `codegen_generate_setup_commands` | POST | mutating (creates async run) | `readOnlyHint=False, openWorldHint=True` |

### Users (`bridge/tools/setup/users.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_get_current_user` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |
| `codegen_list_users` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |
| `codegen_get_user` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |

### Check Suite (`bridge/tools/setup/check_suite.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_get_check_suite_settings` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |
| `codegen_update_check_suite_settings` | PATCH | mutating, idempotent | `readOnlyHint=False, idempotentHint=True, openWorldHint=True` |

### OAuth (`bridge/tools/setup/oauth.py`)

| Tool | HTTP | Semantics | Annotations |
|------|------|-----------|-------------|
| `codegen_get_mcp_providers` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |
| `codegen_get_oauth_status` | GET | read-only | `readOnlyHint=True, openWorldHint=True` |
| `codegen_revoke_oauth` | POST | destructive, non-idempotent | `readOnlyHint=False, destructiveHint=True, openWorldHint=True` |

---

## Resources (5)

| URI | Module | Type | Annotations |
|-----|--------|------|-------------|
| `codegen://config` | `resources/config.py` | Static | `readOnlyHint=True` |
| `codegen://execution/current` | `resources/config.py` | Dynamic (registry) | `readOnlyHint=True` |
| `codegen://prompts/best-practices` | `resources/config.py` | Computed | `readOnlyHint=True` |
| `codegen://platform/integrations-guide` | `resources/platform.py` | Static | `readOnlyHint=True` |
| `codegen://platform/cli-sdk` | `resources/platform.py` | Static | `readOnlyHint=True` |

## Prompts (4)

| Name | Module | Status |
|------|--------|--------|
| `delegate_task` | `prompts/templates.py` | Decorative text |
| `monitor_runs` | `prompts/templates.py` | Decorative text |
| `build_task_prompt_template` | `prompts/templates.py` | Decorative text |
| `execution_summary` | `prompts/templates.py` | Decorative text |

## Skills (4)

| Name | User-Invocable | Trigger |
|------|---------------|---------|
| `agent-monitoring` | No | get_run, get_logs, list_runs |
| `codegen-delegation` | No | create_run, start_execution |
| `executing-via-codegen` | Yes | Manual |
| `pr-management` | No | edit_pr, ban_run, unban_run |

## Agents (2)

| Name | Purpose |
|------|---------|
| `codegen-delegator` | Task delegation via MCP tools |
| `pr-reviewer` | PR review with logs analysis |

## Commands (5)

| Name | Purpose |
|------|---------|
| `codegen` | Delegate tasks |
| `cg-status` | Check run status |
| `cg-logs` | View logs |
| `cg-merge` | Merge PR |
| `cg-settings` | Manage settings |


# Codegen Bridge

AI-agent plugin and skills pack for delegating implementation plans to [Codegen](https://codegen.com) cloud agents.

## What it does

- **~54 MCP tools** — 49 manual tools + 5 auto-generated from OpenAPI spec + remote proxy
- **4 agent skills** — delegation, execution, monitoring, and PR management
- **2 Task agents** — codegen-delegator and pr-reviewer
- **5 slash commands** — `/codegen`, `/cg-status`, `/cg-logs`, `/cg-merge`, `/cg-settings`
- **Cross-platform packaging** — Claude, Cursor, Codex, Gemini CLI, and OpenCode install adapters

## Setup

1. Get API key from [codegen.com](https://codegen.com)
2. Set environment variables:

```bash
export CODEGEN_API_KEY="your-api-key"
export CODEGEN_ORG_ID="your-org-id"
```

## Installation By Platform

### Claude Code

Install local plugin:

```text
/install-plugin ~/.claude/plugins/codegen-bridge
```

### Cursor

Install plugin from repository:

```text
/add-plugin https://github.com/evgenygurin/codegen-bridge
```

Detailed guide: [docs/README.cursor.md](docs/README.cursor.md)

### Codex

Tell Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/evgenygurin/codegen-bridge/main/.codex/INSTALL.md
```

Detailed guide: [docs/README.codex.md](docs/README.codex.md)

### Gemini CLI

```bash
gemini extensions install https://github.com/evgenygurin/codegen-bridge
```

Update:

```bash
gemini extensions update codegen-bridge
```

Detailed guide: [docs/README.gemini.md](docs/README.gemini.md)

### OpenCode

Tell OpenCode:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/evgenygurin/codegen-bridge/main/.opencode/INSTALL.md
```

Detailed guide: [docs/README.opencode.md](docs/README.opencode.md)

### Verify Installation

Start a new agent session and ask for delegation, for example:
- `delegate this task to codegen`
- `show latest codegen runs`
- `summarize run <id>`

The assistant should use `codegen_*` tools and `codegen-bridge` skills.

## Usage with Superpowers

When `writing-plans` offers execution options, choose **"Codegen Remote"** to delegate to cloud agents. The `executing-via-codegen` skill will:

1. Parse the plan into tasks
2. Create one Codegen agent run per task
3. Monitor progress (polling every 30s)
4. Report results with PR links
5. Handle failures and pauses

## Manual MCP Tools

| Module | Tools | Purpose |
|--------|-------|---------|
| `agent` | `create_run`, `get_run`, `list_runs`, `resume_run`, `stop_run`, `ban_run`, `unban_run`, `remove_from_pr`, `get_logs`, `create_and_monitor`, `monitor_run_background`, `bulk_create_runs`, `report_run_result` | Agent run lifecycle, monitoring, bulk ops |
| `execution` | `start_execution`, `get_execution_context`, `get_agent_rules` | Multi-task execution plans |
| `pr` | `edit_pr`, `edit_pr_simple` | Pull request management |
| `setup` | `list_orgs`, `list_repos`, `list_users`, `get_user`, `get_current_user`, `get_organization_settings`, `get_mcp_providers`, `get_oauth_status`, `revoke_oauth`, `get_check_suite_settings`, `update_check_suite_settings`, `generate_setup_commands`, `list_models`, `get_repository_rules`, `configure_repository_rules`, `get_web_preview_guide`, `get_secrets_guide` | Organization, repo, user setup, rules, web preview, secrets |
| `integrations` | `get_integrations`, `get_webhook_config`, `set_webhook_config`, `delete_webhook_config`, `test_webhook`, `analyze_sandbox_logs`, `generate_slack_token`, `check_integration_health` | Webhooks, sandbox, Slack, health |
| `analytics` | `get_run_analytics` | Run statistics and metrics |
| `session` | `set_session_preference`, `get_session_preferences`, `clear_session_preferences` | Per-session state management |
| `settings` | `get_settings`, `update_settings` | Plugin settings management |
| `sampling` | `summarise_run`, `summarise_execution`, `generate_task_prompt`, `analyse_run_logs` | LLM sampling tools |

Auto-generated tools from the Codegen OpenAPI spec are also available at runtime via the OpenAPI provider.

## Skills

| Skill | Description |
|-------|-------------|
| `executing-via-codegen` | Orchestrate plan execution task-by-task via cloud agents |
| `codegen-delegation` | Delegate individual tasks to Codegen agents |
| `agent-monitoring` | Monitor and track agent run progress |
| `pr-management` | Manage pull requests created by agents |

## Agents

| Agent | Description |
|-------|-------------|
| `codegen-delegator` | Orchestrates multi-task plan execution via cloud agents |
| `pr-reviewer` | Reviews and manages pull requests from agent runs |

## Hooks

Hooks live in the root `hooks/` directory and run automatically:

- **PostToolUse** — auto-extracts run URLs after `codegen_create_run`, auto-formats status after `codegen_get_run`
- **Stop** — generates a session summary of all Codegen agent runs

## Plugin Structure

```text
codegen-bridge/
├── .codex/
│   └── INSTALL.md           # Codex bootstrap instructions
├── .claude-plugin/
│   ├── plugin.json          # Plugin metadata (name, version, keywords)
│   ├── settings.json        # Runtime settings (model, polling)
│   └── marketplace.json     # Marketplace listing
├── .cursor-plugin/
│   └── plugin.json          # Cursor plugin manifest
├── .opencode/
│   └── INSTALL.md           # OpenCode bootstrap instructions
├── GEMINI.md                # Gemini context entrypoint
├── gemini-extension.json    # Gemini extension manifest
├── hooks/                   # Claude/Cursor hooks
│   ├── hooks.json
│   ├── hooks-cursor.json
│   ├── session-start
│   └── scripts/
├── skills/                  # Agent skills (SKILL.md files)
├── agents/                  # Task agents (markdown definitions)
├── commands/                # Slash commands (markdown definitions)
├── bridge/                  # MCP server source code
│   ├── server.py            # FastMCP server + lifespan
│   ├── client.py            # Codegen API client
│   ├── tools/               # Manual tool implementations
│   ├── resources/           # MCP resources
│   ├── prompts/             # Prompt templates
│   ├── providers/           # Custom MCP providers
│   ├── middleware/          # 9-layer request middleware stack
│   ├── sampling/            # LLM sampling tools
│   ├── services/            # Business logic (RunService, ExecutionService)
│   ├── transforms/          # 4-stage transform chain
│   ├── telemetry/           # OpenTelemetry integration
│   └── ...
├── tests/                   # Test suite
└── pyproject.toml           # Python project config (v0.6.0)
```

## Development

```bash
cd ~/.claude/plugins/codegen-bridge
uv sync --dev
uv run pytest -v
uv run ruff check .
uv run mypy bridge/
```

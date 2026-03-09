# Codegen Bridge

Claude Code plugin for delegating implementation plans to [Codegen](https://codegen.com) cloud AI agents.

## What it does

- **~36 MCP tools** — 15 manual core tools + ~21 auto-generated from OpenAPI spec
- **4 agent skills** — delegation, execution, monitoring, and PR management
- **2 Task agents** — codegen-delegator and pr-reviewer
- **5 slash commands** — `/codegen`, `/cg-status`, `/cg-logs`, `/cg-merge`, `/cg-settings`
- **Hooks** — PostToolUse auto-formatting and Stop session summaries

## Setup

1. Get API key from [codegen.com](https://codegen.com)
2. Set environment variables:

```bash
export CODEGEN_API_KEY="your-api-key"
export CODEGEN_ORG_ID="your-org-id"
```

3. Install the plugin in Claude Code:

```text
/install-plugin ~/.claude/plugins/codegen-bridge
```

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
| `agent` | `codegen_create_run`, `codegen_get_run`, `codegen_list_runs`, `codegen_resume_run`, `codegen_get_logs` | Agent run lifecycle |
| `execution` | `codegen_start_execution`, `codegen_get_execution_context` | Multi-task execution plans |
| `pr` | PR management tools | Review, merge, manage pull requests |
| `setup` | `codegen_list_orgs`, `codegen_list_repos` | Organization and repository setup |
| `integrations` | Integration tools | Webhooks, sandbox, Slack connect |
| `settings` | Settings tools | Plugin settings management |

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
├── .claude-plugin/
│   ├── plugin.json          # Plugin metadata (name, version, keywords)
│   ├── settings.json        # Runtime settings (model, polling)
│   └── marketplace.json     # Marketplace listing
├── hooks/                   # Claude Code hooks (PostToolUse, Stop)
│   ├── hooks.json
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
│   ├── middleware/          # Request middleware stack
│   ├── sampling/            # LLM sampling tools
│   ├── transforms/          # Tool transform chain
│   └── ...
├── tests/                   # Test suite
└── pyproject.toml           # Python project config (v0.5.0)
```

## Development

```bash
cd ~/.claude/plugins/codegen-bridge
uv sync --dev
uv run pytest -v
uv run ruff check .
uv run mypy bridge/
```

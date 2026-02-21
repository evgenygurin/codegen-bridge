# Codegen Bridge

Claude Code plugin for delegating implementation plans to [Codegen](https://codegen.com) cloud AI agents.

## What it does

- **7 MCP tools** for Codegen API: create/monitor/resume agent runs, view logs
- **executing-via-codegen skill** — orchestrates plan execution task-by-task via cloud agents
- **Slash commands** — `/codegen`, `/cg-status`, `/cg-logs`

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

## MCP Tools

| Tool | Purpose |
|------|---------|
| `codegen_create_run` | Create agent run (prompt + repo + model) |
| `codegen_get_run` | Get run status + result + PRs |
| `codegen_list_runs` | List recent runs |
| `codegen_resume_run` | Resume blocked run |
| `codegen_get_logs` | View step-by-step agent logs |
| `codegen_list_orgs` | List organizations |
| `codegen_list_repos` | List repositories |

## Development

```bash
cd ~/.claude/plugins/codegen-bridge
uv sync --dev
uv run pytest -v
uv run ruff check .
```

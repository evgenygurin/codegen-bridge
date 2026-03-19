---
paths:
  - .claude-plugin/**
  - hooks/**
  - skills/**
  - commands/**
  - agents/**
---

# Plugin Structure

## Manifest (`plugin.json`)

```json
{
  "name": "codegen-bridge",
  "version": "0.6.0",
  "keywords": ["codegen", "agent", "execution", "delegation", "mcp"]
}
```

MCP server declared as inline `mcpServers` within `plugin.json` (uses `${CLAUDE_PLUGIN_ROOT}` variable for paths). Entry point: `uv run python -m bridge.server`.

## Settings (`settings.json`)

Default settings file at `.claude-plugin/settings.json`:

```json
{"default_model": null, "auto_monitor": true, "poll_interval": 30}
```

Managed via `codegen_get_settings` / `codegen_update_settings` tools.

## Hooks (`hooks/`)

Hook definitions in `hooks/hooks.json`. Scripts in `hooks/scripts/`.

### PostToolUse Hooks

| Matcher | Script | Purpose |
|---------|--------|---------|
| `mcp__.*codegen_create_run` | `post-create-run.sh` | Extract and display agent run URL after creation |
| `mcp__.*codegen_get_run` | `post-get-run.sh` | Format run status with PR links |

Matcher uses regex — `mcp__.*` prefix matches any MCP server name (the plugin name varies by installation).

**Hook script pattern:**
- Input: `$TOOL_RESULT` env var contains JSON (may be double-encoded)
- Parse with `jq`: first try direct, then try `fromjson` for double-encoded
- Output: plain text to stdout (shown to user as hook feedback)

### Stop Hook

Prompt-based hook that generates a session summary of all Codegen runs when the session ends.

**Critical:** Stop hook prompt MUST output raw JSON (no markdown, no code blocks). Format: `{"ok": true, "reason": "summary text"}`.

## Commands (`commands/`)

| File | Slash Command | Purpose |
|------|--------------|---------|
| `codegen.md` | `/codegen` | Create a new agent run |
| `cg-status.md` | `/cg-status` | Check status of agent runs |
| `cg-logs.md` | `/cg-logs` | View agent execution logs |
| `cg-merge.md` | `/cg-merge` | Merge PR from agent run |
| `cg-settings.md` | `/cg-settings` | Manage plugin settings |

## Agents (`agents/`)

Task tool agents for Claude Code's `/task` delegation:

| File | Agent | Purpose |
|------|-------|---------|
| `codegen-delegator.md` | `codegen-delegator` | Orchestrate plan execution via cloud agents |
| `pr-reviewer.md` | `pr-reviewer` | Review and manage PRs from agent runs |

## Skills (`skills/`)

Each skill is a directory with `SKILL.md`:

| Directory | Skill | Purpose |
|-----------|-------|---------|
| `codegen-delegation/` | Codegen delegation | Automated task delegation to agents |
| `agent-monitoring/` | Agent monitoring | Monitor running agent status |
| `executing-via-codegen/` | Plan execution | Execute implementation plans via agents |
| `pr-management/` | PR management | Manage PRs created by agents |

## Adding New Components

### New Hook
1. Add entry to `hooks/hooks.json` under appropriate event type
2. If command hook: create script in `hooks/scripts/`
3. Matcher: use `mcp__.*tool_name` regex pattern
4. Test: `uv run pytest tests/test_hooks.py -v`

### New Command
1. Create `commands/<name>.md` with slash command content
2. `CommandsProvider` auto-discovers it from the directory

### New Agent
1. Create `agents/<name>.md` with agent description
2. `AgentsProvider` auto-discovers it from the directory

### New Skill
1. Create `skills/<name>/SKILL.md`
2. `SkillsDirectoryProvider` auto-discovers it from the directory

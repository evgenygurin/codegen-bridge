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
  "version": "0.7.0",
  "keywords": ["codegen", "agent", "execution", "delegation", "mcp", "cloud", "review", "debugging"]
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

Cross-platform execution via `hooks/run-hook.cmd` polyglot wrapper (Windows CMD / Unix shell).

### SessionStart Hook

| Matcher | Script | Purpose |
|---------|--------|---------|
| `startup\|clear\|compact` | `session-start.sh` | Inject `using-codegen-bridge` meta-skill, detect superpowers plugin |

Invoked via `run-hook.cmd session-start`. Outputs JSON with `additionalContext` field containing the meta-skill content. Detects superpowers plugin presence and adjusts context messaging.

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

| Directory | Skill | User-Invocable | Purpose |
|-----------|-------|----------------|---------|
| `using-codegen-bridge/` | Meta-skill | No (SessionStart) | Skill map, decision tree, superpowers integration |
| `codegen-delegation/` | Delegation | No | Task delegation with prompt templates |
| `agent-monitoring/` | Monitoring | No | Monitor runs with verification gates |
| `executing-via-codegen/` | Plan execution | Yes | Execute plans via agents with two-stage review |
| `pr-management/` | PR management | No | Manage PRs created by agents |
| `bulk-delegation/` | Bulk delegation | Yes | Batch-delegate independent tasks |
| `run-analytics/` | Analytics | Yes | Analyze agent run performance |
| `debugging-failed-runs/` | Debugging | Yes | 4-phase systematic debugging for failed runs |
| `prompt-crafting/` | Prompt crafting | Yes | Guide for writing effective agent prompts |
| `reviewing-agent-output/` | Output review | Yes | Two-stage review (spec + quality) of agent work |

### Prompt Templates

Located in `skills/codegen-delegation/templates/`:

| Template | Purpose |
|----------|---------|
| `task-prompt-template.md` | Single task prompt structure |
| `multi-step-prompt-template.md` | Task within a plan (includes previous task context) |

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

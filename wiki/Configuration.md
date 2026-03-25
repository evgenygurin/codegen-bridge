# Configuration

Complete reference for all configuration options in Codegen Bridge.

## Environment Variables

### Required

| Variable | Type | Description |
|----------|------|-------------|
| `CODEGEN_API_KEY` | string | Bearer token from [codegen.com](https://codegen.com). Used for all API requests. |
| `CODEGEN_ORG_ID` | integer | Organization ID from your Codegen dashboard. |

### Optional

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CODEGEN_ALLOW_DANGEROUS_TOOLS` | boolean | `false` | Set `"true"` to bypass the dangerous tool guard middleware. Allows tools like `codegen_stop_run`, `codegen_ban_run`, etc. without interactive confirmation. |
| `CODEGEN_ENABLE_REMOTE_PROXY` | boolean | `false` | Set `"true"` to mount the remote Codegen MCP server proxy. Doubles tool surface with server-side tools under `remote_*` namespace. May slow shutdown. |

### Setting Environment Variables

**Shell export:**
```bash
export CODEGEN_API_KEY="your-api-key"
export CODEGEN_ORG_ID="your-org-id"
```

**From `.env` file:**
```bash
cp .env.example .env
# Edit .env with your values
```

**Example `.env`:**
```bash
CODEGEN_API_KEY=your-api-key-here
CODEGEN_ORG_ID=12345
# CODEGEN_ALLOW_DANGEROUS_TOOLS=true
# CODEGEN_ENABLE_REMOTE_PROXY=true
```

---

## Plugin Settings

Settings are stored in `.claude-plugin/settings.json` and managed via the `codegen_get_settings` / `codegen_update_settings` tools or the `/cg-settings` command.

### Default Settings

```json
{
  "default_model": null,
  "auto_monitor": true,
  "poll_interval": 30
}
```

### Setting Reference

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `default_model` | `string \| null` | `null` | — | LLM model for agent runs. `null` uses the organization default. |
| `auto_monitor` | `bool` | `true` | — | Automatically poll run status after creating a run. |
| `poll_interval` | `int` | `30` | 5-300 | Seconds between status polls when monitoring runs. |

### Managing Settings

```text
/cg-settings                              # View all settings
/cg-settings default_model claude-sonnet  # Set model
/cg-settings poll_interval 60             # Set poll interval
/cg-settings auto_monitor false           # Disable auto-monitoring
/cg-settings default_model null           # Reset to org default
```

---

## Plugin Manifest

**File:** `.claude-plugin/plugin.json`

```json
{
  "name": "codegen-bridge",
  "description": "Bridge to Codegen AI agent platform",
  "version": "0.7.0",
  "author": { "name": "Evgeny" },
  "license": "MIT",
  "keywords": ["codegen", "agent", "execution", "delegation", "mcp", "cloud", "review", "debugging"]
}
```

The MCP server is declared as inline `mcpServers` within `plugin.json`, using `${CLAUDE_PLUGIN_ROOT}` for paths. Entry point: `uv run python -m bridge.server`.

---

## MCP Configuration

**File:** `.mcp.json`

Standard MCP configuration file used by platforms that support it. Points to the bridge server.

---

## Platform-Specific Configuration

### Claude Code

Plugin installed via `/install-plugin`. Reads from `.claude-plugin/plugin.json`.

### Cursor

Plugin installed via `/add-plugin`. Reads from `.cursor-plugin/plugin.json`. Hooks from `hooks/hooks-cursor.json`.

### Gemini CLI

Extension manifest: `gemini-extension.json`. Context entrypoint: `GEMINI.md`.

### OpenAI Codex

Bootstrap instructions: `.codex/INSTALL.md`. Skills symlinked to `~/.agents/skills/`.

### OpenCode

Bootstrap instructions: `.opencode/INSTALL.md`. Skills symlinked to `~/.config/opencode/skills/`.

---

## Hooks Configuration

**File:** `hooks/hooks.json`

Hooks run automatically at specific lifecycle points.

### SessionStart Hook

| Matcher | Script | Purpose |
|---------|--------|---------|
| `startup\|clear\|compact` | `session-start.sh` | Inject meta-skill context, detect superpowers plugin |

### PostToolUse Hooks

| Matcher | Script | Purpose |
|---------|--------|---------|
| `mcp__.*codegen_create_run` | `post-create-run.sh` | Extract and display agent run URL after creation |
| `mcp__.*codegen_get_run` | `post-get-run.sh` | Format run status with PR links |

### Stop Hook

Prompt-based hook that generates a session summary of all Codegen runs when the session ends. Outputs raw JSON: `{"decision": "approve", "reason": "summary text"}`.

### Hook Script Pattern

- Input: `$TOOL_RESULT` env var contains JSON (may be double-encoded)
- Parse with `jq`: first try direct, then try `fromjson` for double-encoded
- Output: plain text to stdout

### Cross-Platform Execution

`hooks/run-hook.cmd` is a polyglot wrapper that works on both Windows CMD and Unix shells.

---

## Python Environment

| Setting | Value |
|---------|-------|
| Python version | 3.12 (pinned in `.python-version`) |
| Package manager | `uv` |
| Virtual env | Managed by `uv` |
| Entry point | `uv run python -m bridge.server` |

### Dependencies

**Core:**
| Package | Version | Purpose |
|---------|---------|---------|
| `fastmcp[tasks]` | >=3.0.0 | MCP server framework |
| `httpx` | >=0.27.0 | Async HTTP client |
| `pydantic` | >=2.0.0 | Data validation |
| `py-key-value-aio` | >=0.4.0 | Storage backend |

**Optional (telemetry):**
| Package | Purpose |
|---------|---------|
| `opentelemetry-sdk` | Tracing SDK |
| `opentelemetry-exporter-otlp` | OTLP exporter |

---

## See Also

- **[[Getting-Started]]** — Installation guide
- **[[Architecture]]** — How configuration flows through the system
- **[[Development-Guide]]** — Development environment setup

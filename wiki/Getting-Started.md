# Getting Started

This guide covers installation, setup, and your first interaction with Codegen Bridge across all supported platforms.

## Prerequisites

1. **Codegen Account** — Sign up at [codegen.com](https://codegen.com)
2. **API Key** — Generate from your Codegen dashboard
3. **Organization ID** — Found in your Codegen organization settings (integer)
4. **Python 3.12+** — Required for running the MCP server
5. **uv** — Python package manager ([install guide](https://docs.astral.sh/uv/))

## Environment Variables

Set these before launching any AI assistant:

```bash
export CODEGEN_API_KEY="your-api-key"
export CODEGEN_ORG_ID="your-org-id"
```

You can also create a `.env` file from the provided example:

```bash
cp .env.example .env
# Edit .env with your values
```

| Variable | Required | Description |
|----------|----------|-------------|
| `CODEGEN_API_KEY` | Yes | Bearer token from codegen.com |
| `CODEGEN_ORG_ID` | Yes | Organization ID (integer) |
| `CODEGEN_ALLOW_DANGEROUS_TOOLS` | No | Set `"true"` to bypass dangerous tool guard |
| `CODEGEN_ENABLE_REMOTE_PROXY` | No | Set `"true"` to mount remote Codegen MCP server proxy |

## Installation by Platform

### Claude Code

Install as a local plugin:

```text
/install-plugin ~/.claude/plugins/codegen-bridge
```

The plugin reads its manifest from `.claude-plugin/plugin.json` and starts the MCP server via `uv run python -m bridge.server`.

### Cursor

Install from the repository:

```text
/add-plugin https://github.com/evgenygurin/codegen-bridge
```

Cursor reads plugin metadata from `.cursor-plugin/plugin.json`. What gets loaded:
- Skills from `./skills/`
- Agents from `./agents/`
- Commands from `./commands/`
- Session hook from `./hooks/hooks-cursor.json`

To update, re-run the same `/add-plugin` command.

### OpenAI Codex

Tell Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/evgenygurin/codegen-bridge/main/.codex/INSTALL.md
```

Or install manually:

```bash
# Clone
git clone https://github.com/evgenygurin/codegen-bridge.git ~/.codex/codegen-bridge

# Expose skills
mkdir -p ~/.agents/skills
ln -s ~/.codex/codegen-bridge/skills ~/.agents/skills/codegen-bridge

# Restart Codex — it discovers skills on startup
```

To update: `cd ~/.codex/codegen-bridge && git pull`

### Gemini CLI

```bash
gemini extensions install https://github.com/evgenygurin/codegen-bridge
```

Gemini reads `gemini-extension.json` and `GEMINI.md` for context. To update:

```bash
gemini extensions update codegen-bridge
```

### OpenCode

Tell OpenCode:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/evgenygurin/codegen-bridge/main/.opencode/INSTALL.md
```

Or install manually:

```bash
# Clone
git clone https://github.com/evgenygurin/codegen-bridge.git ~/.config/opencode/codegen-bridge

# Symlink skills
mkdir -p ~/.config/opencode/skills
rm -rf ~/.config/opencode/skills/codegen-bridge
ln -s ~/.config/opencode/codegen-bridge/skills ~/.config/opencode/skills/codegen-bridge

# Restart OpenCode
```

To update: `cd ~/.config/opencode/codegen-bridge && git pull`

## Verifying Installation

Start a new AI assistant session and try any of these:

- `delegate this task to codegen`
- `show latest codegen runs`
- `summarize run <id>`
- `/codegen <task description>`
- `/cg-status`

The assistant should use `codegen_*` tools and `codegen-bridge` skills.

## Your First Delegation

### 1. Simple Task Delegation

Ask your assistant:

```text
Use codegen to add input validation to the signup form in my project
```

The assistant will:
1. Detect the intent to delegate
2. Compose a prompt using the `codegen-delegation` skill
3. Call `codegen_create_run` to create an agent run
4. Report the run ID and web URL

### 2. Check Status

```text
/cg-status
```

Or ask: "What's the status of my codegen runs?"

### 3. View Logs

```text
/cg-logs
```

### 4. Review Results

When the agent completes, it creates a PR. The assistant will:
- Show the PR link
- Summarize what was changed
- Suggest reviewing and merging

## Usage with Superpowers Plugin

When the [superpowers](https://github.com/superpowers) plugin is also installed, you get a combined workflow:

1. **superpowers:brainstorming** — design the feature
2. **superpowers:writing-plans** — create the implementation plan
3. **codegen-bridge:executing-via-codegen** — execute via cloud agents
4. **codegen-bridge:reviewing-agent-output** — review agent PRs
5. **superpowers:finishing-a-development-branch** — merge

When `writing-plans` offers execution options, choose **"Codegen Remote"** to delegate to cloud agents.

## Next Steps

- **[[Tools-Reference]]** — Explore all available MCP tools
- **[[Skills-Guide]]** — Learn about the skill system
- **[[Commands-Reference]]** — Quick-access slash commands
- **[[Architecture]]** — Understand how it all fits together

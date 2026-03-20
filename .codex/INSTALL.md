# Installing Codegen Bridge for Codex

## Prerequisites

- OpenAI Codex CLI installed
- Git installed
- Codegen credentials (`CODEGEN_API_KEY`, `CODEGEN_ORG_ID`)

## Installation Steps

### 1. Clone the repository

```bash
git clone https://github.com/evgenygurin/codegen-bridge.git ~/.codex/codegen-bridge
```

### 2. Symlink Codegen Bridge skills

Codex discovers skills from `~/.agents/skills/`.

```bash
mkdir -p ~/.agents/skills
ln -s ~/.codex/codegen-bridge/skills ~/.agents/skills/codegen-bridge
```

### 3. Restart Codex

Start a new Codex session so skills are discovered.

### 4. Use Codegen Bridge tools

To use Codegen MCP tools, work in a project that contains `.mcp.json` configured for `codegen-bridge` (this repository already includes one).

## Verify

Ask Codex:

```text
Use codegen-bridge skills and delegate a task to a Codegen cloud agent.
```

The session should discover `codegen-bridge` skills and call `codegen_*` tools.

## Update

```bash
cd ~/.codex/codegen-bridge
git pull
```

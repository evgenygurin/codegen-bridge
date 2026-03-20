# Installing Codegen Bridge for OpenCode

## Prerequisites

- OpenCode installed
- Git installed
- Codegen credentials (`CODEGEN_API_KEY`, `CODEGEN_ORG_ID`)

## Installation Steps

### 1. Clone the repository

```bash
git clone https://github.com/evgenygurin/codegen-bridge.git ~/.config/opencode/codegen-bridge
```

### 2. Symlink skills

```bash
mkdir -p ~/.config/opencode/skills
rm -rf ~/.config/opencode/skills/codegen-bridge
ln -s ~/.config/opencode/codegen-bridge/skills ~/.config/opencode/skills/codegen-bridge
```

### 3. Restart OpenCode

Start a new OpenCode session so skill discovery refreshes.

### 4. Configure MCP tools

Use this repository's `.mcp.json` as a template for your OpenCode MCP server config.

## Verify

Ask OpenCode:

```text
Use codegen-bridge and delegate this feature to a Codegen cloud agent.
```

## Update

```bash
cd ~/.config/opencode/codegen-bridge
git pull
```

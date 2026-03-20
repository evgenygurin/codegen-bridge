# Codegen Bridge for OpenCode

Guide for using Codegen Bridge with OpenCode.

## Quick Install

Tell OpenCode:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/evgenygurin/codegen-bridge/main/.opencode/INSTALL.md
```

## Manual Installation

### 1. Clone

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

OpenCode discovers skills on startup.

### 4. Configure MCP

Use `.mcp.json` from this repository as the base for your MCP setup so OpenCode can call `codegen_*` tools.

## Verify

Ask OpenCode:

```text
Use codegen-bridge to execute this plan through Codegen cloud agents.
```

## Update

```bash
cd ~/.config/opencode/codegen-bridge
git pull
```

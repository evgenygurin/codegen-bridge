# Codegen Bridge for Codex

Guide for using Codegen Bridge with OpenAI Codex.

## Quick Install

Tell Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/evgenygurin/codegen-bridge/main/.codex/INSTALL.md
```

## Manual Installation

### 1. Clone

```bash
git clone https://github.com/evgenygurin/codegen-bridge.git ~/.codex/codegen-bridge
```

### 2. Expose skills to Codex

```bash
mkdir -p ~/.agents/skills
ln -s ~/.codex/codegen-bridge/skills ~/.agents/skills/codegen-bridge
```

### 3. Restart Codex

Codex discovers skills on startup.

### 4. Configure MCP

To call `codegen_*` tools, run Codex in a workspace with a matching `.mcp.json` entry.
This repository already includes one at the root.

## Verify

Try:

```text
Use codegen-bridge to execute this plan remotely on Codegen agents.
```

Expected behavior:
- `using-codegen-bridge` skill gets loaded.
- `codegen_create_run` / `codegen_get_run` tools are used.

## Update

```bash
cd ~/.codex/codegen-bridge
git pull
```

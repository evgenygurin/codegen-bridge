# Codegen Bridge for Cursor

Guide for using Codegen Bridge with Cursor Agent mode.

## Install

In Cursor Agent chat:

```text
/add-plugin https://github.com/evgenygurin/codegen-bridge
```

Cursor reads plugin metadata from `.cursor-plugin/plugin.json`.

## What gets loaded

- Skills from `./skills/`
- Agents from `./agents/`
- Commands from `./commands/`
- Session hook from `./hooks/hooks-cursor.json`

## Required environment variables

Set before starting Cursor:

```bash
export CODEGEN_API_KEY="your-api-key"
export CODEGEN_ORG_ID="your-org-id"
```

## Verify

Ask Cursor:

```text
Use codegen-bridge and create a Codegen run for this task.
```

Expected behavior:
- Session starts with Codegen Bridge context.
- Cursor can use `codegen_*` MCP tools.

## Update

Reinstall from the repository URL to refresh to the latest version:

```text
/add-plugin https://github.com/evgenygurin/codegen-bridge
```

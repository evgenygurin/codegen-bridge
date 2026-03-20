# Codegen Bridge for Gemini CLI

Guide for using Codegen Bridge with Gemini CLI extensions.

## Install

```bash
gemini extensions install https://github.com/evgenygurin/codegen-bridge
```

Gemini reads:
- `gemini-extension.json`
- `GEMINI.md` (context entrypoint)

## Required environment variables

```bash
export CODEGEN_API_KEY="your-api-key"
export CODEGEN_ORG_ID="your-org-id"
```

## Verify

Start a new Gemini session and ask:

```text
Use codegen-bridge to delegate this implementation task to a cloud agent.
```

Expected behavior:
- Gemini receives context from `GEMINI.md`.
- Gemini follows `skills/using-codegen-bridge/SKILL.md`.
- Gemini invokes `codegen_*` tools through MCP configuration.

## Update

```bash
gemini extensions update codegen-bridge
```

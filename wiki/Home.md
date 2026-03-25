# Codegen Bridge Wiki

Welcome to the **Codegen Bridge** wiki — the comprehensive documentation for the Claude Code plugin that bridges to the [Codegen](https://codegen.com) cloud AI agent platform.

## What is Codegen Bridge?

Codegen Bridge is a hybrid MCP (Model Context Protocol) server plugin that enables AI coding assistants to delegate tasks to cloud-based AI agents on the Codegen platform. Instead of making changes locally, tasks run in isolated cloud sandboxes and produce pull requests on GitHub.

**Current version:** v0.7.0

### Key Capabilities

| Feature | Count | Description |
|---------|-------|-------------|
| **MCP Tools** | 51 | 49 manual + 2 unique auto-generated from OpenAPI spec |
| **Skills** | 10 | Delegation, execution, monitoring, debugging, prompt crafting, review, analytics, bulk ops, PR management, meta-skill |
| **Agents** | 2 | `codegen-delegator` and `pr-reviewer` task agents |
| **Slash Commands** | 5 | `/codegen`, `/cg-status`, `/cg-logs`, `/cg-merge`, `/cg-settings` |
| **Resources** | 33 | Config, platform docs, skills, commands, agents |
| **Prompts** | 8 | Workflow prompt templates |
| **Middleware** | 9 layers | Error handling, auth, rate limiting, caching, telemetry |
| **Providers** | 4+ | OpenAPI, Skills, Commands, Agents, optional Remote proxy |

### Supported Platforms

- **Claude Code** — native plugin support
- **Cursor** — plugin via `.cursor-plugin/`
- **OpenAI Codex** — bootstrap via `.codex/INSTALL.md`
- **Gemini CLI** — extension via `gemini-extension.json`
- **OpenCode** — bootstrap via `.opencode/INSTALL.md`

## Wiki Pages

### Getting Started
- **[[Getting-Started]]** — Installation, setup, and first run for all supported platforms
- **[[Configuration]]** — Environment variables, settings, and plugin configuration

### User Guide
- **[[Tools-Reference]]** — Complete reference for all 51 MCP tools
- **[[Skills-Guide]]** — Detailed guide to all 10 agent skills
- **[[Commands-Reference]]** — Slash commands for quick actions
- **[[Agents]]** — Task agents for delegation and PR review

### Architecture & Internals
- **[[Architecture]]** — System architecture, data flow, and module map
- **[[Middleware-and-Transforms]]** — 9-layer middleware stack and 4-stage transform chain
- **[[Providers]]** — OpenAPI, Skills, Commands, Agents, and Remote proxy providers

### Development
- **[[Development-Guide]]** — Contributing, testing, adding new tools, and coding patterns
- **[[Changelog]]** — Version history and release notes

## Quick Start

```bash
# 1. Set environment variables
export CODEGEN_API_KEY="your-api-key"
export CODEGEN_ORG_ID="your-org-id"

# 2. Install as Claude Code plugin
/install-plugin ~/.claude/plugins/codegen-bridge

# 3. Start using it
# In a Claude Code session:
# - "delegate this task to codegen"
# - "show latest codegen runs"
# - /codegen <task description>
```

## How It Works

```
User Request → Claude Code → MCP Protocol → Codegen Bridge Server
                                                    │
                                              ┌─────┴─────┐
                                              ▼           ▼
                                         Middleware   Transforms
                                         (9 layers)  (4 stages)
                                              │           │
                                              └─────┬─────┘
                                                    ▼
                                              Tool Functions
                                                    │
                                              Service Layer
                                                    │
                                              Codegen REST API
                                                    │
                                              Cloud Agent Sandbox
                                                    │
                                              GitHub Pull Request
```

## License

MIT License — see the repository root for details.

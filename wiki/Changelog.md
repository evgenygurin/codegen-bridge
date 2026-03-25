# Changelog

All notable changes to Codegen Bridge.

---

## [0.7.0] — Latest

### Added
- **4 new skills:** `debugging-failed-runs`, `prompt-crafting`, `reviewing-agent-output`, `using-codegen-bridge` (meta-skill)
- **SessionStart hook** with superpowers detection
- **Cross-platform hook wrapper** (`run-hook.cmd` polyglot)
- **Prompt templates** in `skills/codegen-delegation/templates/`
- Total skills: 10 (up from 6)

---

## [0.6.0]

### Added
- **Bulk operations:** `codegen_bulk_create_runs` — create multiple agent runs in a single batch call
- **Background monitoring:** `codegen_monitor_run_background` — poll an existing run via FastMCP background tasks
- **Analytics:** `codegen_get_run_analytics` — aggregate statistics (totals, success rate, status distribution)
- **Integration health:** `codegen_check_integration_health` — verify webhook/integration connectivity
- **Session state:** 3 new tools (`set_session_preference`, `get_session_preferences`, `clear_session_preferences`) for per-session key/value storage
- **Model discovery:** `codegen_list_models` — list available AI models and providers
- **Remote proxy:** Mount hosted Codegen MCP server under `namespace="remote"` for server-side tools
- **Rate budget:** `OutboundRateBudget` (token-bucket) throttles outgoing API calls to prevent 429s
- **Annotations:** 6 `ToolAnnotations` presets on every manual tool
- **Storage TTL:** TTL support for `FileStorage` and `MemoryStorage`
- **Enhanced elicitation:** Pydantic schema support in `confirm_with_schema`, multi-select

### Changed
- **Service layer:** Business logic extracted into `RunService` and `ExecutionService`; tools are thin wrappers
- **HTTP client:** Unified all API calls through `_request_json` method
- **Transforms fully configured:** Namespace, Visibility, and VersionFilter transforms active
- **OpenTelemetry complete:** Full tracing and metrics pipeline operational
- **Agent tools decomposed:** `tools/agent/` split into 7 submodules
- **Setup tools decomposed:** `tools/setup/` split into 5 submodules
- **DI providers:** 7 → 8 (added `get_session_state`)
- **Tool count:** 41 → 49 manual tools

---

## [0.5.0]

### Added
- Service layer (`bridge/services/`) with `RunService` and `ExecutionService`
- `ToolAnnotations` presets in `bridge/annotations.py`
- Agent tool decomposition into SOLID submodules
- Setup tool decomposition into SOLID submodules
- `codegen_report_run_result` and `codegen_create_and_monitor` tools
- `codegen_edit_pr_simple` tool
- Setup tools: `get_current_user`, `get_mcp_providers`, `get_oauth_status`, `revoke_oauth`
- 8 MCP resources (3 config + 2 platform + 3 parameterized templates)
- Platform resources: integrations guide and CLI/SDK docs

### Changed
- OpenAPI auto-generated tools reduced from ~21 to 5 (rest covered by manual tools)
- DI providers expanded (5 → 7)
- Tool count: 39 → 41
- Critical safety fix: split `codegen_get_run` into pure-read + explicit-mutation `codegen_report_run_result`
- Tool call caching disabled by default (prevents stale polling data)

---

## [0.4.0]

### Added
- FastMCP 3.x server with lifespan and DI
- 39 manual tools across 6 modules + 4 sampling
- 9-layer middleware stack
- 4-stage transform chain
- 4 providers (OpenAPI, Skills, Commands, Agents)
- Resources, prompts, and sampling via `ctx.sample()`
- Plugin structure: hooks, commands, agents, skills
- OpenTelemetry integration
- Storage backends (Memory, File)
- Elicitation helpers for dangerous tool confirmation

---

## Version Statistics

| Metric | v0.4.0 | v0.5.0 | v0.6.0 | v0.7.0 |
|--------|--------|--------|--------|--------|
| Manual tools | 39 | 41 | 49 | 49 |
| Auto-generated (unique) | ~21 | 2 | 2 | 2 |
| Total tools | ~60 | 43 | 51 | 51 |
| Skills | 4 | 4 | 6 | 10 |
| Resources | 3 | 8 | 33 | 33 |
| Services | 0 | 2 | 2 | 2 |
| Middleware layers | 9 | 9 | 9 | 9 |
| DI providers | 5 | 7 | 8 | 8 |
| Test count | — | — | — | 1382 |

---

## See Also

- **[[Home]]** — Wiki home page
- **[[Architecture]]** — Current architecture
- **[[Tools-Reference]]** — Complete tool list

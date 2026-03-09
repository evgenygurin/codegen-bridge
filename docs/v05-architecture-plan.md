# v0.5 Architecture Plan — As-Built Record

> Based on [MCP Surface Inventory](./mcp-surface-inventory.md) audit.
> Phases 0–5 **completed**. Phase 6 (serialization cleanup) deferred. P0 safety hotfix applied post-completion.

---

## Dependency Graph (completed)

```text
Phase 0: Semantic Fixes ✅ ──────────────────────┐
  (split get_run, re-tag misleading tools)        │
                                                  ▼
Phase 1: Service Layer ✅ ────────────────────────┐
  (RunService, ExecutionService)                  │
                                                  ▼
Phase 2: ToolAnnotations ✅ ──┐   Phase 3: Outbound Rate Budget ✅
  (6 presets applied)         │     (token-bucket in CodegenClient)
                              │              │
                              ▼              ▼
                   Phase 4: Resource Templates ✅
                     (3 parameterized templates)
                              │
                              ▼
                   Phase 5: Workflow Composition ✅
                     (codegen_create_and_monitor)
                              │
                              ▼
                   Phase 6: Serialization Cleanup
                     (deferred — partial via RunService)
                              │
                              ▼
                   P0: Safety Hotfix ✅
                     (cache, dangerous tools, auto-gen trim)
```

---

## Phase 0: Semantic Fixes ✅

**Commit:** `refactor(tools): split get_run read/write paths`

### 0.1 Split `codegen_get_run` ✅

Split into two tools in `bridge/tools/agent/queries.py`:

| Tool | Annotation | What it does |
|------|-----------|-------------|
| `codegen_get_run` | `READ_ONLY` | Pure read via `RunService.get_run()`. No writes. |
| `codegen_report_run_result` | `MUTATES` | Takes `run_id` + `execution_id`, writes TaskReport via `RunService.report_run_result()`, advances task index. |

### 0.2 Re-tag Misleading Tools ✅

Tags added to tools whose names don't reflect their actual behavior:

| Tool | Added Tag | Why |
|------|-----------|-----|
| `codegen_generate_setup_commands` | `creates-agent-run` | Actually creates a cloud agent run |
| `codegen_analyze_sandbox_logs` | `creates-agent-run` | Actually creates a cloud agent run |
| `codegen_test_webhook` | `external-request` | Sends real HTTP POST to external URL |

---

## Phase 1: Service Layer Extraction ✅

**Commit:** `refactor(arch): extract service layer from tools`

### 1.1 Services Created

```text
bridge/services/
├── __init__.py
├── runs.py          # RunService
└── execution.py     # ExecutionService
```

**Deviation from plan:** Only `RunService` and `ExecutionService` were extracted. `IntegrationService` and `SettingsService` deferred — those tools are simpler and direct `client.xyz()` calls are acceptable for now.

### 1.2 RunService (`bridge/services/runs.py`)

```python
class RunService:
    def __init__(self, client, registry, repo_cache, log_parser) -> None: ...

    async def get_run(self, run_id: int) -> dict           # pure read
    async def list_runs(self, ...) -> dict                  # paginated list
    async def report_run_result(self, ...) -> dict          # explicit mutation
    async def create_run(self, ...) -> dict                 # create + serialize
    async def detect_repo(self) -> int | None               # repo auto-detection
    async def get_logs(self, run_id: int) -> dict           # log retrieval
```

### 1.3 DI Providers

Added to `bridge/dependencies.py`:
- `get_run_service(ctx) -> RunService`
- `get_execution_service(ctx) -> ExecutionService`

Tools use: `svc: RunService = Depends(get_run_service)  # type: ignore[arg-type]`

### 1.4 Serialization Consolidation (partial)

`RunService` consolidates run serialization that was previously duplicated between `helpers/formatting.py` inline dict building in `queries.py` and `sampling/tools.py`. The `format_run()` helper is still used by sampling tools — full consolidation deferred to Phase 6.

---

## Phase 2: ToolAnnotations ✅

**Commit:** `feat(mcp): add ToolAnnotations to all tools`

### 2.1 Annotations Module

Created `bridge/annotations.py` with 6 reusable presets:

| Preset | RO | DH | IH | OW | Usage |
|--------|----|----|----|----|-------|
| `READ_ONLY` | T | F | T | T | External API reads |
| `READ_ONLY_LOCAL` | T | F | T | F | Local state reads |
| `CREATES` | F | F | F | T | New external resources |
| `MUTATES` | F | F | T | T | Idempotent updates |
| `MUTATES_LOCAL` | F | F | T | F | Local-only updates |
| `DESTRUCTIVE` | F | T | F | T | Irreversible mutations |

### 2.2 Application

All 41 manual tools + 4 sampling tools have explicit `annotations=` in their `@mcp.tool()` decorators.

**Deviation from plan:** Instead of individual `ToolAnnotations(...)` per tool, centralized presets reduce boilerplate. Only 6 presets needed — the plan's per-tool annotation map collapsed cleanly into these categories.

---

## Phase 3: Outbound Rate Budget ✅

**Commit:** `feat(client): add outbound rate budget (token-bucket throttling)`

### 3.1 Implementation

Token-bucket rate limiter added to `CodegenClient`:

```python
class OutboundRateBudget:
    max_tokens: int = 60       # burst capacity
    refill_rate: float = 1.0   # tokens/second (60 req/min sustained)
```

Integrated into `CodegenClient._request()` — all outbound API calls pass through the budget.

### 3.2 Configuration

Configurable via `bridge/settings.py` constants. Default: 60 req/min sustained, 60 burst.

---

## Phase 4: Resource Templates ✅

**Commit:** `feat(resources): add parameterized resource templates`

### 4.1 Templates Created (`bridge/resources/templates.py`)

| Resource URI | Backed By | Purpose |
|-------------|-----------|---------|
| `codegen://runs/{run_id}` | `RunService.get_run()` | Run status, result, summary, PRs |
| `codegen://runs/{run_id}/logs` | `RunService.get_logs()` | Step-by-step execution logs |
| `codegen://execution/{execution_id}` | `ExecutionService.get_execution_context()` | Execution context state |

### 4.2 Additional Resources (`bridge/resources/platform.py`)

Two static platform documentation resources added (not in original plan):

| Resource URI | Content |
|-------------|---------|
| `codegen://platform/integrations-guide` | Integration reference (GitHub, Linear, Slack, Jira, Figma, Notion, Sentry) |
| `codegen://platform/cli-sdk` | CLI commands, SDK quick-start, environment variables |

**Total resources: 8** (3 config + 2 platform + 3 templates), up from 3 in v0.4.

---

## Phase 5: Workflow Composition ✅

**Commit:** `feat(tools): add create-and-monitor workflow composition tool`

### 5.1 `codegen_create_and_monitor` (`bridge/tools/agent/workflow.py`)

Fire-and-wait workflow combining `create_run` + polling loop:

- Annotation: `CREATES`
- Tags: `execution, workflow`
- Runs as background task via `task=MONITOR_TASK`
- Polling uses `RunService.get_run()` (pure read — no execution-context side effects)
- Exponential backoff: doubles every 10 polls, capped at 4x base interval
- Default: `max_polls=60`, `poll_interval=10.0s`
- Elicits model selection + confirmation when `confirmed=False`
- Rate-budget-controlled via `CodegenClient`

---

## Phase 6: Serialization Cleanup — DEFERRED

**Reason:** Partial consolidation already achieved via `RunService` in Phase 1. The remaining duplication points are:

| Location | Status |
|----------|--------|
| `helpers/formatting.py:format_run()` | Still used by sampling tools |
| `helpers/formatting.py:format_run_basic()` | Candidate for removal |
| `tools/setup/users.py:_user_to_dict()` | Low priority — simple helper |
| `sampling/tools.py` inline formatting | Uses `format_run()` from helpers |

Full consolidation deferred until service extraction is complete for all tool modules (PR-2/PR-3 in audit plan).

---

## P0: Safety Hotfix ✅

**Commit:** `fix(safety): close three P0 security gaps in middleware and OpenAPI layer`

Applied post-Phase-5 based on architecture audit. Three fixes:

### P0-A: Tool Call Caching Disabled by Default

`ResponseCachingMiddleware` now passes `CallToolSettings(enabled=config.caching.tool_call_enabled)`.

**Default: `tool_call_enabled=False`** — prevents stale cached data from being served for polling tools.

Changed in: `bridge/middleware/config.py`, `bridge/middleware/stack.py`

### P0-B: Dangerous Tool List Expanded

`DEFAULT_DANGEROUS_TOOLS` expanded from 4 to 6 names:

```python
frozenset({
    "codegen_stop_run",
    "codegen_edit_pr",
    "codegen_edit_pr_simple",
    "codegen_delete_webhook_config",
    "codegen_set_webhook_config",
    "codegen_revoke_oauth_token",
})
```

All 6 names now match actual tool function names (3 stale names fixed post-P0).

### P0-C: Auto-Generated Tools Trimmed

`TOOL_NAMES` reduced from ~21 to 5 entries. `build_route_maps()` reduced from 16 to 5 routes (4 tool + 1 exclude). Eliminates naming conflicts between auto-generated and manual tools.

---

## Implementation Checklist

```text
[x] Phase 0.1 — Split codegen_get_run → get_run + report_run_result
[x] Phase 0.2 — Add tags to misleading tools
[x] Phase 0.3 — Tests green, lint clean
[x] ─── COMMIT: "refactor(tools): split get_run read/write paths" ───

[x] Phase 1.1 — Create bridge/services/ with RunService, ExecutionService
[x] Phase 1.2 — Migrate agent tools to use RunService
[x] Phase 1.3 — Add DI providers for services
[ ] Phase 1.4 — Migrate remaining tools to services (deferred to PR-2/PR-3)
[x] ─── COMMIT: "refactor(arch): extract service layer from tools" ───

[x] Phase 2.1 — Create annotations module with 6 presets
[x] Phase 2.2 — Apply annotations to all 41 manual tools
[x] Phase 2.3 — Apply annotations to 4 sampling tools
[x] ─── COMMIT: "feat(mcp): add ToolAnnotations to all tools" ───

[x] Phase 3.1 — Implement OutboundRateBudget
[x] Phase 3.2 — Integrate into CodegenClient._request()
[x] Phase 3.3 — Add configuration
[x] ─── COMMIT: "feat(client): add outbound rate budget" ───

[x] Phase 4.1 — Add runs/{run_id} resource template
[x] Phase 4.2 — Add runs/{run_id}/logs resource template
[x] Phase 4.3 — Add execution/{id} resource template
[x] Phase 4.4 — Add platform documentation resources (bonus)
[x] ─── COMMIT: "feat(resources): add dynamic resource templates" ───

[x] Phase 5.1 — Implement codegen_create_and_monitor
[x] Phase 5.2 — Verify rate budget integration
[x] ─── COMMIT: "feat(tools): add create-and-monitor workflow" ───

[ ] Phase 6.1 — Consolidate serialization into Data classes (deferred)
[ ] Phase 6.2 — Remove duplication points (deferred)

[x] P0-A — Disable tool call caching by default
[x] P0-B — Expand dangerous tools list (4→6)
[x] P0-C — Trim auto-generated tools (~21→5)
[x] ─── COMMIT: "fix(safety): close three P0 security gaps" ───

[ ] Update CLAUDE.md with new architecture
[ ] Update plugin version to 0.5.0
[ ] ─── COMMIT: "chore: bump to v0.5.0" ───
```

---

## What Remains for Future PRs

| Item | Original Phase | Why Deferred | Target |
|------|---------------|-------------|--------|
| Service extraction for PR, integrations, setup tools | Phase 1.4 | Direct `client.xyz()` is acceptable for simple tools | Deferred |
| Full serialization cleanup | Phase 6 | Partial consolidation via RunService sufficient | PR-7 |
| ~~Fix dangerous tool name mismatches~~ | P0 follow-up | **DONE** — 3 stale names corrected | ✅ |
| Rename misleading tools | Not planned | Would break existing sessions | Consider for v0.6 |
| Workflow engine + policies | Audit plan | Not in original v0.5 scope | PR-4/PR-5 |
| Observability cleanup | Audit plan | Not in original v0.5 scope | PR-7 |

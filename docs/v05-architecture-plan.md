# v0.5 Architecture Plan — Dependency-Ordered Phases

> Based on [MCP Surface Inventory](./mcp-surface-inventory.md) audit of all 39 manual tools.
> Each phase unlocks the next. Skipping or reordering phases produces incorrect metadata.

---

## Dependency Graph

```text
Phase 0: Semantic Fixes ──────────────────────────────┐
  (split get_run, rename misleading tools)             │
                                                       ▼
Phase 1: Service Layer ────────────────────────────────┐
  (extract shared logic from tools)                    │
                                                       ▼
Phase 2: ToolAnnotations ──────┐   Phase 3: Outbound Rate Budget
  (apply correct hints)        │     (throttle API calls out)
                               │              │
                               ▼              ▼
                    Phase 4: Resource Templates
                      (backed by services)
                               │
                               ▼
                    Phase 5: Workflow Composition
                      (create-and-monitor, orchestration)
                               │
                               ▼
                    Phase 6: Serialization Cleanup
                      (consolidate 6 duplication points)
```

---

## Phase 0: Semantic Fixes

**Why first:** Every subsequent phase (annotations, resources, workflows) depends on tools having
correct, unambiguous semantics. Building on wrong semantics = wrong metadata that misleads MCP clients.

**Duration:** ~2 hours. Zero API changes. Pure refactor.

### 0.1 Split `codegen_get_run`

Current `codegen_get_run` (in `bridge/tools/agent/queries.py`) does two things:
1. **Read:** Fetch run from API, format, return
2. **Mutate:** When `execution_id` provided AND status is terminal → write TaskReport to ContextRegistry, advance task index

**Action:** Split into two tools:

| New Tool | Type | What it does |
|----------|------|-------------|
| `codegen_get_run` | Read-only | Fetch + format. No `execution_id` param. No writes. |
| `codegen_report_run_result` | Mutation | Takes `run_id` + `execution_id`, writes TaskReport, advances index. Explicit name = explicit intent. |

**Files to change:**
- `bridge/tools/agent/queries.py` — extract mutation logic into new function
- `bridge/tools/agent/__init__.py` — export new tool
- `tests/tools/test_agent.py` — split tests accordingly

### 0.2 Re-tag Misleading Tools

Three tools create agent runs but their names don't indicate it:

| Tool | Current Tag | Action |
|------|-------------|--------|
| `codegen_generate_setup_commands` | `setup` | Add tag `creates-agent-run`. Add `openWorldHint` annotation (Phase 2). |
| `codegen_analyze_sandbox_logs` | `integrations` | Add tag `creates-agent-run`. Add `openWorldHint` annotation (Phase 2). |
| `codegen_test_webhook` | `integrations` | Add tag `external-request`. Add `openWorldHint` annotation (Phase 2). |

**No renaming** — renaming breaks existing Claude Code sessions that reference these tools.
Tags + annotations are the correct MCP mechanism for semantic metadata.

### 0.3 Acceptance Criteria

- [ ] `codegen_get_run` has zero writes to ContextRegistry
- [ ] `codegen_report_run_result` is the only place that writes TaskReport
- [ ] All tests pass: `uv run pytest -v`
- [ ] `uv run ruff check .` clean
- [ ] `uv run mypy bridge/` clean

---

## Phase 1: Service Layer Extraction

**Why second:** Resources and workflow tools need shared business logic. Currently logic is
embedded in tool functions — resources would duplicate it, workflows would fork it.

**Duration:** ~3 hours. Internal refactor, no API surface change.

### 1.1 Create `bridge/services/` Module

```text
bridge/services/
├── __init__.py
├── runs.py          # RunService: get, list, create, stop, ban, unban
├── execution.py     # ExecutionService: start, get_context, report_result
├── integrations.py  # IntegrationService: webhooks, sandbox, slack
└── settings.py      # SettingsService: get, update (local file)
```

### 1.2 `RunService` — First Extraction

Extract from `bridge/tools/agent/`:

```python
class RunService:
    def __init__(self, client: CodegenClient, registry: ContextRegistry) -> None:
        self.client = client
        self.registry = registry

    async def get_run(self, run_id: int) -> RunData:
        """Pure read. Returns structured data, no side effects."""
        run = await self.client.get_run(run_id)
        return RunData(run=run, prs=..., logs_summary=...)

    async def list_runs(self, cursor: str | None, limit: int, **filters) -> PaginatedRuns:
        """Pure read. Returns paginated list."""
        ...

    async def report_run_result(self, run_id: int, execution_id: str) -> TaskReport:
        """Explicit mutation. Writes to ContextRegistry."""
        ...
```

Tool functions become thin wrappers:
```python
@mcp.tool()
async def codegen_get_run(run_id: int, ...) -> str:
    service = RunService(client, registry)
    data = await service.get_run(run_id)
    return json.dumps(data.to_dict())
```

### 1.3 DI for Services

Add to `bridge/dependencies.py`:

```python
def get_run_service(ctx: Context) -> RunService:
    lc = ctx.lifespan_context
    return RunService(client=lc["client"], registry=lc["registry"])
```

Tools use: `service: RunService = Depends(get_run_service)  # type: ignore[arg-type]`

### 1.4 Acceptance Criteria

- [ ] All tool functions are thin wrappers (<15 lines) calling services
- [ ] Services own ALL business logic (validation, enrichment, formatting)
- [ ] No `client.xyz()` calls remain in tool functions (only `service.xyz()`)
- [ ] All tests pass with unchanged behavior
- [ ] Services are independently testable (no MCP dependency)

---

## Phase 2: ToolAnnotations

**Why after service layer:** Annotations must reflect REAL semantics. Phase 0 fixed the semantics,
Phase 1 made them explicit in service boundaries. Now annotations are mechanical.

**Duration:** ~1 hour. Metadata-only, no logic changes.

### 2.1 Classification from Inventory

Apply annotations based on [inventory Section 15](./mcp-surface-inventory.md#15-summary-statistics):

```python
from mcp.types import ToolAnnotations

# Pattern for read-only tools
@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
))
async def codegen_list_runs(...) -> str: ...

# Pattern for dangerous + open-world tools
@mcp.tool(
    tags={"dangerous"},
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def codegen_stop_run(...) -> str: ...
```

### 2.2 Full Annotation Map

| Tool | RO | DH | IH | OW |
|------|----|----|----|----|
| `codegen_get_run` (post-split) | T | F | T | F |
| `codegen_report_run_result` | F | F | T | F |
| `codegen_list_runs` | T | F | T | F |
| `codegen_create_run` | F | F | F | T |
| `codegen_resume_run` | F | F | F | T |
| `codegen_stop_run` | F | T | T | T |
| `codegen_ban_run` | F | T | T | T |
| `codegen_unban_run` | F | F | T | T |
| `codegen_remove_from_pr` | F | T | T | T |
| `codegen_get_logs` | T | F | T | F |
| `codegen_start_execution` | F | F | F | F |
| `codegen_get_execution_context` | T | F | T | F |
| `codegen_get_agent_rules` | T | F | T | F |
| `codegen_edit_pr` | F | T | F | T |
| `codegen_edit_pr_simple` | F | T | F | T |
| `codegen_list_orgs` | T | F | T | F |
| `codegen_get_organization_settings` | T | F | T | F |
| `codegen_list_repos` | T | F | T | F |
| `codegen_generate_setup_commands` | F | F | F | T |
| `codegen_get_current_user` | T | F | T | F |
| `codegen_list_users` | T | F | T | F |
| `codegen_get_user` | T | F | T | F |
| `codegen_get_mcp_providers` | T | F | T | F |
| `codegen_get_oauth_status` | T | F | T | F |
| `codegen_revoke_oauth` | F | T | T | T |
| `codegen_get_check_suite_settings` | T | F | T | F |
| `codegen_update_check_suite_settings` | F | F | T | T |
| `codegen_get_integrations` | T | F | T | F |
| `codegen_get_webhook_config` | T | F | T | F |
| `codegen_set_webhook_config` | F | F | T | T |
| `codegen_delete_webhook_config` | F | T | T | T |
| `codegen_test_webhook` | F | F | F | T |
| `codegen_analyze_sandbox_logs` | F | F | F | T |
| `codegen_generate_slack_token` | F | F | F | T |
| `codegen_get_settings` | T | F | T | F |
| `codegen_update_settings` | F | F | T | F |

Sampling tools (4): `RO=T, DH=F, IH=F, OW=F` — read data, invoke LLM, no persistent writes.

### 2.3 Implementation Strategy

**NOT sed-based mass replacement.** Each tool gets annotations added to its `@mcp.tool()` decorator
individually. Group by module, one commit per module.

### 2.4 Acceptance Criteria

- [ ] Every manual tool has explicit `ToolAnnotations`
- [ ] No `readOnlyHint=True` on tools with ANY side effects
- [ ] `openWorldHint=True` on every tool that makes outbound HTTP beyond Codegen API
- [ ] Annotations importable: `from mcp.types import ToolAnnotations`
- [ ] All tests pass

---

## Phase 3: Outbound Rate Budget

**Why before resources/workflows:** Resources may cache API responses (reducing calls),
but workflow tools (Phase 5) poll the API in loops. Without outbound rate limiting,
a create-and-monitor workflow can exhaust the API key's rate limit.

**Duration:** ~2 hours.

### 3.1 Distinction from Middleware Rate Limiting

```text
Middleware RateLimitingMiddleware = throttles INCOMING MCP requests from Claude
Outbound Rate Budget             = throttles OUTGOING httpx calls to Codegen API
```

These are orthogonal. Middleware already exists (layer 7). Outbound budget is new.

### 3.2 Token Bucket in CodegenClient

Add to `bridge/client.py`:

```python
class OutboundRateBudget:
    """Token-bucket rate limiter for outgoing API calls."""
    def __init__(self, max_tokens: int = 60, refill_rate: float = 1.0) -> None:
        self.max_tokens = max_tokens
        self.tokens = float(max_tokens)
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.monotonic()

    async def acquire(self, cost: int = 1) -> None:
        """Block until budget available. Raises if permanently exhausted."""
        ...

    @property
    def available(self) -> int:
        ...
```

Integrate into `CodegenClient._request()`:
```python
async def _request(self, method: str, path: str, ...) -> httpx.Response:
    await self.rate_budget.acquire()
    # existing retry logic...
```

### 3.3 Configuration

Add to `bridge/settings.py`:
```python
RATE_BUDGET_MAX_TOKENS: int = 60       # max burst
RATE_BUDGET_REFILL_RATE: float = 1.0   # tokens/sec (= 60 req/min sustained)
```

### 3.4 Acceptance Criteria

- [ ] `CodegenClient` has `OutboundRateBudget` injected
- [ ] All API calls go through budget (including retry attempts)
- [ ] Budget respects `Retry-After` header from API (already in retry logic)
- [ ] Configurable via settings
- [ ] Tests with `respx` mock verify budget enforcement

---

## Phase 4: Resource Templates

**Why after service layer + rate budget:** Resources call services (not raw client),
and their caching interacts correctly with rate budget.

**Duration:** ~2 hours.

### 4.1 High-Value Resources Only

From inventory Section 11, priority 1-2 only:

| Resource URI | Backed By | TTL | Why |
|-------------|-----------|-----|-----|
| `codegen://runs/{run_id}` | `RunService.get_run()` | 10s | Most polled entity |
| `codegen://runs/{run_id}/logs` | `RunService.get_logs()` | 30s | Debugging workflow |
| `codegen://execution/{execution_id}` | `ExecutionService.get_context()` | 5s | Orchestration state |

**NOT adding** setup/config resources (list_orgs, list_users, etc.) — called once per session,
tool form is fine.

### 4.2 Implementation

```python
# bridge/resources/templates.py
from fastmcp import Context

@mcp.resource("codegen://runs/{run_id}")
async def get_run_resource(
    run_id: int,
    service: RunService = Depends(get_run_service),  # type: ignore[arg-type]
) -> str:
    data = await service.get_run(run_id)
    return json.dumps(data.to_dict())
```

**Key:** Resource calls `service.get_run()` — same code path as the tool.
No data divergence because both use the service layer.

### 4.3 Acceptance Criteria

- [ ] Resources backed by services, NOT raw `client.xyz()` calls
- [ ] Existing tools still work (resources are additive)
- [ ] Resource responses match tool responses (same service, same serialization)
- [ ] Tests verify resource reads go through service layer

---

## Phase 5: Workflow Composition

**Why after rate budget + resources:** Workflows poll `get_run` in loops.
Rate budget prevents API exhaustion. Resources provide cacheable reads.

**Duration:** ~3 hours.

### 5.1 `codegen_create_and_monitor`

```python
@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
))
async def codegen_create_and_monitor(
    task: str,
    repo: str | None = None,
    model: str | None = None,
    max_polls: int = 60,
    poll_interval: float = 10.0,
    ctx: Context = CurrentContext(),
    service: RunService = Depends(get_run_service),  # type: ignore[arg-type]
) -> str:
    # 1. Create run
    run = await service.create_run(task=task, repo=repo, model=model)

    # 2. Poll with backoff (uses PURE get_run, no execution_id side effects)
    for i in range(max_polls):
        await asyncio.sleep(poll_interval * min(2 ** (i // 10), 4))  # backoff
        data = await service.get_run(run.id)  # pure read via service
        await report(ctx, i + 1, max_polls, f"Status: {data.run.status}")
        if data.run.status in ("completed", "failed", "error"):
            return json.dumps(data.to_dict())

    return json.dumps({"timeout": True, "run_id": run.id, "last_status": data.run.status})
```

**Critical:** Uses `service.get_run()` (pure read), NOT `codegen_get_run` tool.
No `execution_id` means no side-effect writes during polling.

### 5.2 Budget Integration

Polling calls `service.get_run()` → `client.get_run()` → passes through `OutboundRateBudget`.
60 polls at 10s interval = 60 API calls over 10 minutes = well within 60 req/min budget.

If budget exhausted (other tools running concurrently), `acquire()` blocks instead of failing.

### 5.3 Acceptance Criteria

- [ ] Workflow uses service layer, NOT tool functions
- [ ] Polling does NOT trigger `report_run_result` side effects
- [ ] Rate budget prevents >60 req/min to API
- [ ] `max_polls` and `poll_interval` prevent infinite loops
- [ ] Progress reporting via `report()` at each poll
- [ ] Tests with `respx` mock verify full create→poll→complete flow

---

## Phase 6: Serialization Cleanup

**Why last:** All prior phases may change serialization points. Consolidating before
they stabilize wastes effort (refactor churn).

**Duration:** ~1.5 hours.

### 6.1 Consolidate Serialization

From inventory Section 10.1, six duplication points. After service layer extraction,
serialization lives in services. Cleanup:

| Current Location | After Cleanup |
|-----------------|---------------|
| `helpers/formatting.py:format_run()` | **Keep** — used by sampling tools |
| `helpers/formatting.py:format_run_basic()` | Remove — replaced by `RunData.to_dict()` |
| `tools/agent/queries.py` inline dict | Remove — replaced by `RunService.get_run()` |
| `tools/setup/users.py:_user_to_dict()` | Move to `UserData.to_dict()` in services |
| `sampling/tools.py` inline log formatting | Replace with `format_logs()` from helpers |

### 6.2 Acceptance Criteria

- [ ] Each entity has ONE serialization method (in its Data class or service)
- [ ] No inline dict building in tool functions
- [ ] `format_run_basic()` removed (redundant with `RunData`)
- [ ] Sampling tools use `format_logs()` from helpers
- [ ] All tests pass

---

## Implementation Order Checklist

```text
[ ] Phase 0.1 — Split codegen_get_run → get_run + report_run_result
[ ] Phase 0.2 — Add tags to misleading tools
[ ] Phase 0.3 — Tests green, lint clean
[ ] ─── COMMIT: "refactor(tools): split get_run read/write paths" ───

[ ] Phase 1.1 — Create bridge/services/ with RunService
[ ] Phase 1.2 — Migrate agent tools to use RunService
[ ] Phase 1.3 — Add DI providers for services
[ ] Phase 1.4 — Migrate remaining tools to services
[ ] ─── COMMIT: "refactor(arch): extract service layer from tools" ───

[ ] Phase 2.1 — Import ToolAnnotations, verify FastMCP support
[ ] Phase 2.2 — Apply annotations to all 39 tools (per annotation map)
[ ] Phase 2.3 — Apply annotations to 4 sampling tools
[ ] ─── COMMIT: "feat(mcp): add ToolAnnotations to all tools" ───

[ ] Phase 3.1 — Implement OutboundRateBudget
[ ] Phase 3.2 — Integrate into CodegenClient._request()
[ ] Phase 3.3 — Add configuration
[ ] ─── COMMIT: "feat(client): add outbound rate budget" ───

[ ] Phase 4.1 — Add runs/{run_id} resource template
[ ] Phase 4.2 — Add runs/{run_id}/logs resource template
[ ] Phase 4.3 — Add execution/{id} resource template
[ ] ─── COMMIT: "feat(resources): add dynamic resource templates" ───

[ ] Phase 5.1 — Implement codegen_create_and_monitor
[ ] Phase 5.2 — Verify rate budget integration
[ ] ─── COMMIT: "feat(tools): add create-and-monitor workflow" ───

[ ] Phase 6.1 — Consolidate serialization into Data classes
[ ] Phase 6.2 — Remove duplication points
[ ] ─── COMMIT: "refactor(serial): consolidate entity serialization" ───

[ ] Update CLAUDE.md with new architecture
[ ] Update plugin version to 0.5.0
[ ] ─── COMMIT: "chore: bump to v0.5.0" ───
```

---

## What This Plan Does NOT Include

| Excluded | Why |
|----------|-----|
| Mass `sed`-based decorator replacement | Fragile, impossible to validate semantically |
| Renaming existing tools | Breaks Claude Code sessions with cached tool names |
| Resource templates for all 16 candidates | Low-value resources (setup/config) add complexity without benefit |
| OpenAPI provider annotations | Auto-generated tools are a fallback layer — annotating them is wasted effort |
| Prompt refactoring | Prompts are decorative text, refactoring them has zero architectural value |
| Transform chain changes | Existing transforms are fine — v0.5 is about tool semantics, not transport |

---

## Risk Matrix

| Risk | Impact | Mitigation |
|------|--------|-----------|
| `codegen_get_run` split breaks execution flow | High | Phase 0 tests verify both paths independently before proceeding |
| Service layer introduces latency | Low | Services are thin wrappers, no extra I/O. Profile if concerned |
| ToolAnnotations not supported by FastMCP version | Medium | Phase 2.1 validates import before applying. Fallback: skip phase |
| Rate budget too aggressive | Medium | Configurable. Default 60 req/min matches most API limits |
| Workflow polling timeout | Low | `max_polls` + `poll_interval` are tool parameters, caller controls |
| Serialization consolidation breaks response format | Medium | Phase 6 is last — all consumers stabilized. Test response schemas |

# Full Redesign Plan: Codegen Bridge MCP Server v1.0

**Date:** 2026-02-22
**Status:** Approved
**Strategy:** Wave execution (parallel within waves, sequential between waves)
**Model:** claude-opus-4-6
**Code principles:** OOP, KISS, DRY, SOLID, GoF patterns, clean architecture

## Goal

Complete redesign of the Codegen Bridge Claude Code plugin:
- Leverage modern FastMCP 3.x capabilities (background tasks, progress, Tasks API, storage backends, transforms)
- Refactor to SOLID/DRY principles with proper OOP and GoF patterns
- Improve HTTP reliability, error handling, and observability
- Automate OpenAPI spec governance
- Add new capabilities and improve skills/plugin structure
- Comprehensive CI/CD and developer experience

## Architecture Overview

```text
Claude Code ──MCP──▶ FastMCP Server (bridge/server.py)
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
        Middleware     Transforms   Background
        (9 layers)    (4 stages)    Tasks API
             │            │            │
             └────────────┬────────────┘
                          ▼
                   Tool Functions (bridge/tools/)
                   [Decomposed: agent/, setup/, integrations/]
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
     CodegenClient    Storage       Sampling
     (reliable httpx) (Strategy)   (ctx.sample)
```

## Reference Documentation

All Codegen agents MUST read these before implementing:

### FastMCP Documentation (gofastmcp.com)
- **Core:** https://gofastmcp.com/servers/server.md — server setup, lifespan
- **Context:** https://gofastmcp.com/servers/context.md — ctx.report_progress, ctx.sample, ctx.lifespan_context
- **Background Tasks:** https://gofastmcp.com/servers/tasks.md — deferred/background execution
- **Progress:** https://gofastmcp.com/servers/progress.md — progress reporting API
- **Middleware:** https://gofastmcp.com/servers/middleware.md — middleware chain patterns
- **Elicitation:** https://gofastmcp.com/servers/elicitation.md — interactive user prompts
- **Sampling:** https://gofastmcp.com/servers/sampling.md — server-side LLM calls
- **Providers:** https://gofastmcp.com/servers/providers/overview.md — provider system
- **Transforms:** https://gofastmcp.com/servers/transforms/transforms.md — tool transformation
- **Tool Transform:** https://gofastmcp.com/servers/transforms/tool-transformation.md
- **Resources:** https://gofastmcp.com/servers/resources.md
- **Prompts:** https://gofastmcp.com/servers/prompts.md
- **Storage:** https://gofastmcp.com/servers/storage-backends.md
- **Telemetry:** https://gofastmcp.com/servers/telemetry.md
- **Pagination:** https://gofastmcp.com/servers/pagination.md
- **Logging:** https://gofastmcp.com/servers/logging.md
- **Lifespan:** https://gofastmcp.com/servers/lifespan.md
- **DI:** https://gofastmcp.com/servers/dependency-injection.md
- **OpenAPI:** https://gofastmcp.com/integrations/openapi.md
- **Claude Code:** https://gofastmcp.com/integrations/claude-code.md
- **Testing:** https://gofastmcp.com/patterns/testing.md
- **Client Tasks:** https://gofastmcp.com/clients/tasks.md
- **Client Progress:** https://gofastmcp.com/clients/progress.md
- **Client Sampling:** https://gofastmcp.com/clients/sampling.md
- **Transforms — Namespace:** https://gofastmcp.com/servers/transforms/namespace.md
- **Transforms — Prompts as Tools:** https://gofastmcp.com/servers/transforms/prompts-as-tools.md
- **Transforms — Resources as Tools:** https://gofastmcp.com/servers/transforms/resources-as-tools.md
- **Providers — Filesystem:** https://gofastmcp.com/servers/providers/filesystem.md
- **Providers — Skills:** https://gofastmcp.com/servers/providers/skills.md
- **Versioning:** https://gofastmcp.com/servers/versioning.md
- **Visibility:** https://gofastmcp.com/servers/visibility.md
- **Auth Overview:** https://gofastmcp.com/servers/auth/authentication.md
- **Python SDK — Server:** https://gofastmcp.com/python-sdk/fastmcp-server-server.md
- **Python SDK — Tasks:** https://gofastmcp.com/python-sdk/fastmcp-server-tasks-__init__.md
- **Python SDK — Sampling:** https://gofastmcp.com/python-sdk/fastmcp-server-sampling-__init__.md

### Codegen API Documentation (docs.codegen.com)
- **Overview:** https://docs.codegen.com/introduction/overview.md
- **SDK:** https://docs.codegen.com/introduction/sdk.md
- **Prompting:** https://docs.codegen.com/introduction/prompting.md
- **CLI:** https://docs.codegen.com/introduction/cli.md
- **Use Cases:** https://docs.codegen.com/introduction/use-cases.md
- **Agents — Create Run:** https://docs.codegen.com/api-reference/agents/create-agent-run.md
- **Agents — Get Run:** https://docs.codegen.com/api-reference/agents/get-agent-run.md
- **Agents — List Runs:** https://docs.codegen.com/api-reference/agents/list-agent-runs.md
- **Agents — Resume:** https://docs.codegen.com/api-reference/agents/resume-agent-run.md
- **Agents — Ban:** https://docs.codegen.com/api-reference/agents/ban-all-checks-for-agent-run.md
- **Agents — Unban:** https://docs.codegen.com/api-reference/agents/unban-all-checks-for-agent-run.md
- **Agents — Remove from PR:** https://docs.codegen.com/api-reference/agents/remove-codegen-from-pr.md
- **Logs:** https://docs.codegen.com/api-reference/agent-run-logs.md
- **Logs Alpha:** https://docs.codegen.com/api-reference/agents-alpha/get-agent-run-logs.md
- **PRs — Edit:** https://docs.codegen.com/api-reference/pull-requests/edit-pull-request.md
- **PRs — Edit Simple:** https://docs.codegen.com/api-reference/pull-requests/edit-pull-request-simple.md
- **Repos:** https://docs.codegen.com/api-reference/repositories/get-repositories.md
- **Check Suite:** https://docs.codegen.com/api-reference/repositories/get-check-suite-settings.md
- **Sandbox Overview:** https://docs.codegen.com/sandboxes/overview.md
- **Sandbox Setup:** https://docs.codegen.com/sandboxes/setup-commands.md
- **Sandbox Env Vars:** https://docs.codegen.com/sandboxes/environment-variables.md
- **Sandbox Secrets:** https://docs.codegen.com/sandboxes/secrets.md
- **Sandbox Editor:** https://docs.codegen.com/sandboxes/editor.md
- **Sandbox Web Preview:** https://docs.codegen.com/sandboxes/web-preview.md
- **Settings:** https://docs.codegen.com/settings/settings.md
- **Agent Behavior:** https://docs.codegen.com/settings/agent-behavior.md
- **Agent Permissions:** https://docs.codegen.com/settings/agent-permissions.md
- **Model Config:** https://docs.codegen.com/settings/model-configuration.md
- **Repo Rules:** https://docs.codegen.com/settings/repo-rules.md
- **Team Roles:** https://docs.codegen.com/settings/team-roles.md
- **Capabilities:** https://docs.codegen.com/capabilities/capabilities.md
- **Analytics:** https://docs.codegen.com/capabilities/analytics.md
- **PR Review:** https://docs.codegen.com/capabilities/pr-review.md
- **Claude Code Integration:** https://docs.codegen.com/capabilities/claude-code.md
- **Triggering:** https://docs.codegen.com/capabilities/triggering-codegen.md
- **Integrations:** https://docs.codegen.com/integrations/integrations.md
- **GitHub:** https://docs.codegen.com/integrations/github.md
- **Linear:** https://docs.codegen.com/integrations/linear.md
- **Slack:** https://docs.codegen.com/integrations/slack.md
- **Sentry:** https://docs.codegen.com/integrations/sentry.md
- **MCP Servers:** https://docs.codegen.com/integrations/mcp-servers.md
- **Authentication:** https://docs.codegen.com/api-reference/authentication.md
- **MCP Providers:** https://docs.codegen.com/api-reference/organizations/get-mcp-providers.md

### Claude Code Plugin Documentation
- **Plugins Guide:** https://code.claude.com/docs/en/plugins.md
- **MCP Guide:** https://code.claude.com/docs/en/mcp.md

### Superpowers Reference
- **Repository:** https://github.com/obra/superpowers
- **Executing Plans:** Skills pattern for plan execution with checkpoints
- **Writing Plans:** Plan creation with bite-sized tasks

---

## Wave 1: Foundation (Parallel)

### Task 1: CI/CD + Developer Experience + Justfile

**Goal:** Add GitHub Actions CI pipeline and developer tooling to ensure reproducible builds.

**Scope:**
- Create `.github/workflows/ci.yml`: `uv sync` → `ruff` → `mypy` → `pytest` → smoke-import test
- Create `Justfile` with recipes: `test`, `lint`, `typecheck`, `check` (all), `dev`, `preflight`
- Preflight script: verify Python 3.12, env vars present, `.venv` exists
- Add smoke-test job: import `bridge.server`, verify MCP tools registered
- Update `README.md` with "Always use `uv run`" section and quick-start
- Create `.env.example` with all required vars

**References:**
- https://gofastmcp.com/patterns/testing.md
- https://gofastmcp.com/deployment/running-server.md
- https://gofastmcp.com/deployment/server-configuration.md
- https://docs.codegen.com/sandboxes/environment-variables.md
- https://docs.codegen.com/sandboxes/setup-commands.md
- https://code.claude.com/docs/en/plugins.md

**Standards:** KISS (minimal CI steps), DRY (shared actions), SOLID (single-responsibility per job)

---

### Task 2: HTTP Client Reliability

**Goal:** Make `bridge/client.py` production-grade with proper timeouts, retries, and error normalization.

**Scope:**
- `httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)` — split timeout config
- `httpx.Limits(max_keepalive_connections=10, max_connections=20)`
- Retry transport for transient errors (429, 500+) — exponential backoff, max 3 retries
- Unified error hierarchy: `CodegenAPIError → (RateLimitError, AuthError, ServerError, NotFoundError)`
- Request/response event hooks for correlation ID and telemetry
- Sync `CodegenClient` config with HTTP client in `bridge/server.py` (no drift)
- Tests with `respx` for all error scenarios

**References:**
- https://gofastmcp.com/servers/telemetry.md
- https://gofastmcp.com/servers/logging.md
- https://gofastmcp.com/python-sdk/fastmcp-server-telemetry.md
- https://docs.codegen.com/api-reference/authentication.md
- https://docs.codegen.com/api-reference/overview.md

**GoF Patterns:** Template Method (retry logic), Chain of Responsibility (error handling), Observer (event hooks)
**Standards:** SOLID (SRP — client only does HTTP, OCP — extend via hooks), DRY (one error hierarchy)

---

### Task 3: Tools Architecture Refactoring (SOLID Decomposition)

**Goal:** Decompose `bridge/tools/agent.py` (644 lines) and `bridge/tools/setup.py` (401 lines) into focused submodules.

**Scope:**
- `bridge/tools/agent/` package:
  - `create.py` — `codegen_create_run`
  - `read.py` — `codegen_get_run`, `codegen_list_runs`
  - `lifecycle.py` — `codegen_resume_run`, `codegen_stop_run`, `codegen_ban_run`, `codegen_unban_run`
  - `pr.py` — `codegen_remove_from_pr`
  - `logs.py` — `codegen_get_logs`
  - `__init__.py` — `register_agent_tools(mcp)` → imports all submodules
- `bridge/tools/setup/` package: split by domain (users, repos, orgs, projects)
- Shared `bridge/tools/response.py` — typed response envelopes, `json.dumps` helpers
- Shared `bridge/tools/pagination.py` — cursor pagination pattern (extract from `list_runs`)
- Update all imports in `server.py` and tests
- All tests must pass: `uv run pytest -v`

**References:**
- https://gofastmcp.com/servers/tools.md
- https://gofastmcp.com/servers/dependency-injection.md
- https://gofastmcp.com/servers/context.md
- https://gofastmcp.com/python-sdk/fastmcp-tools-__init__.md
- https://code.claude.com/docs/en/plugins.md

**GoF Patterns:** Facade (register_agent_tools as facade), Factory Method (response builders), Strategy (pagination)
**Standards:** SOLID (SRP per module, ISP per interface), DRY (shared response/pagination helpers)

---

## Wave 2: Modern FastMCP Features (Parallel, after Wave 1)

### Task 4: Background Tasks + Progress Reporting for Run Monitoring

**Goal:** Replace synchronous polling pattern with FastMCP background tasks and progress reporting.

**Scope:**
- New tool: `codegen_monitor_run` — starts background task that polls run status
  - Uses `ctx.report_progress(current, total, message)` for live updates
  - Runs in background, notifies when done or blocked
- New tool: `codegen_monitor_execution` — monitors full execution context progress
- Update `codegen_get_logs` to stream logs progressively with progress events
- Background task manager: cancel/list active monitors via `codegen_list_monitors`, `codegen_cancel_monitor`
- Integrate with FastMCP Tasks API (`fastmcp[tasks]` extra)
- Tests: mock background execution, verify progress events emitted

**References:**
- https://gofastmcp.com/servers/tasks.md
- https://gofastmcp.com/servers/progress.md
- https://gofastmcp.com/servers/context.md
- https://gofastmcp.com/clients/tasks.md
- https://gofastmcp.com/clients/progress.md
- https://gofastmcp.com/python-sdk/fastmcp-server-tasks-__init__.md
- https://gofastmcp.com/python-sdk/fastmcp-cli-tasks.md
- https://gofastmcp.com/python-sdk/fastmcp-client-tasks.md
- https://docs.codegen.com/api-reference/agents/get-agent-run.md
- https://docs.codegen.com/api-reference/agent-run-logs.md

**GoF Patterns:** Observer (progress events), Command (background task as command object), Template Method (poll loop)
**Standards:** SOLID (OCP — new monitoring without changing existing tools), KISS (simple polling with progress)

---

### Task 5: OpenAPI Spec Automation + Governance

**Goal:** Automate OpenAPI spec synchronization and add drift/parity detection tests.

**Scope:**
- Script `scripts/update_openapi_spec.py`:
  - Fetches `https://api.codegen.com/api/openapi.json`
  - Patches and saves to `bridge/openapi_spec.json`
  - Reports diff summary
- Test `tests/test_openapi_governance.py`:
  - Drift detection: warn if local spec is older than N days
  - Parity test: manual endpoints excluded from OpenAPI tool generation
  - Coverage test: all `TOOL_NAMES` operationIds present in spec
  - Route map test: no unexpected endpoints captured
- Makefile/Justfile recipe: `just update-spec`
- GitHub Actions job: monthly spec freshness check

**References:**
- https://gofastmcp.com/integrations/openapi.md
- https://gofastmcp.com/servers/providers/overview.md
- https://gofastmcp.com/python-sdk/fastmcp-server-providers-openapi-__init__.md
- https://gofastmcp.com/python-sdk/fastmcp-server-openapi-__init__.md
- https://gofastmcp.com/python-sdk/fastmcp-utilities-openapi-__init__.md
- https://docs.codegen.com/api-reference/overview.md
- https://docs.codegen.com/api-reference/authentication.md

**GoF Patterns:** Adapter (spec patching), Template Method (governance checks), Strategy (diff algorithms)
**Standards:** DRY (single source for spec), SOLID (OCP — extend governance without changing core)

---

### Task 6: Enhanced Sampling + Elicitation Patterns

**Goal:** Upgrade sampling service and elicitation with structured schemas, better UX, and more sampling tools.

**Scope:**
- Upgrade `bridge/elicitation.py`:
  - `confirm_with_schema` — richer typed schemas using Pydantic
  - `select_multiple` — multi-choice elicitation
  - Graceful degradation testing for non-supporting clients
- New sampling tools in `bridge/sampling/`:
  - `codegen_review_logs` — AI review of run logs, suggests next action
  - `codegen_diagnose_failure` — structured failure analysis with recovery suggestions
  - `codegen_estimate_task` — AI estimates task complexity from description
- Update `bridge/sampling/service.py` to use model-specified opus-4-6
- Tests: mock `ctx.sample()`, verify sampling prompts, test elicitation flows

**References:**
- https://gofastmcp.com/servers/elicitation.md
- https://gofastmcp.com/servers/sampling.md
- https://gofastmcp.com/servers/context.md
- https://gofastmcp.com/clients/elicitation.md
- https://gofastmcp.com/clients/sampling.md
- https://gofastmcp.com/python-sdk/fastmcp-server-elicitation.md
- https://gofastmcp.com/python-sdk/fastmcp-server-sampling-__init__.md
- https://gofastmcp.com/python-sdk/fastmcp-client-sampling-__init__.md
- https://gofastmcp.com/integrations/anthropic.md
- https://docs.codegen.com/settings/model-configuration.md

**GoF Patterns:** Strategy (sampling backends), Builder (structured schemas), Template Method (sampling prompts)
**Standards:** OOP, SOLID, KISS — keep sampling prompts simple and focused

---

## Wave 3: New Capabilities (Parallel, after Wave 2)

### Task 7: New Tools — Bulk Operations + Analytics + Advanced Monitoring

**Goal:** Add high-value tools for bulk operations, analytics, and advanced run monitoring.

**Scope:**
- `codegen_bulk_create_runs` — create multiple runs from a list of tasks (batch delegation)
- `codegen_get_run_analytics` — aggregate stats: total runs, success rate, avg duration per repo
- `codegen_list_runs_by_status` — filtered listing with status, repo, date range
- `codegen_get_organization_summary` — org-level overview: users, repos, active runs, quota
- `codegen_watch_run` — long-poll that blocks until run completes (combines monitor + wait)
- Pagination improvements: cursor-based with `has_more` + count estimates
- All tools follow response envelope pattern from Task 3

**References:**
- https://docs.codegen.com/api-reference/agents/list-agent-runs.md
- https://docs.codegen.com/capabilities/analytics.md
- https://docs.codegen.com/capabilities/capabilities.md
- https://docs.codegen.com/api-reference/organizations/get-organizations.md
- https://docs.codegen.com/api-reference/users/get-users.md
- https://gofastmcp.com/servers/tools.md
- https://gofastmcp.com/servers/pagination.md
- https://gofastmcp.com/servers/tasks.md

**GoF Patterns:** Facade (org summary), Iterator (pagination), Command (bulk operations)
**Standards:** SOLID (SRP per tool), DRY (shared pagination/response helpers)

---

### Task 8: Transforms, Versioning + Visibility Enhancements

**Goal:** Leverage unused FastMCP transform capabilities for better tool organization and versioning.

**Scope:**
- Configure `VersionFilter` transform: gate experimental tools behind version flag
- Configure `Visibility` transform: hide internal/debug tools from production
- `PromptAsTools` transform: expose prompt templates as callable tools
- `ResourcesAsTools` transform: expose resources (config, platform docs) as tools
- `Namespace` transform config: consistent `codegen_` prefix enforcement
- Version-based tool migration path: old → new tool names with deprecation notices
- Transform config in `bridge/transforms/config.py` — extend `TransformsConfig`

**References:**
- https://gofastmcp.com/servers/transforms/transforms.md
- https://gofastmcp.com/servers/transforms/tool-transformation.md
- https://gofastmcp.com/servers/transforms/namespace.md
- https://gofastmcp.com/servers/transforms/prompts-as-tools.md
- https://gofastmcp.com/servers/transforms/resources-as-tools.md
- https://gofastmcp.com/servers/versioning.md
- https://gofastmcp.com/servers/visibility.md
- https://gofastmcp.com/python-sdk/fastmcp-server-transforms-__init__.md

**GoF Patterns:** Decorator (transform chain), Chain of Responsibility (transform pipeline), Adapter (resource-as-tool)
**Standards:** OCP (extend without modifying), DRY (centralized transform config)

---

### Task 9: Integrations — Webhooks, Slack, GitHub Advanced

**Goal:** Fully implement integrations capabilities with proper models and UX.

**Scope:**
- Webhook tools: full CRUD with validation, test-fire, event type selection
- `codegen_setup_github_integration` — guided GitHub setup with elicitation
- `codegen_setup_slack_integration` — Slack connect with token generation
- `codegen_get_sandbox_info` — sandbox environment details for current org
- `codegen_manage_environment_variables` — CRUD for sandbox env vars
- Integration health check: `codegen_check_integration_health`
- Update `bridge/tools/integrations.py` → decompose into `bridge/tools/integrations/` package

**References:**
- https://docs.codegen.com/integrations/integrations.md
- https://docs.codegen.com/integrations/github.md
- https://docs.codegen.com/integrations/slack.md
- https://docs.codegen.com/integrations/linear.md
- https://docs.codegen.com/integrations/sentry.md
- https://docs.codegen.com/integrations/mcp-servers.md
- https://docs.codegen.com/sandboxes/overview.md
- https://docs.codegen.com/sandboxes/environment-variables.md
- https://docs.codegen.com/sandboxes/secrets.md
- https://docs.codegen.com/api-reference/integrations/get-organization-integrations-endpoint.md
- https://docs.codegen.com/api-reference/slack-connect/generate-slack-connect-token-endpoint.md
- https://gofastmcp.com/servers/elicitation.md

**GoF Patterns:** Facade (integration setup wizards), Strategy (per-integration logic), Command (CRUD ops)
**Standards:** SOLID, KISS — wizard-style elicitation for complex setup flows

---

## Wave 4: Skills, Plugin + Docs (Sequential, after Wave 3)

### Task 10: Skills Redesign + New Skills

**Goal:** Update all skills with modern patterns and add new skills for the enhanced capabilities.

**Scope:**
- Update `skills/executing-via-codegen/SKILL.md`:
  - Add background task monitoring option (use Task 4's `codegen_monitor_run`)
  - Add parallel runs option for independent tasks
  - Add `codegen_review_logs` AI-review step (Task 6)
  - Reference model selection: `codegen_get_models` → claude-opus-4-6
- New skill: `skills/bulk-delegation/SKILL.md` — batch task execution via `codegen_bulk_create_runs`
- New skill: `skills/run-analytics/SKILL.md` — analyze past runs, generate insights
- Update `skills/agent-monitoring/SKILL.md` — use new background task monitoring
- Update `skills/pr-management/SKILL.md` — add auto-merge flow, health checks

**References:**
- https://github.com/obra/superpowers
- https://code.claude.com/docs/en/plugins.md
- https://gofastmcp.com/servers/providers/skills.md
- https://gofastmcp.com/python-sdk/fastmcp-server-providers-skills-__init__.md
- https://docs.codegen.com/introduction/use-cases.md
- https://docs.codegen.com/capabilities/claude-code.md
- https://docs.codegen.com/capabilities/pr-review.md

---

### Task 11: Plugin Structure + Hooks + Commands + Agents

**Goal:** Modernize plugin structure following official Claude Code plugin documentation.

**Scope:**
- Update `plugin.json`: version bump, add new skills/commands/agents
- New hooks:
  - `post-monitor-run.sh` — formats background task completion notification
  - `post-bulk-create.sh` — summary after bulk run creation
  - Update existing hooks for new response formats
- New command: `commands/cg-bulk.md` — `/cg-bulk` for batch task delegation
- New command: `commands/cg-analytics.md` — `/cg-analytics` for run analytics
- Update `agents/codegen-delegator.md` — use bulk operations and monitoring
- New agent: `agents/run-analyzer.md` — analyzes failed runs and suggests fixes
- Verify all hook regexes match `mcp__.*codegen_*` pattern

**References:**
- https://code.claude.com/docs/en/plugins.md
- https://code.claude.com/docs/en/mcp.md
- https://gofastmcp.com/integrations/claude-code.md
- https://gofastmcp.com/servers/providers/skills.md
- https://docs.codegen.com/capabilities/claude-code.md
- https://docs.codegen.com/integrations/mcp-servers.md

---

### Task 12: Telemetry, Observability + Storage Backends

**Goal:** Complete telemetry integration and improve storage backend usage.

**Scope:**
- Complete OpenTelemetry config in `bridge/telemetry/`:
  - Span attributes: run_id, org_id, tool_name, duration
  - Metrics: tool call count, error rate, latency histogram
  - Export to OTLP (configurable endpoint)
- Storage improvements in `bridge/storage.py`:
  - TTL-based expiry for `FileStorage` contexts
  - Typed storage keys enum
  - Storage health check: `codegen_storage_stats`
- Environment config: `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`
- Tests: mock telemetry exporter, verify spans/metrics

**References:**
- https://gofastmcp.com/servers/telemetry.md
- https://gofastmcp.com/servers/storage-backends.md
- https://gofastmcp.com/servers/logging.md
- https://gofastmcp.com/python-sdk/fastmcp-server-telemetry.md
- https://gofastmcp.com/python-sdk/fastmcp-client-telemetry.md
- https://docs.codegen.com/settings/settings.md

**GoF Patterns:** Observer (telemetry hooks), Proxy (storage with TTL), Decorator (telemetry wrapper)

---

### Task 13: Documentation — Architecture + API Reference + Runbooks

**Goal:** Write comprehensive documentation for the project.

**Scope:**
- `docs/architecture.md` — full architecture guide with diagrams (data flow, middleware stack, transform chain)
- `docs/api-reference.md` — all 39+ manual tools with parameters, examples, error codes
- `docs/development.md` — dev setup, testing strategy, contributing guide, troubleshooting
- `docs/runbooks/` — operational runbooks:
  - `rate-limiting.md` — handle 429 errors
  - `auth-failure.md` — debug API key/org_id issues
  - `openapi-drift.md` — update spec when Codegen API changes
  - `telemetry-setup.md` — configure OTEL exporter
- Update `README.md` — concise overview with quick-start, links to docs/
- `CHANGELOG.md` — document all changes from this redesign

**References:**
- https://gofastmcp.com/getting-started/welcome.md
- https://gofastmcp.com/servers/server.md
- https://docs.codegen.com/introduction/overview.md
- https://docs.codegen.com/introduction/prompting.md
- https://code.claude.com/docs/en/plugins.md
- https://code.claude.com/docs/en/mcp.md
- https://github.com/obra/superpowers

---

## Execution Plan (Wave Schedule)

```text
Wave 1 (Parallel): Task 1 + Task 2 + Task 3
   ↓ (all merged)
Wave 2 (Parallel): Task 4 + Task 5 + Task 6
   ↓ (all merged)
Wave 3 (Parallel): Task 7 + Task 8 + Task 9
   ↓ (all merged)
Wave 4 (Sequential): Task 10 → Task 11 → Task 12 → Task 13
```

## Quality Gates (per task)

Before creating PR, Codegen agent MUST verify:
1. `uv run pytest -q` — all tests pass (baseline: 1015 passed)
2. `uv run ruff check .` — no linting errors
3. `uv run mypy bridge/` — no type errors
4. New code has test coverage ≥ 80%
5. No new `# type: ignore` without comment explaining why

## Constraints

- **Model:** `claude-opus-4-6` for all Codegen agent runs
- **Branch:** Each task creates its own feature branch from `master`
- **Commits:** Conventional commits format (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`)
- **PR:** One PR per task, reviewed and merged before next wave starts
- **NEVER:** Break existing 1015 passing tests
- **ALWAYS:** `uv run` prefix (never bare `python`, `pytest`, `mypy`)

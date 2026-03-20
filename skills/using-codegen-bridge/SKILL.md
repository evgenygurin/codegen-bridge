---
name: using-codegen-bridge
description: Use when starting any conversation involving Codegen cloud agents — establishes skill map, decision tree, and integration with superpowers plugin
user-invocable: false
---

# Using Codegen Bridge

## What This Plugin Does

Codegen Bridge delegates coding tasks to cloud AI agents on the [Codegen](https://codegen.com) platform. Instead of making changes locally, tasks run in isolated cloud sandboxes and produce pull requests on GitHub.

## Skill Map

When working with Codegen agents, invoke the relevant skill BEFORE taking action:

| Situation | Skill | How |
|-----------|-------|-----|
| Delegate a task to cloud agent | `codegen-bridge:codegen-delegation` | Auto-triggers on `codegen_create_run` |
| Execute a plan via cloud agents | `codegen-bridge:executing-via-codegen` | User-invocable or auto |
| Batch-delegate independent tasks | `codegen-bridge:bulk-delegation` | User-invocable |
| Monitor running agents | `codegen-bridge:agent-monitoring` | Auto-triggers on `codegen_get_run` |
| Debug a failed/stuck agent run | `codegen-bridge:debugging-failed-runs` | Auto-triggers on failure patterns |
| Write effective agent prompts | `codegen-bridge:prompt-crafting` | Auto-triggers on `codegen_create_run` |
| Review agent-created code/PRs | `codegen-bridge:reviewing-agent-output` | Auto-triggers on completed runs |
| Manage PR state (close/draft/ban) | `codegen-bridge:pr-management` | Auto-triggers on `codegen_edit_pr` |
| Analyze agent performance | `codegen-bridge:run-analytics` | User-invocable |

## Decision Tree

```text
User wants to change code
├── Small/quick change (one-liner, config tweak)?
│   └── Do it locally — Codegen is overkill
├── Needs local environment (secrets, services, debugging)?
│   └── Do it locally
├── Feature implementation, refactor, test suite?
│   ├── Single task?
│   │   └── codegen-delegation → codegen_create_run
│   ├── Multi-step plan with dependencies?
│   │   └── executing-via-codegen → sequential runs
│   └── Multiple independent tasks?
│       └── bulk-delegation → codegen_bulk_create_runs
└── Not sure?
    └── Ask: "Should this run locally or via Codegen cloud agent?"
```

## Integration with Superpowers

If the `superpowers` plugin is installed alongside codegen-bridge:

**Use superpowers for PROCESS:**
- `superpowers:brainstorming` — design before code
- `superpowers:writing-plans` — create implementation plans
- `superpowers:test-driven-development` — TDD discipline
- `superpowers:systematic-debugging` — debug LOCAL issues
- `superpowers:requesting-code-review` — review LOCAL code
- `superpowers:verification-before-completion` — verify LOCAL work

**Use codegen-bridge for CLOUD EXECUTION:**
- `codegen-bridge:executing-via-codegen` — execute plans via cloud agents
- `codegen-bridge:debugging-failed-runs` — debug AGENT failures
- `codegen-bridge:reviewing-agent-output` — review AGENT-created code
- `codegen-bridge:prompt-crafting` — optimize prompts for agents

**Combined workflow:**
1. `superpowers:brainstorming` → design the feature
2. `superpowers:writing-plans` → create the plan
3. `codegen-bridge:executing-via-codegen` → execute via cloud agents
4. `codegen-bridge:reviewing-agent-output` → review agent PRs
5. `superpowers:finishing-a-development-branch` → merge

If superpowers is NOT installed, codegen-bridge works standalone. You lose the process skills but all cloud delegation skills work independently.

## Slash Commands

| Command | Purpose |
|---------|---------|
| `/codegen` | Delegate a task to cloud agent |
| `/cg-status` | Check status of agent runs |
| `/cg-logs` | View agent execution logs |
| `/cg-merge` | Merge PRs from agent runs |
| `/cg-settings` | Manage plugin settings |

## Key Principles

1. **One task = one agent run** — keep tasks focused and self-contained
2. **Prompts are everything** — agent quality depends on prompt quality
3. **Verify, don't trust** — always review agent output before merging
4. **Monitor actively** — check agent status, don't fire-and-forget
5. **Fail fast** — stop on blockers, don't let agents spin

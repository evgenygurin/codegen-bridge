# Skills Guide

Codegen Bridge includes **10 skills** that provide structured workflows for AI assistants. Skills are discovered automatically by the `SkillsDirectoryProvider` from the `skills/` directory.

## Skill Overview

| Skill | Directory | User-Invocable | Description |
|-------|-----------|----------------|-------------|
| `using-codegen-bridge` | `using-codegen-bridge/` | No (SessionStart) | Meta-skill: skill map, decision tree, superpowers integration |
| `codegen-delegation` | `codegen-delegation/` | No (auto) | Task delegation with prompt templates |
| `executing-via-codegen` | `executing-via-codegen/` | Yes | Execute plans via cloud agents task-by-task |
| `agent-monitoring` | `agent-monitoring/` | No (auto) | Monitor runs with verification gates |
| `pr-management` | `pr-management/` | No (auto) | Manage PRs created by agents |
| `bulk-delegation` | `bulk-delegation/` | Yes | Batch-delegate independent tasks |
| `run-analytics` | `run-analytics/` | Yes | Analyze agent run performance |
| `debugging-failed-runs` | `debugging-failed-runs/` | Yes | 4-phase systematic debugging |
| `prompt-crafting` | `prompt-crafting/` | Yes | Writing effective agent prompts |
| `reviewing-agent-output` | `reviewing-agent-output/` | Yes | Two-stage review (spec + quality) |

**User-invocable** skills can be triggered directly by the user. **Auto** skills activate automatically when relevant tools are called.

---

## Meta-Skill: Using Codegen Bridge

**File:** `skills/using-codegen-bridge/SKILL.md`
**Invoked:** Automatically at session start via the SessionStart hook

This is the entry point skill that establishes context for the entire session. It provides:

### Decision Tree

```
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

### Key Principles

1. **One task = one agent run** — keep tasks focused
2. **Prompts are everything** — agent quality depends on prompt quality
3. **Verify, don't trust** — always review agent output before merging
4. **Monitor actively** — check agent status, don't fire-and-forget
5. **Fail fast** — stop on blockers, don't let agents spin

---

## Codegen Delegation

**File:** `skills/codegen-delegation/SKILL.md`
**Triggers:** When `codegen_create_run`, `codegen_start_execution`, or `codegen_resume_run` are called

The core delegation workflow:

### Flow

1. **Assess** — Is the task suitable for cloud delegation?
2. **Prepare** — Initialize execution context (for multi-step work)
3. **Build Prompt** — Use the prompt template with quality checklist
4. **Submit** — Call `codegen_create_run`
5. **Confirm** — Report run ID and web URL to user

### Prompt Quality Checklist

Before submitting any prompt:
- [ ] Self-contained — agent can work without other context
- [ ] Specific task — not vague but precise
- [ ] File paths included — exact paths, not "the auth file"
- [ ] Test command specified — exact command to run tests
- [ ] Acceptance criteria — how to know the task is done
- [ ] Scope bounded — "Do NOT modify files outside X"
- [ ] No local references — no localhost, no local file paths

### Prompt Templates

Located in `skills/codegen-delegation/templates/`:

| Template | Purpose |
|----------|---------|
| `task-prompt-template.md` | Single task prompt structure |
| `multi-step-prompt-template.md` | Task within a plan (includes previous task context) |

---

## Executing via Codegen

**File:** `skills/executing-via-codegen/SKILL.md`
**User-invocable:** Yes

The most comprehensive skill — orchestrates entire plan execution:

### Process

1. **Find the Plan** — Read plan file or discover from `docs/plans/`
2. **Review Plan** — Check for issues, parse tasks, initialize execution context
3. **Verify Access** — `codegen_list_repos`, optionally `codegen_check_integration_health`
4. **Execute Tasks** — For each task:
   - Build prompt with previous task summaries
   - Create agent run with `execution_id`
   - Monitor progress (background or manual polling)
   - **Two-stage review gate** before proceeding
5. **Final Summary** — List all PRs, show analytics

### Two-Stage Review Gate

Between tasks, the skill performs:

**Stage 1: Spec Compliance** (always)
- All task items addressed?
- Correct files modified?
- Tests passing?
- PR created?

**Stage 2: Code Quality** (for risky tasks)
- No debug artifacts?
- No hardcoded secrets?
- Diff size proportional to scope?

### Bulk vs. Sequential

- **Independent tasks** → Use `codegen_bulk_create_runs`
- **Dependent tasks** → Execute sequentially with context passing

---

## Agent Monitoring

**File:** `skills/agent-monitoring/SKILL.md`
**Triggers:** When `codegen_get_run`, `codegen_get_logs`, `codegen_list_runs`, or `codegen_get_execution_context` are called

### Status Interpretation

| Status | User-Facing Summary | Next Action |
|--------|-------------------|-------------|
| `queued` | "Agent is queued..." | Poll in 30s |
| `running` | "Agent is working..." | Poll in 30s |
| `completed` | "Agent completed!" | Show results + PR |
| `failed` | "Agent failed." | Show error, offer resume |
| `paused` | "Agent waiting for input..." | Show question, get response |

### Verification Gates

**Iron Law: NO COMPLETION CLAIMS WITHOUT FRESH EVIDENCE.**

| Claim | Required Evidence |
|-------|-------------------|
| "Agent completed" | `status: completed` from API |
| "Tests pass" | Test command output in logs showing PASS |
| "PR created" | PR URL in `pull_requests` array |
| "No errors" | Full log scan showing no error outputs |

---

## Debugging Failed Runs

**File:** `skills/debugging-failed-runs/SKILL.md`
**User-invocable:** Yes

**Iron Law: NO RETRY WITHOUT DIAGNOSIS.**

### 4-Phase Approach

**Phase 1: Gather Evidence**
- Get run details and full logs
- Check integration health

**Phase 2: Classify the Failure**

| Category | Symptoms | Fix |
|----------|----------|-----|
| A: Prompt Problem | Wrong task, wrong files | Rewrite prompt |
| B: Test/Build Failure | Code written but tests fail | Add test expectations |
| C: Environment | No logs, permission errors | Fix integrations |
| D: Scope Too Large | Timeout, excessive reading | Break into smaller tasks |
| E: Agent Loop | Repeating same action | Provide explicit direction |
| F: Merge Conflict | Git errors | Fresh run from main |

**Phase 3: Build Fix Strategy** — Targeted fix based on classification

**Phase 4: Execute and Verify** — Apply fix, monitor, max 2 retries

---

## Prompt Crafting

**File:** `skills/prompt-crafting/SKILL.md`
**User-invocable:** Yes

### Prompt Structure

```markdown
## Context
- Repository: <owner/repo-name>
- Tech stack: <languages, frameworks>
- Architecture: <brief description>
- Relevant files: <exact file paths>

## Task
<Clear, specific description>

## Requirements
- <Acceptance criteria>
- <Test expectations>
- <PR requirements>

## Constraints
- Create a branch from main
- Use conventional commit messages
- Run tests: <exact command>
- Do NOT modify files outside: <scope list>
```

### Anti-Patterns

| Bad Prompt | Better Prompt |
|-----------|---------------|
| "Fix the bug" | "Fix timeout in `app/upload.py:45` — stream file instead of `read()`" |
| "Improve performance" | "Add database index on `users.email` — queries in `app/auth/login.ts` are slow" |
| "Refactor the codebase" | "Extract auth middleware from 5 route files into `src/middleware/auth.ts`" |

### Prompt Size Guidelines

| Complexity | Size | Notes |
|-----------|------|-------|
| Simple | 200-500 chars | Context + task + constraints |
| Medium | 500-2000 chars | Full template with requirements |
| Complex | 2000-4000 chars | Detailed steps + file list |
| Too complex | >4000 chars | Split into multiple tasks |

---

## Reviewing Agent Output

**File:** `skills/reviewing-agent-output/SKILL.md`
**User-invocable:** Yes

**Iron Law: NO MERGE WITHOUT REVIEW.**

### Two-Stage Review

**Stage 1: Spec Compliance** — Did the agent do what was asked?
- [ ] Task completed — all items addressed
- [ ] Correct files modified
- [ ] Tests written and passing
- [ ] PR created with descriptive title
- [ ] Scope respected

**Stage 2: Code Quality** — Is the code good enough?
- [ ] No obvious bugs
- [ ] Error handling present
- [ ] No security issues
- [ ] Consistent style
- [ ] No debug artifacts
- [ ] Tests are meaningful

### Review Depth by Task Risk

| Task Type | Review Depth |
|-----------|-------------|
| Simple model/schema | Stage 1 only |
| API with auth | Both stages |
| Multi-file refactor | Both stages |
| Tests only | Stage 1 only |
| Database migration | Both stages |

---

## Bulk Delegation

**File:** `skills/bulk-delegation/SKILL.md`
**User-invocable:** Yes

For delegating multiple independent tasks simultaneously.

**Rule:** If reversing the task order produces the same result, use bulk delegation.

### Process
1. Analyze task independence
2. Group into batches
3. Build self-contained prompts for each
4. Submit batch via `codegen_bulk_create_runs`
5. Monitor all runs
6. Report batch summary with analytics

---

## PR Management

**File:** `skills/pr-management/SKILL.md`
**Triggers:** When PR-related tools are called

Manages the full PR lifecycle: review state, ban/unban checks, remove Codegen from PRs.

---

## Run Analytics

**File:** `skills/run-analytics/SKILL.md`
**User-invocable:** Yes

Analyze agent performance metrics: success rates, durations, token usage, failure patterns, and trends.

---

## See Also

- **[[Tools-Reference]]** — Tools that skills orchestrate
- **[[Commands-Reference]]** — Quick-access slash commands
- **[[Agents]]** — Task agents that implement delegation

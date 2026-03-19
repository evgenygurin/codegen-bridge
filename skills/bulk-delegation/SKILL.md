---
name: bulk-delegation
description: Batch-delegate multiple independent tasks to Codegen cloud agents in a single call. Uses codegen_bulk_create_runs for parallel execution. Best for plans where tasks have no inter-dependencies.
user-invocable: true
---

# Bulk Delegation via Codegen

## Overview

Delegate multiple independent tasks to Codegen agents simultaneously using `codegen_bulk_create_runs`. Instead of creating runs one at a time, submit an entire batch and monitor them in parallel.

**Core principle:** Independent tasks run faster in parallel. Dependent tasks must stay sequential.

**Announce at start:** "I'm using the bulk-delegation skill to launch multiple agent runs in parallel."

## When to Use

| Scenario | Use Bulk? | Reason |
|----------|-----------|--------|
| 5 independent feature tasks | Yes | No dependencies, all can run at once |
| Multi-step refactor (A depends on B) | No | Sequential dependencies |
| Same change across 3 repos | Yes | Identical tasks, different repos |
| Test suite for 4 modules | Yes | Each module is independent |
| Feature + its tests | No | Tests depend on feature code |

**Rule of thumb:** If reversing the task order would produce the same result, use bulk delegation.

## Prerequisites

- `CODEGEN_API_KEY` and `CODEGEN_ORG_ID` environment variables set
- Repository registered in Codegen organization
- `codegen_bulk_create_runs` tool available
- Recommended: `codegen_check_integration_health` to verify platform health before batch

## The Process

### Step 1: Analyze Task Independence

Review the plan and classify each task:

1. **Independent** — no input from other tasks, can run in any order
2. **Dependent** — needs output or artifacts from another task

Group independent tasks into a batch. Dependent tasks must run sequentially after their prerequisites complete.

Example plan with 5 tasks:
```text
Task 1: Add user model           [independent]
Task 2: Add product model        [independent]
Task 3: Add order model          [depends on 1, 2]
Task 4: Add user API endpoints   [depends on 1]
Task 5: Add product API tests    [depends on 2]
```

Batches:
- **Batch 1:** Tasks 1, 2 (fully independent)
- **Batch 2:** Tasks 4, 5 (after batch 1 completes, these are independent of each other)
- **Batch 3:** Task 3 (depends on both 1 and 2)

### Step 2: Pre-Flight Checks

1. Call `codegen_check_integration_health` to verify platform connectivity
2. Call `codegen_list_repos` to confirm repository access
3. If using execution context: `codegen_start_execution(mode="plan", plan_tasks=[...])`

### Step 3: Build Task Prompts

For each task in the batch, compose a self-contained prompt:

```text
## Context
- Repository: <name>
- Tech stack: <languages, frameworks>
- This task is part of a batch — other tasks run in parallel

## Your Task
<Full task description — all steps verbatim from the plan>

## Constraints
- Create a branch from main
- Run tests after changes
- Use conventional commit messages
- Create a PR when done
- Do NOT modify files outside your task scope
```

Each prompt must be **fully self-contained** — agents in a batch cannot see each other's work.

### Step 4: Submit the Batch

```text
codegen_bulk_create_runs(
  tasks=[
    {
      prompt: <task_1_prompt>,
      execution_id: <ctx_id>,
      repo_id: <detected_or_explicit>
    },
    {
      prompt: <task_2_prompt>,
      execution_id: <ctx_id>,
      repo_id: <detected_or_explicit>
    }
  ],
  agent_type="claude_code"
)
```

The response returns all run IDs at once. Report to user:
- Number of runs created
- Run IDs and web URLs
- Estimated completion time (if available)

### Step 5: Monitor the Batch

Use `codegen_monitor_run_background` for each run, or poll manually:

**Background monitoring (preferred):**
```text
# For each run_id from the batch
codegen_monitor_run_background(run_id=<id>, execution_id=<ctx_id>)
```

You will be notified as each run reaches a terminal state.

**Manual polling (fallback):**
```text
# Poll all runs in a round-robin fashion
for each run_id:
    codegen_get_run(run_id=<id>, execution_id=<ctx_id>)
sleep 30
```

Report progress as runs complete:
```text
Batch progress: 2/5 runs completed
  Run #101: Add user model        [completed] PR #40
  Run #102: Add product model     [completed] PR #41
  Run #103: Add order service     [running]
  Run #104: Add user endpoints    [running]
  Run #105: Add product tests     [queued]
```

### Step 6: Handle Failures

If a run in the batch fails:

1. Report the failure immediately — do not wait for other runs
2. Offer options: "Resume this run, skip it, or stop all remaining?"
3. Other runs in the batch continue independently unless user says stop
4. If stopping all: call `codegen_stop_run` for each still-running run

### Step 7: Batch Summary

After all runs complete, use `codegen_get_run_analytics` for aggregate metrics:
- Total runs, success/failure counts
- Average duration per run
- All PR links collected in one list

## Limits and Recommendations

| Aspect | Recommendation |
|--------|---------------|
| Batch size | 3-8 tasks per batch (API and sandbox limits) |
| Prompt size | Keep under 4000 chars per task |
| Timeout | 10 minutes per run; escalate to user after |
| Concurrency | Codegen manages sandbox allocation automatically |

## Error Recovery

| Error | Action |
|-------|--------|
| Partial batch failure (some created, some failed) | Report which succeeded; retry failed ones individually |
| HTTP 429 (rate limit) | Wait 60 seconds, retry the batch |
| HTTP 402 (billing limit) | Stop immediately, report to user |
| All runs fail with same error | Likely a systemic issue — check integration health |

## Remember

- Only batch tasks that are truly independent
- Each prompt must be self-contained — no cross-references between batch tasks
- Monitor all runs, not just the first one
- Report failures immediately, don't wait for the full batch
- Use `codegen_get_run_analytics` after completion for batch performance summary
- If tasks have dependencies, use the **executing-via-codegen** skill for sequential execution
- Add "Do NOT modify files outside your task scope" to prevent merge conflicts between parallel PRs

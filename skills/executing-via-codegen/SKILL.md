---
name: executing-via-codegen
description: Use when executing implementation plans via Codegen cloud agents instead of locally. Delegates each task as a separate Codegen agent run, monitors progress, and handles blockers. Drop-in replacement for superpowers:executing-plans — works with the same plan format.
user-invocable: true
---

# Executing Plans via Codegen

## Overview

Load plan, delegate each task to a Codegen cloud agent, monitor until done, report results.

**Core principle:** One task = one agent run. You orchestrate, Codegen executes.

**Announce at start:** "I'm using the executing-via-codegen skill to execute this plan via Codegen cloud agents."

## Prerequisites

- `CODEGEN_API_KEY` and `CODEGEN_ORG_ID` environment variables set
- Repository registered in Codegen organization
- MCP tools available: `codegen_create_run`, `codegen_get_run`, `codegen_get_logs`, `codegen_resume_run`, `codegen_stop_run`, `codegen_start_execution`, `codegen_get_execution_context`, `codegen_get_agent_rules`

### v0.6 Tools (Optional, Recommended)

These tools enhance the execution workflow but are not required:

- `codegen_check_integration_health` — verify integrations before running (Step 2)
- `codegen_bulk_create_runs` — batch-create runs for independent tasks (Step 3 alternative)
- `codegen_monitor_run_background` — background monitoring with progress callbacks (Step 3c alternative)
- `codegen_get_run_analytics` — analytics after all runs complete (Step 5 enhancement)

## The Process

### Step 0: Find the Plan

1. If a plan path was provided, read it
2. Otherwise, look for the most recent plan in `docs/plans/` (pattern: `YYYY-MM-DD-*.md`)
3. If no plan found, ask the user for the path
4. The plan may contain a superpowers header like:
   ```text
   > **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
   ```

   This is fine — executing-via-codegen is the cloud alternative. Proceed normally.

### Step 1: Load and Review Plan

1. Read the plan file
2. Review critically — check for:
   - Missing prerequisites or dependencies between tasks
   - Unclear task descriptions that an agent might misinterpret
   - Tasks that need repo-specific knowledge
3. If concerns: raise with user before starting
4. Parse all tasks from the plan (`### Task N: ...`)
5. Extract plan header (Goal, Architecture, Tech Stack, any context sections)
6. Initialize context with `codegen_start_execution(mode="plan", plan_tasks=[...])` — this returns an `execution_id` that tracks all tasks and their state

### Step 2: Verify Codegen Access

1. Call `codegen_list_repos` to verify the repository is accessible
2. Note the `repo_id` for subsequent calls (or let auto-detect handle it)
3. If repo not found: ask user to check Codegen setup
4. **(v0.6)** Call `codegen_check_integration_health` to verify webhooks, GitHub app, and API connectivity are healthy before creating runs. If any check fails, surface it to the user before proceeding.

### Step 2b: Select Model (Optional)

1. Call `codegen_get_models` to see available models
2. Show options to user: "Which model for agent runs? (default = org default)"
3. Use selected model for all runs, or let each run use the default

### Step 3: Execute Each Task

#### Bulk Delegation (v0.6, Independent Tasks Only)

If the plan contains tasks that are **independent** (no inter-task dependencies), consider using `codegen_bulk_create_runs` to launch them all at once:

```text
codegen_bulk_create_runs(
  tasks=[
    {prompt: <task_1_prompt>, execution_id: <ctx_id>},
    {prompt: <task_2_prompt>, execution_id: <ctx_id>},
    ...
  ],
  agent_type="claude_code"
)
```

This returns all run IDs at once and is faster than sequential creation. Skip to Step 3c for monitoring. See the **bulk-delegation** skill for details.

If tasks have dependencies (Task 2 needs Task 1's output), use sequential execution below.

#### Sequential Execution

For each task in the plan:

**a. Build the prompt:**

Use the `delegate_task` prompt template as base, then compose:

```bash
## Context
[Plan header: Goal, Architecture, Tech Stack]

Previously completed tasks:
- Task 1: [one-line summary of result]
- Task 2: [one-line summary of result]

## Your Task
[Full text of current task from plan — all steps verbatim]

## Constraints
- Create a branch from main (or the current default branch)
- Run tests after each step
- Commit with conventional commit messages
- Create a PR when done
```

**b. Create the agent run:**

```text
codegen_create_run(
  prompt=<composed prompt>,
  execution_id=<ctx_id>,
  repo_id=<detected or explicit>,
  agent_type="claude_code"
)
```

The `execution_id` enables auto-enrichment — the run prompt is automatically enriched with execution context (goal, completed tasks, previous results).

If a model was selected in Step 2b, pass `model=<selected>`.

**c. Monitor progress:**

**(v0.6 preferred)** Use `codegen_monitor_run_background(run_id=<id>, execution_id=<ctx_id>)` to start background monitoring. This automatically polls, detects status transitions, and reports progress without manual sleep loops. You will be notified when the run reaches a terminal state.

**Manual polling (fallback):** Poll every 30 seconds:

```bash
sleep 30
```

Then call `codegen_get_run(run_id=<id>, execution_id=<ctx_id>)`. The `execution_id` enables auto-parsing — run results are automatically parsed and stored in the execution context. Check the `status` field:

| Status | Action |
|--------|--------|
| `running` | Continue polling. Show: "Task N still running..." |
| `queued` | Continue polling. Show: "Task N queued..." |
| `completed` | Go to step d |
| `failed` | Go to step e |
| `paused` | Go to step f |

**Max polling:** 10 minutes per task. After 10 min, show status and ask user.

**d. On completion:**

1. Call `codegen_get_logs(run_id, limit=20)` to review what happened
2. Call `codegen_get_run(run_id, execution_id=<ctx_id>)` to check for PRs
3. Report to user:
   - What the agent did (from logs summary)
   - PR link (if created)
   - Any warnings from logs
4. Mark task as completed in TodoWrite

**e. On failure:**

1. Call `codegen_get_logs(run_id, limit=30)` to see error details
2. Show error logs to user
3. Ask: "Resume with fix instructions, skip this task, or stop?"
4. If resume: `codegen_resume_run(run_id, prompt=<user guidance>)`
5. If skip: mark task as skipped, continue to next
6. If stop: `codegen_stop_run(run_id)` if still running, then halt

**f. On pause (agent needs input):**

1. Call `codegen_get_logs(run_id, limit=10)` to see what agent is asking
2. Show the agent's question/blocker to user
3. Get user's response
4. `codegen_resume_run(run_id, prompt=<user response>)`
5. Resume polling

### Step 4: Report Between Tasks

After each task completes, use `codegen_get_execution_context` for a progress report:
- Show what was done
- Show PR link if created
- Show current progress (N/M tasks completed) from the execution context
- Say: "Ready for next task, or do you want to review first?"

### Step 5: Final Summary

After all tasks, use the `execution_summary` prompt to generate a final report:
- List all completed tasks with PR links
- Show any skipped/failed tasks
- Total agent runs created
- Suggest: "All PRs created. Review them on GitHub and merge when ready."
- Offer: "Want to use superpowers:finishing-a-development-branch to handle merging?"

**(v0.6)** Call `codegen_get_run_analytics` to enrich the summary with:
- Average run duration and token usage
- Success/failure rates across all tasks
- Performance trends compared to previous executions
- Recommendations for prompt or workflow improvements

See the **run-analytics** skill for interpretation guidance.

## Differences from Local Execution

| Aspect | executing-plans (local) | executing-via-codegen (cloud) |
|--------|------------------------|-------------------------------|
| Where | Your terminal | Codegen cloud sandbox |
| Output | Files on disk | PRs on GitHub |
| Branch | Git worktree required | Codegen creates branch |
| Review | Local diff | PR diff on GitHub |
| Batch size | 3 tasks per batch | 1 task = 1 agent run |
| Monitoring | Direct stdout | codegen_get_logs |
| Cancel | Ctrl+C | codegen_stop_run |
| Context | Manual prompt building | Auto-enriched via execution_id |

## When to Stop and Ask

**STOP immediately when:**
- HTTP 402 — billing limit reached (tell user)
- HTTP 403 — check API key / org_id
- Agent fails repeatedly (>2 retries)
- User requests stop
- Plan has critical gaps

## Error Recovery

If `codegen_create_run` returns HTTP error:
- 429: Wait 60 seconds, retry once
- 402: "Codegen billing limit reached. Cannot continue."
- 500+: Retry once, then report error

If polling times out (10 min):
- Show last known status
- Ask: "Agent still running. Wait longer, check logs, or cancel?"

## Remember
- One task = one agent run (or use `codegen_bulk_create_runs` for independent tasks)
- Include full task text in prompt (not file references)
- Include previous task summaries for context
- Use `execution_id` with `codegen_create_run` and `codegen_get_run` for automatic context enrichment and parsing
- Prefer `codegen_monitor_run_background` over manual sleep loops when available
- Poll with `sleep 30` between checks (fallback if background monitoring unavailable)
- Always show PR links when available
- Use `codegen_stop_run` for cancellation — don't just stop polling
- Use `codegen_get_execution_context` for progress tracking
- Use `codegen_check_integration_health` before starting a batch of runs
- Use `codegen_get_run_analytics` after completion for performance insights
- Stop on blockers, don't guess

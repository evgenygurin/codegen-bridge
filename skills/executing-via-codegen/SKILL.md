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
- MCP tools available: `codegen_create_run`, `codegen_get_run`, `codegen_get_logs`, `codegen_resume_run`, `codegen_stop_run`

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

### Step 2: Verify Codegen Access

1. Call `codegen_list_repos` to verify the repository is accessible
2. Note the `repo_id` for subsequent calls (or let auto-detect handle it)
3. If repo not found: ask user to check Codegen setup

### Step 2b: Select Model (Optional)

1. Call `codegen_get_models` to see available models
2. Show options to user: "Which model for agent runs? (default = org default)"
3. Use selected model for all runs, or let each run use the default

### Step 3: Execute Each Task

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
  repo_id=<detected or explicit>,
  agent_type="claude_code"
)
```

If a model was selected in Step 2b, pass `model=<selected>`.

**c. Monitor progress:**

Poll every 30 seconds:

```bash
sleep 30
```

Then call `codegen_get_run(run_id=<id>)`. Check the `status` field:

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
2. Call `codegen_get_run(run_id)` to check for PRs
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

After each task completes:
- Show what was done
- Show PR link if created
- Show current progress (N/M tasks)
- Say: "Ready for next task, or do you want to review first?"

### Step 5: Final Summary

After all tasks:
- List all completed tasks with PR links
- Show any skipped/failed tasks
- Total agent runs created
- Suggest: "All PRs created. Review them on GitHub and merge when ready."
- Offer: "Want to use superpowers:finishing-a-development-branch to handle merging?"

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
- One task = one agent run (NOT batching)
- Include full task text in prompt (not file references)
- Include previous task summaries for context
- Poll with `sleep 30` between checks
- Always show PR links when available
- Use `codegen_stop_run` for cancellation — don't just stop polling
- Stop on blockers, don't guess

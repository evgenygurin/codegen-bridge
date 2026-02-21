---
name: agent-monitoring
description: Monitor running Codegen agents — poll status, review logs, detect blockers, and surface progress. Triggered when codegen_get_run, codegen_get_logs, codegen_list_runs, or codegen_get_execution_context tools are invoked.
user-invocable: false
---

# Agent Monitoring

## Overview

Monitor Codegen agent runs in real time. This skill activates when checking agent status, reviewing execution logs, or tracking multi-task execution progress. It interprets raw agent output into actionable summaries for the user.

**Core principle:** Poll, interpret, summarize, suggest next action.

## When This Skill Activates

This skill is invoked by the model when any of these MCP tools are called:
- `codegen_get_run` — checking a specific run's status
- `codegen_get_logs` — viewing execution logs
- `codegen_list_runs` — browsing recent runs
- `codegen_get_execution_context` — checking multi-task progress

## Status Interpretation

### Run Status Reference

| Status | Meaning | User-Facing Summary | Next Action |
|---|---|---|---|
| `queued` | Waiting for sandbox | "Agent is queued, waiting for a sandbox..." | Poll again in 30s |
| `running` | Actively executing | "Agent is working on the task..." | Poll again in 30s |
| `completed` | Finished successfully | "Agent completed! Here's what it did..." | Show results + PR link |
| `failed` | Errored out | "Agent failed. Here's what went wrong..." | Show error, offer resume |
| `paused` | Needs human input | "Agent is waiting for your input..." | Show question, get response |

### Polling Strategy

When monitoring a running agent:

1. **Initial check:** Call `codegen_get_run(run_id)` immediately
2. **If still running:** Wait 30 seconds, then poll again

```bash
sleep 30
```

3. **Continue polling** until terminal status (`completed`, `failed`) or timeout
4. **Timeout:** After 10 minutes of polling, stop and report:
   - "Agent has been running for 10 minutes. Still active."
   - Offer: "Wait longer, check logs, or cancel?"

### Interpreting Results

On `completed`:
1. Call `codegen_get_logs(run_id, limit=20)` for a summary of what happened
2. Check `pull_requests` in the run result for PR links
3. Report to user:
   - Brief summary of changes made
   - PR link (if created) with title and branch name
   - Files changed (from parsed logs if available)
   - Test results (if logged)
4. Suggest: "Review the PR and merge when ready"

On `failed`:
1. Call `codegen_get_logs(run_id, limit=30)` to see the error
2. Look for:
   - Error messages in `tool_output` fields
   - Failed commands in the log sequence
   - The last agent thought before failure
3. Report to user:
   - What the agent was trying to do
   - The specific error or failure point
   - Suggested fix or workaround
4. Offer: "Resume with fix instructions, or create a new run?"

On `paused`:
1. Call `codegen_get_logs(run_id, limit=10)` to see the agent's question
2. Look for the most recent `thought` — this usually contains the question
3. Present the agent's question to the user clearly
4. After getting user input: `codegen_resume_run(run_id, prompt=<user response>)`

## Log Analysis

### Reading Logs

Call `codegen_get_logs(run_id, limit=<N>)` with appropriate limits:

| Scenario | Recommended limit | Reason |
|---|---|---|
| Quick status check | 5 | Just the latest activity |
| Post-completion review | 20 | Enough for a summary |
| Debugging a failure | 30 | Need error context |
| Full audit trail | 100 | Complete history |

Use `reverse=True` (default) for newest-first, or `reverse=False` for chronological order.

### Log Entry Fields

Each log entry may contain:
- `thought` — the agent's reasoning (most useful for understanding intent)
- `tool_name` — which tool was called (e.g., `Edit`, `Bash`, `Read`)
- `tool_input` — what was passed to the tool (may contain file paths, commands)
- `tool_output` — the tool's result (truncated to 500 chars)
- `message_type` — entry classification
- `created_at` — timestamp

### Summarizing Logs for Users

When presenting logs to the user, focus on:

1. **What was done:** Group by action type (file edits, command runs, reads)
2. **Key decisions:** Extract from `thought` fields — why the agent chose an approach
3. **Test outcomes:** Look for `Bash` tool calls with test commands
4. **Errors:** Highlight any failed tool calls or error outputs
5. **PR creation:** Note when `gh pr create` or similar commands appear

Format as a concise summary, not raw log dumps:
```
Agent completed in 12 steps:
- Modified 3 files: src/auth.py, tests/test_auth.py, src/models.py
- Ran tests: 45 passed, 0 failed
- Created PR #42: "feat: add JWT authentication"
```

## Execution Context Monitoring

For multi-task executions, use `codegen_get_execution_context(execution_id)` to get:
- Overall progress: N of M tasks completed
- Per-task status: which tasks are done, running, pending, or failed
- Run IDs for each task (to drill into specific logs)

Present as a progress dashboard:
```
Execution: "Implement auth system" (3/5 tasks completed)

Task 1: Add user model          [completed] PR #40
Task 2: Add JWT middleware       [completed] PR #41
Task 3: Add login endpoint       [completed] PR #42
Task 4: Add registration flow    [running]   Run #789
Task 5: Add password reset       [pending]
```

## Proactive Monitoring Tips

When the user has active runs:
- Offer to check status when conversation resumes
- After long pauses, proactively poll active runs
- If a run completes while discussing something else, mention it
- Track multiple concurrent runs if the user has several going

## Error Handling

| Error | Action |
|---|---|
| Run not found | Verify run ID; suggest `codegen_list_runs` to find it |
| No logs available | Run may be too new; wait and retry |
| Execution context not found | May have expired; check with specific `execution_id` |
| Pagination needed | Use `cursor` from previous response's `next_cursor` |

## Remember

- Poll with `sleep 30` between status checks — don't flood the API
- Always show PR links prominently when they exist
- Summarize logs into actionable insights, don't dump raw entries
- On failure, provide the specific error and a suggested next step
- On pause, clearly present the agent's question to the user
- For multi-task executions, show overall progress context
- Timeout after 10 minutes of polling and ask the user what to do
- Use `codegen_stop_run` for cancellation if the user wants to abort

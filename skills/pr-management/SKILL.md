---
name: pr-management
description: Manage pull requests created by Codegen agents — review status, edit state, ban/unban checks, and remove Codegen from PRs. Triggered when codegen_edit_pr, codegen_ban_run, codegen_unban_run, or codegen_remove_from_pr tools are invoked.
user-invocable: false
---

# PR Management via Codegen

## Overview

Manage the lifecycle of pull requests created by Codegen agent runs. This skill handles reviewing PR state, changing PR status, controlling CI/CD check processing, and removing Codegen from PRs when needed.

**Core principle:** Surface PR status clearly, confirm destructive actions, provide next steps.

## When This Skill Activates

This skill is invoked by the model when any of these MCP tools are called:
- `codegen_edit_pr` / `codegen_edit_pr_simple` — changing PR state
- `codegen_ban_run` — banning checks and stopping agents on a PR
- `codegen_unban_run` — re-enabling checks on a PR
- `codegen_remove_from_pr` — removing Codegen from a PR entirely

It also assists when the user discusses PRs created by agent runs discovered via:
- `codegen_get_run` — checking run results that include PR links
- `codegen_list_runs` — browsing recent runs for their PR output

## PR State Management

### Viewing PR Status

When a user asks about a PR from an agent run:

1. Call `codegen_get_run(run_id=<id>)` to get run details
2. Check `pull_requests` in the response for PR links
3. Report: PR URL, title, branch name, current state
4. If the run is still in progress, report that and suggest waiting

### Changing PR State

Available states for `codegen_edit_pr` / `codegen_edit_pr_simple`:

| State | When to use |
|---|---|
| `open` | Reopen a closed PR |
| `closed` | Close a PR without merging |
| `draft` | Convert to draft for further work |
| `ready_for_review` | Mark as ready after draft iteration |

**Flow:**

1. Confirm the user's intent: "You want to close PR #123?"
2. Call the appropriate tool:
   - Use `codegen_edit_pr_simple(pr_id=<id>, state=<state>)` when you only have the PR ID
   - Use `codegen_edit_pr(repo_id=<id>, pr_id=<id>, state=<state>)` when you have both IDs
3. Report the result: success/failure, new state, URL
4. Suggest next steps based on the action taken

### Banning Checks (Stopping All Agents on a PR)

Use `codegen_ban_run` when:
- Agent is stuck in a loop on CI/CD checks
- User wants to stop all automated processing on a PR
- PR needs manual intervention without agent interference

**This is a destructive action.** Always confirm unless `confirmed=True`.

After banning:
- All current agents on the PR are stopped
- Future CI/CD check suite events will not trigger new agents
- Tell the user: "Codegen agents are stopped and future checks are disabled for this PR. Use unban to re-enable."

### Unbanning Checks

Use `codegen_unban_run` when:
- User fixed the issue and wants automated checks to resume
- Ban was applied by mistake

After unbanning:
- Future CI/CD events will be processed normally again
- Tell the user: "Checks are re-enabled. New CI/CD events will trigger agent processing."

### Removing Codegen from a PR

Use `codegen_remove_from_pr` when:
- User wants to fully disconnect Codegen from a specific PR
- PR should be handled entirely manually going forward

**This is a destructive action.** Always confirm unless `confirmed=True`.

This is functionally equivalent to banning but uses clearer naming for the user's intent.

## Common Workflows

### After Agent Run Completes

1. `codegen_get_run(run_id)` to check status and get PR link
2. Report: "Agent completed. PR created: [link]. Ready for review."
3. If user wants changes: suggest resuming the run or creating a new one
4. If user wants to close: `codegen_edit_pr_simple(pr_id, state="closed")`

### Agent Stuck on PR

1. User reports agent keeps running on a PR
2. `codegen_ban_run(run_id)` to stop all agents and prevent re-triggers
3. Report: "All agents stopped and future checks disabled."
4. Offer: "Want me to unban later when you're ready?"

### PR Needs More Work

1. `codegen_edit_pr_simple(pr_id, state="draft")` to mark as draft
2. `codegen_resume_run(run_id, prompt=<fix instructions>)` to resume the agent
3. Monitor progress, then mark ready: `codegen_edit_pr_simple(pr_id, state="ready_for_review")`

## Error Handling

| Error | Action |
|---|---|
| PR not found | Verify the PR ID; call `codegen_get_run` to get correct PR info |
| Permission denied | User needs write access to the repository |
| Run not found | Verify run ID; call `codegen_list_runs` to find correct one |
| Already in target state | Inform user: "PR is already in that state" |

## Remember

- Always confirm destructive actions (ban, remove-from-pr, close) before executing
- Include PR URL in all responses so the user can navigate directly
- After state changes, suggest logical next steps
- When banning, explain that both current agents and future triggers are affected
- Use `codegen_edit_pr_simple` when you only have a PR ID (more common)
- Use `codegen_edit_pr` when you have both repo ID and PR ID (RESTful compliance)

---
name: debugging-failed-runs
description: Use when debugging failed, stuck, or misbehaving Codegen agent runs — systematic 4-phase approach. Triggers on agent run failures, timeouts, or unexpected results. Analogous to superpowers systematic-debugging but for cloud agents.
user-invocable: true
---

# Debugging Failed Agent Runs

## Overview

When a Codegen agent run fails, gets stuck, or produces wrong results — do NOT immediately retry with the same prompt. Systematically diagnose the root cause first.

**Iron Law: NO RETRY WITHOUT DIAGNOSIS.**

Retrying a failed run with the same prompt wastes time and credits. Understand WHY it failed, fix the cause, THEN retry.

**Announce at start:** "I'm using the debugging-failed-runs skill to diagnose this agent failure."

## When This Skill Activates

- Agent run status is `failed`
- Agent run has been `running` for >10 minutes without progress
- Agent completed but produced wrong/incomplete output
- Agent is in a retry loop (multiple failures on same task)
- User says "the agent failed" or "the run is stuck"

## Phase 1: Gather Evidence

**DO NOT GUESS. Read the logs first.**

### Step 1: Get Run Details

```text
codegen_get_run(run_id=<id>)
```

Record: status, duration, error message (if any), PR links.

### Step 2: Read Full Logs

```text
codegen_get_logs(run_id=<id>, limit=50, reverse=false)
```

Read chronologically (oldest first). Look for:

| Signal | What it means |
|--------|---------------|
| Last `thought` before failure | Agent's final reasoning — often reveals the actual problem |
| Repeated tool calls to same file | Agent stuck in a loop |
| `Bash` with test commands + failures | Tests failing — read the test output |
| `Bash` with git commands + errors | Branch/merge conflicts |
| No logs at all | Sandbox setup failure — infrastructure issue |
| Logs stop abruptly | Timeout or crash |

### Step 3: Check Environment

```text
codegen_check_integration_health
```

Rule out infrastructure issues: GitHub app connected? Webhooks working? API accessible?

## Phase 2: Classify the Failure

Based on evidence from Phase 1, classify into one of these categories:

### Category A: Prompt Problem

**Symptoms:** Agent did the wrong thing, misunderstood the task, worked on wrong files.

**Evidence:** Agent thoughts show confusion about requirements. Tool calls target unexpected files.

**Fix:** Rewrite the prompt with clearer instructions. See `prompt-crafting` skill.

### Category B: Test/Build Failure

**Symptoms:** Agent wrote code but tests fail. Build errors in logs.

**Evidence:** `Bash` tool calls show test/build output with errors.

**Fix:** Include test expectations in prompt. Add "if tests fail, read the error and fix" instruction. Ensure dependencies are available in sandbox.

### Category C: Environment/Infrastructure

**Symptoms:** No logs, immediate failure, permission errors, git clone failures.

**Evidence:** `codegen_check_integration_health` shows issues. Logs show auth errors or missing repos.

**Fix:** Fix integration issues first. Check: repo registered? GitHub app installed? API key valid?

### Category D: Scope Too Large

**Symptoms:** Agent times out. Logs show extensive file reading. Agent tries to refactor everything.

**Evidence:** Duration >10 min. Hundreds of log entries. Agent touches many unrelated files.

**Fix:** Break task into smaller pieces. Add "Do NOT modify files outside: [list]" constraint.

### Category E: Agent Loop

**Symptoms:** Agent repeats same action. Makes a change, reverts it, makes it again.

**Evidence:** Logs show cyclic pattern: edit → test → fail → revert → edit (same thing).

**Fix:** Provide explicit fix direction. "The error is X. Fix it by doing Y, not Z."

### Category F: Merge Conflict / Stale Branch

**Symptoms:** Git operations fail. Agent can't push. Merge conflicts.

**Evidence:** Git error messages in logs.

**Fix:** Create a fresh run from updated main branch. Don't resume — start clean.

## Phase 3: Build Fix Strategy

Based on classification:

### For Prompt Problems (A):
1. Review original prompt
2. Identify the ambiguity or missing context
3. Rewrite prompt — use `prompt-crafting` skill
4. Create new run (don't resume — stale context)

### For Test/Build Failures (B):
1. Extract the specific error from logs
2. Decide: can agent fix it with guidance, or is the task wrong?
3. If fixable: `codegen_resume_run(run_id, prompt="The test fails because X. Fix by Y.")`
4. If task is wrong: create new run with corrected task

### For Environment Issues (C):
1. Fix the infrastructure issue
2. Verify with `codegen_check_integration_health`
3. Create new run (don't resume — environment changed)

### For Scope Issues (D):
1. Split the original task into 2-3 smaller tasks
2. Add explicit file scope constraints
3. Use `executing-via-codegen` or `bulk-delegation` for the subtasks

### For Agent Loops (E):
1. Identify what the agent is cycling on
2. Provide explicit direction in resume prompt
3. `codegen_resume_run(run_id, prompt="Stop trying X. Instead, do Y because Z.")`
4. If loop persists after resume: `codegen_stop_run`, create fresh run with explicit approach

### For Merge/Git Issues (F):
1. `codegen_stop_run` if still running
2. Create new run with fresh branch from main
3. Add "Create a NEW branch from main, do not reuse existing branches" to prompt

## Phase 4: Execute and Verify

1. Apply the fix (new run or resume)
2. Monitor the new/resumed run: `codegen_get_run(run_id)`
3. On completion: verify the output actually addresses the original task
4. If it fails AGAIN with the SAME error:
   - **STOP.** Do not retry a third time.
   - The task may need fundamental rethinking
   - Consider: is this task suitable for cloud delegation at all?
   - Report to user with full diagnosis

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Retry immediately with same prompt | Diagnose first |
| Resume without reading logs | Always read logs before resuming |
| Blame "the agent" generically | Identify specific failure category |
| Create 5 retries in a row | Max 2 retries, then rethink |
| Ignore timeout as "flaky" | Timeout = scope too large or loop |
| Add more text to prompt hoping it helps | Identify what's MISSING, add only that |

## Escalation

If 2 retries fail with different errors each time, the task is likely:
- Too complex for a single agent run — split it
- Missing critical context — gather more info locally first
- Better done locally — some tasks don't suit cloud delegation

Report honestly: "This task failed twice with different errors. I recommend [splitting it / doing it locally / providing more context]."

## Remember

- **Logs first, always.** Never diagnose without reading logs.
- **Classify before fixing.** Different failure types need different fixes.
- **Max 2 retries.** After that, change approach entirely.
- **Fresh runs > resumes** for prompt problems and environment issues.
- **Resumes > fresh runs** for test failures and agent loops (context preserved).
- Track failures across tasks — if multiple tasks fail the same way, it's likely a systemic issue (environment, integration, or prompt pattern).

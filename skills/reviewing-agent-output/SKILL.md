---
name: reviewing-agent-output
description: Use when reviewing code and PRs created by Codegen agents — two-stage review process. Stage 1 checks spec compliance (did the agent do what was asked?). Stage 2 checks code quality (is the code good?). Triggers after agent runs complete.
user-invocable: true
---

# Reviewing Agent Output

## Overview

Agent-created code requires verification before merging. Trust but verify — agents complete most tasks correctly, but edge cases, misunderstandings, and quality issues slip through.

**Iron Law: NO MERGE WITHOUT REVIEW.**

Two-stage process:
1. **Spec Compliance** — did the agent do what was asked?
2. **Code Quality** — is the code good enough to merge?

**Announce at start:** "I'm using the reviewing-agent-output skill to review this agent's work."

## When This Skill Activates

- Agent run reaches `completed` status with a PR
- User asks to review an agent-created PR
- As part of `executing-via-codegen` workflow between tasks
- User says "check what the agent did" or "review the PR"

## Prerequisites

Before reviewing, gather the context:

1. **Run details:** `codegen_get_run(run_id)` — get status, PR links, summary
2. **Run logs:** `codegen_get_logs(run_id, limit=30, reverse=false)` — chronological activity
3. **Original prompt:** from execution context or conversation history — what was the agent asked to do?

## Stage 1: Spec Compliance Review

**Question: Did the agent do what was asked?**

### Checklist

- [ ] **Task completed** — all items from the original prompt are addressed
- [ ] **Correct files** — changes are in the expected files, no unexpected files modified
- [ ] **Tests written** — if the prompt asked for tests, they exist
- [ ] **Tests passing** — logs show test run with passes (not just "tests written")
- [ ] **PR created** — PR exists with descriptive title and body
- [ ] **Branch correct** — branched from the right base (usually main)
- [ ] **Scope respected** — no changes outside the specified scope

### How to Check

**From logs:**
- Look for `Bash` calls with test commands → check output for PASS/FAIL
- Look for `Edit`/`Write` calls → verify correct files were modified
- Look for `gh pr create` → verify PR was created

**From run result:**
- Check `pull_requests` array for PR links
- Check `summary` for agent's own description of what it did

### Spec Compliance Verdict

| Verdict | Meaning | Action |
|---------|---------|--------|
| **PASS** | All requirements met | Proceed to Stage 2 |
| **PARTIAL** | Some requirements met, some missing | Resume agent with specific missing items |
| **FAIL** | Wrong approach or major misunderstanding | Create new run with clarified prompt |
| **UNCLEAR** | Can't determine from logs alone | Need to read the actual PR diff |

If PARTIAL: `codegen_resume_run(run_id, prompt="You missed: [specific items]. Please complete them.")`

If FAIL: Use `debugging-failed-runs` skill to diagnose, then `prompt-crafting` for a better prompt.

## Stage 2: Code Quality Review

**Question: Is the code good enough to merge?**

Only proceed to Stage 2 if Stage 1 passed.

### Quality Checklist

- [ ] **No obvious bugs** — logic errors, off-by-one, null handling
- [ ] **Error handling** — errors caught and handled appropriately, not swallowed
- [ ] **No security issues** — no hardcoded secrets, no SQL injection, no XSS
- [ ] **Consistent style** — matches project conventions (naming, structure, patterns)
- [ ] **No unnecessary changes** — no random reformatting, no unrelated refactors
- [ ] **Tests are meaningful** — not just "it exists", tests cover real behavior
- [ ] **No debug artifacts** — no `console.log`, no commented-out code, no TODOs

### How to Check

**From logs (quick check):**
- Look for patterns suggesting issues:
  - `console.log` in `Edit` tool inputs
  - Hardcoded values that look like secrets
  - Very large diffs (agent may have over-modified)
  - Agent reverting its own changes (indecision)

**From PR (thorough check):**
- If PR URL is available, ask user to review the diff
- Or use `gh pr diff <number>` locally if repo is available
- Focus on: new code logic, test quality, error handling

### Quality Verdict

| Verdict | Meaning | Action |
|---------|---------|--------|
| **APPROVE** | Code is good to merge | Report to user, suggest merge |
| **MINOR** | Small issues, fixable by agent | Resume with specific fixes needed |
| **MAJOR** | Significant quality issues | New run with more guidance, or fix locally |
| **REJECT** | Fundamentally wrong approach | Close PR, rethink the task |

If MINOR: `codegen_resume_run(run_id, prompt="Quality issues to fix: [list specific issues]")`

If MAJOR: Consider whether a new run or local fix is more efficient.

## Review Report Format

Present review results to the user as:

```text
Agent Output Review — Run #<id>
================================

Stage 1: Spec Compliance — [PASS/PARTIAL/FAIL]
  [✓] Task completed
  [✓] Correct files modified
  [✓] Tests written and passing
  [✓] PR created: <link>
  [✗] Missing: <what's missing, if any>

Stage 2: Code Quality — [APPROVE/MINOR/MAJOR/REJECT]
  [✓] No obvious bugs
  [✓] Error handling present
  [✓] Consistent style
  [!] Minor: <issue description>

Recommendation: [Merge / Fix then merge / Rework / Reject]
```

## Review in Multi-Task Context

When reviewing as part of `executing-via-codegen` (between tasks):

1. **Quick review** — Stage 1 only for intermediate tasks (keep momentum)
2. **Full review** — Both stages for the final task or critical tasks
3. **Batch review** — After all tasks complete, full review of all PRs together

The goal is efficiency: don't spend 5 minutes reviewing every trivial task, but don't skip review for complex or risky tasks.

### Task Risk Assessment

| Task Type | Review Depth | Why |
|-----------|-------------|-----|
| Add simple model/schema | Stage 1 only | Low risk, easily verified |
| Add API endpoint with auth | Both stages | Security-sensitive |
| Refactor across files | Both stages | High risk of breaking things |
| Add/update tests only | Stage 1 only | Tests verify themselves |
| Database migration | Both stages | Hard to undo |
| UI component | Stage 1 + visual check | Need to see the output |

## Integration with Code Review Skills

If superpowers `requesting-code-review` skill is available:
- Use it for DEEP review of critical agent PRs
- It dispatches a code-reviewer subagent for thorough analysis
- Best for: final PR, complex changes, security-sensitive code

For routine reviews, this skill's two-stage process is sufficient and faster.

## Remember

- **Two stages:** spec compliance first, code quality second
- **Logs are your primary source** — read them before making judgments
- **Compare against the original prompt** — that's the spec
- **Don't merge without review** — even if the agent says "all tests pass"
- **Resume for minor fixes** — cheaper than creating a new run
- **New run for major issues** — stale context in a failed run hurts more than it helps
- **Risk-based depth** — full review for risky tasks, quick check for simple ones
- **Report clearly** — the user needs to make the merge decision

# Agents

Codegen Bridge includes **2 task agents** for Claude Code's `/task` delegation system. Agents are discovered automatically by the `AgentsProvider` from the `agents/` directory.

## Agent Overview

| Agent | File | Purpose |
|-------|------|---------|
| `codegen-delegator` | `agents/codegen-delegator.md` | Orchestrate task execution via cloud agents |
| `pr-reviewer` | `agents/pr-reviewer.md` | Review and analyze PRs from agent runs |

---

## Codegen Delegator

**File:** `agents/codegen-delegator.md`

A task-delegation agent that takes a coding task, delegates it to a Codegen cloud agent, monitors the run until completion, and reports the result.

### Available Tools

| Tool | Purpose |
|------|---------|
| `codegen_start_execution` | Initialize execution context |
| `codegen_create_run` | Create a new agent run |
| `codegen_get_run` | Poll run status and results |
| `codegen_get_logs` | View execution logs |
| `codegen_resume_run` | Resume paused runs |
| `codegen_stop_run` | Cancel runs |
| `codegen_list_runs` | List recent runs |
| `codegen_get_execution_context` | Get execution state |
| `codegen_get_agent_rules` | Fetch org rules |
| `codegen_list_repos` | List available repos |

### Workflow

1. **Prepare** — Receive task, verify repo access
2. **Initialize** — Create execution context (`mode="adhoc"`)
3. **Create Run** — Submit with `confirmed=true` (non-interactive subagent)
4. **Monitor** — Poll every 30s, timeout after 10 minutes
5. **Collect** — Get logs and PR links on completion
6. **Report** — Return structured summary

### Result Format

```markdown
## Task Result

**Status:** completed | failed
**Run ID:** <id>
**Web URL:** <url>

### Changes
- <summary of what was done>

### Pull Requests
- [PR #N: <title>](<url>) — <state>

### Notes
- <any warnings or follow-up items>
```

### Error Handling

| Error | Action |
|-------|--------|
| HTTP 402 | "Codegen billing limit reached" — stop |
| HTTP 403 | "Authentication error" — stop |
| HTTP 429 | Wait 60s, retry once |
| HTTP 500+ | Retry once, then report |
| Agent failure | Get logs, include error details |
| Agent paused | Report the blocker to caller |

### Key Rules

- Always pass `confirmed=true` (non-interactive subagent)
- Include full task context in prompts
- Never guess at missing information — report back and ask
- Always include PR links in results
- One task = one agent run

---

## PR Reviewer

**File:** `agents/pr-reviewer.md`

A code-review agent that reviews pull requests created by Codegen agent runs, analyzing changes for correctness and quality.

### Available Tools

| Tool | Purpose |
|------|---------|
| `codegen_get_run` | Get run details including PRs |
| `codegen_get_logs` | View execution logs |
| `codegen_list_runs` | Find relevant runs |
| `codegen_get_execution_context` | Get execution state |
| `codegen_get_agent_rules` | Get coding standards |
| `codegen_edit_pr` | Change PR state |
| `codegen_edit_pr_simple` | Change PR state (simplified) |

### Workflow

1. **Identify PR** — From run ID, execution ID, or recent runs
2. **Gather Context** — Run summary, logs, org rules
3. **Analyze Changes** — Correctness, quality, completeness, risks
4. **Build Review** — Structured feedback with severity levels
5. **Act** (optional) — Change PR state if requested
6. **Report** — Return structured review

### Review Format

```markdown
## PR Review: <PR title>

**PR:** <url>
**Run ID:** <id>
**Agent task:** <one-line summary>

### Verdict: APPROVE | REQUEST_CHANGES | NEEDS_DISCUSSION

### Summary
<2-3 sentence overview>

### What Was Done Well
- <positive observations>

### Issues Found
1. **[severity]** <issue description>
   - File: <path>
   - Suggestion: <how to fix>

### Test Coverage
- Tests run: yes/no
- Tests passed: yes/no/unknown
- New tests added: yes/no

### Files Changed
- <file list from parsed logs>

### Recommendations
- <actionable next steps>
```

### Severity Levels

| Level | Meaning |
|-------|---------|
| `[critical]` | Must fix before merge (bugs, security, data loss) |
| `[major]` | Should fix, significant quality concern |
| `[minor]` | Nice to fix, style or minor improvement |
| `[nit]` | Optional, subjective preference |

### Key Rules

- Never merge a PR — only review and optionally change state
- Be specific — cite file names and log entries
- Distinguish agent errors from legitimate choices
- If logs are insufficient, say so explicitly
- Always include the PR URL
- One review per PR unless re-review is requested

---

## See Also

- **[[Skills-Guide]]** — Skills that agents leverage
- **[[Tools-Reference]]** — Complete tool documentation
- **[[Commands-Reference]]** — Quick-access commands

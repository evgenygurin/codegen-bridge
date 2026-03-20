---
name: run-analytics
description: Use when analyzing Codegen agent run performance — interpret success rates, duration metrics, token usage, and trends via codegen_get_run_analytics. Best used after batch runs or for periodic performance review.
user-invocable: true
---

# Run Analytics

## Overview

Analyze the performance of Codegen agent runs — success rates, durations, token usage, and trends over time. Use after batch executions to evaluate results, or periodically to review agent effectiveness.

**Core principle:** Measure, interpret, recommend.

**Announce at start:** "I'm using the run-analytics skill to analyze agent run performance."

## When to Use

| Scenario | Trigger |
|----------|---------|
| After a bulk delegation batch completes | Review batch performance |
| After a multi-task plan execution finishes | Evaluate overall execution |
| User asks "how are my agents performing?" | Periodic performance review |
| Investigating why runs are slow or failing | Debugging performance issues |
| Comparing different prompting strategies | A/B testing agent behavior |

## Prerequisites

- `codegen_get_run_analytics` tool available
- At least one completed (or failed) agent run to analyze
- Recommended: `codegen_get_logs` for deeper analysis of specific runs

## The Process

### Step 1: Gather Analytics

Call `codegen_get_run_analytics` with the appropriate scope:

```text
# Analytics for a specific execution (batch or plan)
codegen_get_run_analytics(execution_id=<ctx_id>)

# Analytics for recent runs (time-based)
codegen_get_run_analytics(limit=20)

# Analytics for a specific repository
codegen_get_run_analytics(repo_id=<id>, limit=50)
```

### Step 2: Interpret the Results

#### Success Metrics

| Metric | Good | Concerning | Action |
|--------|------|------------|--------|
| Success rate | >80% | <60% | Review failed run logs for common errors |
| Average duration | <5 min | >15 min | Check prompt complexity or task scope |
| Retry rate | <10% | >30% | Prompts may be ambiguous |
| PR creation rate | ~100% of successes | <80% | Agents may be completing without PR |

#### Duration Analysis

Present durations in human-readable format:
```text
Run Performance (last 20 runs):
  Average duration:  4m 32s
  Fastest run:       1m 15s (Run #101 — simple model addition)
  Slowest run:      18m 44s (Run #108 — complex refactor)
  Median duration:   3m 50s
```

If the slowest run is >3x the median, it likely had a different scope or hit a blocker. Drill into it with `codegen_get_logs(run_id)`.

#### Token Usage

If token data is available:
```text
Token Usage:
  Average per run:   12,400 tokens
  Total (batch):    124,000 tokens
  Highest single:    38,200 tokens (Run #108)
```

High token usage relative to task complexity may indicate:
- Excessive exploration (agent reading too many files)
- Retry loops (agent hitting errors and retrying)
- Verbose prompts causing long context chains

#### Failure Patterns

When failures exist, categorize them:

| Pattern | Indicator | Recommendation |
|---------|-----------|----------------|
| Test failures | Agent completed code but tests fail | Add test expectations to prompt |
| Timeout | Run exceeded time limit | Break task into smaller pieces |
| Auth/permission errors | API/Git access failures | Check integration health |
| Merge conflicts | Branch conflicts with main | Rebase or use isolated branches |
| Prompt ambiguity | Agent did wrong thing | Improve prompt specificity |

### Step 3: Combine with Logs

For runs with unexpected metrics (very slow, very high tokens, failures):

1. Call `codegen_get_logs(run_id=<id>, limit=30)` for the specific run
2. Look for:
   - Long gaps between log entries (indicates blocking operations)
   - Repeated tool calls (indicates retry loops)
   - Error messages in tool outputs
3. Cross-reference with the analytics to build a complete picture

### Step 4: Present Recommendations

Based on the analysis, suggest concrete improvements:

**For low success rates:**
- "3 of 10 runs failed due to test errors. Consider adding expected test behavior to prompts."
- "2 runs timed out on the refactor task. Break it into 2 smaller tasks."

**For high durations:**
- "Runs averaging 12 minutes. The prompts include full file contents — use file paths instead."
- "Agent spent 8 minutes on file exploration. Add relevant file paths to the prompt context."

**For high token usage:**
- "Token usage is 3x higher than similar tasks. The agent is reading too many files."
- "Consider narrowing the task scope or providing more specific file paths."

**For trends:**
- "Success rate improved from 60% to 85% after prompt refinements in the last 2 batches."
- "Average duration increased by 40% this week — tasks may be growing in scope."

## Report Format

Present a complete analytics report as:

```text
Agent Run Analytics — Execution "Implement auth system"
========================================================

Overview:
  Total runs:     5
  Completed:      4 (80%)
  Failed:         1 (20%)
  Total duration: 22m 15s

Performance:
  Avg duration:   4m 27s
  Fastest:        2m 10s (Task 1: Add user model)
  Slowest:        8m 33s (Task 3: Add JWT middleware)

Results:
  Task 1: Add user model        [completed]  3m 12s  PR #40
  Task 2: Add login endpoint    [completed]  4m 45s  PR #41
  Task 3: Add JWT middleware    [completed]  8m 33s  PR #42
  Task 4: Add registration     [completed]  5m 45s  PR #43
  Task 5: Add password reset   [failed]     —       Test failures

Recommendations:
  - Task 5 failed due to missing test fixtures. Add setup instructions to prompt.
  - Task 3 took 2x average. JWT tasks may benefit from more specific guidance.
```

## Error Handling

| Error | Action |
|-------|--------|
| No runs found | Verify execution_id or adjust time range / limit |
| Analytics unavailable | Fall back to manual calculation from `codegen_list_runs` + `codegen_get_run` |
| Partial data (some runs still in progress) | Report available data, note in-progress runs |

## Remember

- Always present numbers in context — "4 minutes" means nothing without "average is 3 minutes"
- Categorize failures by root cause, not just count them
- Suggest actionable improvements, not just observations
- Combine analytics with log analysis for the full picture
- Compare against previous executions when possible to show trends
- Token usage is a proxy for agent effort — high usage is not always bad (complex tasks need more)

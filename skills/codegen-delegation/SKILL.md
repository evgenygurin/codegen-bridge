---
name: codegen-delegation
description: Automatically delegate tasks to Codegen cloud agents when user requests code changes, implementations, or fixes that should run remotely. Triggered when codegen_create_run or codegen_start_execution tools are invoked.
user-invocable: false
---

# Codegen Task Delegation

## Overview

Intelligently delegate coding tasks to Codegen cloud agents. This skill activates when a user asks for code changes that should be executed remotely rather than locally — refactors, feature implementations, bug fixes, or any task that benefits from isolated sandbox execution.

**Core principle:** Detect intent, prepare context, delegate, confirm.

## When This Skill Activates

This skill is invoked by the model when any of these MCP tools are called:
- `codegen_create_run` — creating a new agent run
- `codegen_start_execution` — initializing an execution context
- `codegen_resume_run` — resuming a paused agent

## Pre-Delegation Checklist

Before delegating, ensure:

1. **API access is configured** — `CODEGEN_API_KEY` and `CODEGEN_ORG_ID` environment variables are set
2. **Repository is registered** — call `codegen_list_repos` to verify the repo exists in the organization
3. **Task is well-scoped** — the prompt contains enough context for an agent working in isolation

## Delegation Flow

### Step 1: Assess the Task

Evaluate whether the task is suitable for cloud delegation:

| Good for delegation | Better done locally |
|---|---|
| Feature implementation | Quick one-line fix |
| Refactoring across files | Reading/exploring code |
| Bug fix with clear repro | Interactive debugging |
| Test suite additions | Configuration changes needing local env |
| Documentation generation | Tasks requiring local secrets/services |

If the task is better done locally, say so and handle it directly instead.

### Step 2: Prepare the Execution Context

For multi-step work, initialize an execution context first:

```
codegen_start_execution(
  execution_id=<unique_id>,
  goal=<user's goal>,
  mode="adhoc" or "plan",
  tasks=[{title, description}, ...],
  tech_stack=[...],
  architecture=<if known>
)
```

For single tasks, skip to Step 3.

### Step 3: Build and Submit the Prompt

Compose a clear, self-contained prompt for the agent:

```
## Context
- Repository: <name>
- Tech stack: <languages, frameworks>
- Relevant files: <if known>

## Task
<Detailed description of what needs to be done>

## Requirements
- <specific acceptance criteria>
- Run tests after changes
- Create a PR with descriptive title and body

## Constraints
- Create a branch from main
- Use conventional commit messages
- Do not modify unrelated files
```

Submit via:

```
codegen_create_run(
  prompt=<composed_prompt>,
  execution_id=<ctx_id if multi-step>,
  agent_type="claude_code"
)
```

### Step 4: Confirm Submission

After the run is created, report back to the user:
- Run ID and web URL for tracking
- What the agent will do (brief summary)
- How to check status: "Use `/cg-status` or ask me to check on it"

## Prompt Quality Guidelines

**Do:**
- Include full file paths when referencing specific files
- Describe the expected behavior, not just the change
- Mention related tests that should pass
- Include error messages if fixing a bug
- Provide architectural context for large changes

**Don't:**
- Reference local-only resources (localhost URLs, local file paths)
- Assume the agent has prior conversation context
- Include sensitive credentials in prompts
- Send vague one-liner prompts ("fix the bug")

## Error Handling

| Error | Action |
|---|---|
| No repository detected | Ask user which repo to use, or run `codegen_list_repos` |
| HTTP 402 (billing limit) | Tell user: "Codegen billing limit reached" |
| HTTP 403 (auth error) | Tell user to check API key and org ID |
| HTTP 429 (rate limit) | Wait 60 seconds, retry once |
| Prompt too vague | Ask user for more detail before submitting |

## Remember

- Always confirm with the user before creating a run (unless `confirmed=True`)
- Include enough context in the prompt for the agent to work independently
- Report the run ID and web URL so the user can track progress
- Suggest follow-up: checking status with `/cg-status` or viewing logs with `/cg-logs`
- For multi-task work, use execution contexts to maintain state across runs

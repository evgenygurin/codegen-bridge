# Multi-Step Prompt Template

Use this template when composing prompts for tasks that are part of a larger plan (via `executing-via-codegen`). Includes context from previous tasks.

```markdown
## Plan Context
- Goal: <overall plan goal — one sentence>
- Architecture: <plan-level architecture description>
- Tech stack: <from plan header>

## Previously Completed Tasks
- Task 1: <title> — <one-line summary of what was done, PR link if available>
- Task 2: <title> — <one-line summary>
(Include all completed tasks so the agent understands the current state)

## Your Task (Task N of M)
<Full text of the current task from the plan — all steps verbatim.
Do NOT summarize — include every detail from the plan.>

## Requirements
- All existing tests must still pass
- Add tests for new functionality
- Run tests: <exact test command>
- Create a PR with title: "<conventional commit>: <task description>"
- PR description should reference the plan and task number

## Constraints
- Create a branch from main (or current default branch)
- Use conventional commit messages
- Do NOT modify files outside the scope of this task
- If you encounter issues with code from previous tasks, note them in the PR but do NOT fix them
```

## Notes

- **Previous task summaries** give the agent context about the current codebase state
- **"Do NOT fix previous tasks"** prevents scope creep — each task is independently reviewable
- **Full task text** — never summarize, the plan author wrote specific steps for a reason

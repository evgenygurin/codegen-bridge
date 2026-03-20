# Task Prompt Template

Use this template when composing prompts for `codegen_create_run`. Fill in each section, then remove the template instructions.

```markdown
## Context
- Repository: <owner/repo-name>
- Tech stack: <primary language, framework, key libraries>
- Architecture: <brief description — e.g., "FastAPI + SQLAlchemy + PostgreSQL">
- Relevant files: <list exact file paths the agent should focus on>

## Task
<Clear, specific description of what needs to be done.
Include: what to create, what to modify, expected behavior.
For bug fixes: include the error message verbatim.>

## Requirements
- <Acceptance criterion 1 — what "done" looks like>
- <Acceptance criterion 2>
- Run tests after changes: <exact test command, e.g., "pytest tests/ -v">
- Create a PR with title: "<conventional commit format title>"

## Constraints
- Create a branch from main
- Use conventional commit messages
- Do NOT modify files outside: <scope — e.g., "src/auth/ and tests/auth/">
- <Any additional constraints>
```

## Guidelines

- **Self-contained:** Agent has NO prior context — include everything
- **Specific:** "Add validation to `app/forms/signup.tsx`" not "fix the form"
- **Bounded:** "Do NOT modify files outside X" prevents scope creep
- **Testable:** Include exact test command so agent can verify
- **Size:** Keep under 4000 chars. If larger, split into multiple tasks.

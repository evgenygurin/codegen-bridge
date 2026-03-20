---
name: prompt-crafting
description: Guide for writing effective prompts for Codegen cloud agents. Includes templates, anti-patterns, and optimization strategies. Auto-triggers when creating agent runs to ensure prompt quality.
user-invocable: true
---

# Prompt Crafting for Codegen Agents

## Overview

The quality of a Codegen agent run is directly proportional to the quality of its prompt. A vague prompt produces vague results. A precise prompt produces precise results.

**Core principle:** The agent works in an isolated sandbox with NO prior context. Everything it needs must be in the prompt.

## When This Skill Activates

- Before calling `codegen_create_run` — review prompt quality
- Before calling `codegen_bulk_create_runs` — review each prompt
- When a run fails due to misunderstanding (Category A from `debugging-failed-runs`)
- User asks "how do I write a better prompt for the agent?"

## The Prompt Structure

Every agent prompt should follow this structure:

```markdown
## Context
- Repository: <owner/repo-name>
- Tech stack: <languages, frameworks, key libraries>
- Architecture: <brief — e.g., "Next.js App Router + Prisma + PostgreSQL">
- Relevant files: <list of files the agent should focus on>

## Task
<Clear, specific description of what to do>

## Requirements
- <Specific acceptance criteria — what "done" looks like>
- <Test expectations — what tests should pass>
- <PR requirements — title format, description>

## Constraints
- Create a branch from main
- Use conventional commit messages (feat:, fix:, refactor:, etc.)
- Run tests after changes: <exact test command>
- Create a PR with descriptive title and body
- Do NOT modify files outside: <scope list>
```

## Prompt Quality Checklist

Before submitting any prompt, verify:

- [ ] **Self-contained** — agent can work without any other context
- [ ] **Specific task** — not "improve the code" but "add input validation to the signup form in `app/auth/signup.tsx`"
- [ ] **File paths included** — exact paths, not "the auth file"
- [ ] **Test command specified** — exact command to run tests
- [ ] **Acceptance criteria clear** — how to know the task is done
- [ ] **Scope bounded** — "Do NOT modify files outside X" for focused changes
- [ ] **No local references** — no `localhost:3000`, no `~/my-project/`, no local env vars

## Templates

### Template 1: Feature Implementation

```markdown
## Context
- Repository: acme/web-app
- Tech stack: Next.js 16, TypeScript, Prisma, PostgreSQL
- Architecture: App Router with Server Components, API routes in app/api/

## Task
Add a password reset flow to the authentication system.

Specifically:
1. Create a new API route `app/api/auth/reset-password/route.ts` that:
   - Accepts POST with `{ email: string }`
   - Generates a reset token (crypto.randomUUID())
   - Stores token in `password_reset_tokens` table with 1h expiry
   - Returns 200 (always, to prevent email enumeration)

2. Create a new page `app/(auth)/reset-password/page.tsx` with:
   - Email input form
   - Success message after submission
   - Link back to login

3. Add Prisma model for `PasswordResetToken` in `prisma/schema.prisma`

## Requirements
- All existing tests must still pass
- Add tests for the new API route (success + expired token + invalid token)
- PR title: "feat(auth): add password reset flow"

## Constraints
- Create branch from main
- Run tests: `npm test`
- Do NOT modify existing auth routes
- Do NOT send actual emails (just store the token)
```

### Template 2: Bug Fix

```markdown
## Context
- Repository: acme/api-service
- Tech stack: Python 3.12, FastAPI, SQLAlchemy
- The bug: Users report 500 errors when uploading files > 10MB

## Task
Fix the file upload timeout for large files.

The error from logs:

    httpx.ReadTimeout: timed out
    File "app/routes/upload.py", line 45, in upload_file

Root cause: The upload handler reads the entire file into memory before processing.

## Requirements
- Fix: Stream the file upload instead of loading into memory
- File `app/routes/upload.py` line ~45 — change `await file.read()` to streaming
- Add test: upload a 15MB file successfully
- Existing tests must pass

## Constraints
- Create branch from main
- Run tests: `pytest tests/ -v`
- Only modify `app/routes/upload.py` and `tests/test_upload.py`
```

### Template 3: Refactor

```markdown
## Context
- Repository: acme/backend
- Tech stack: Node.js, Express, TypeScript
- Current state: Authentication logic duplicated across 5 route files

## Task
Extract authentication into a shared middleware.

Files with duplicated auth logic:
- `src/routes/users.ts` (lines 12-28)
- `src/routes/orders.ts` (lines 8-24)
- `src/routes/products.ts` (lines 15-31)
- `src/routes/admin.ts` (lines 10-35)
- `src/routes/reports.ts` (lines 5-21)

Create `src/middleware/auth.ts` with:
- `requireAuth` middleware (verify JWT, attach user to req)
- `requireRole(role: string)` middleware (check user role)

Then replace duplicated code in all 5 files with middleware usage.

## Requirements
- All existing tests pass after refactor
- No behavior change — same auth logic, just extracted
- PR title: "refactor: extract auth middleware from route handlers"

## Constraints
- Create branch from main
- Run tests: `npm test`
- Do NOT change auth behavior — only move code
```

### Template 4: Parallel Task (for bulk delegation)

```markdown
## Context
- Repository: acme/monorepo
- Tech stack: TypeScript, Turborepo
- This task runs in parallel with other tasks — do NOT modify shared files

## Your Task
Add input validation to the user registration form in `packages/web/src/components/RegisterForm.tsx`.

Specifically:
- Email: valid email format (use zod schema)
- Password: min 8 chars, at least 1 number
- Name: 2-50 chars, no special characters
- Show inline errors below each field

## Requirements
- Add tests in `packages/web/src/components/__tests__/RegisterForm.test.tsx`
- All existing tests pass
- PR title: "feat(web): add registration form validation"

## Constraints
- Create branch from main
- Run tests: `cd packages/web && npm test`
- Do NOT modify files outside `packages/web/src/components/`
- Do NOT modify shared packages (other tasks may be working on them)
```

## Anti-Patterns

| Bad Prompt | Problem | Better Prompt |
|-----------|---------|---------------|
| "Fix the bug" | No context, no specifics | "Fix the timeout in `app/upload.py:45` — stream file instead of `read()`" |
| "Improve performance" | Vague scope | "Add database index on `users.email` column — queries in `app/auth/login.ts` are slow" |
| "Refactor the codebase" | Unbounded scope | "Extract auth middleware from 5 route files into `src/middleware/auth.ts`" |
| "Make it work like the PR says" | Agent can't see PRs | Include the requirements directly in the prompt |
| "Use the same pattern as UserService" | Agent needs to find it | "Follow the pattern in `src/services/UserService.ts` (constructor injection, async methods)" |
| "Update the tests" | Which tests? What behavior? | "Add test for 15MB file upload success in `tests/test_upload.py`" |

## Optimization Strategies

### For Faster Runs
- Provide exact file paths (agent spends less time searching)
- Include the exact test command (agent doesn't guess)
- Scope the task tightly (agent doesn't explore)

### For Higher Success Rates
- Include error messages verbatim (for bug fixes)
- Specify expected behavior, not just the change
- Add "if tests fail, read the error output and fix the issue"
- Add "if unsure about approach, check existing patterns in <file>"

### For Better PRs
- Specify PR title format
- Request conventional commits
- Ask for PR description that explains WHY, not just WHAT

## Prompt Size Guidelines

| Task Complexity | Recommended Prompt Size | Notes |
|----------------|------------------------|-------|
| Simple (one file, clear fix) | 200-500 chars | Just context + task + constraints |
| Medium (2-5 files, feature) | 500-2000 chars | Full template with requirements |
| Complex (refactor, multi-file) | 2000-4000 chars | Detailed steps + file list |
| Too complex (>4000 chars) | Split into multiple tasks | Use `executing-via-codegen` |

## Remember

- **Prompts are the #1 lever** for agent quality — invest time in them
- **Self-contained** — the agent has NO context beyond the prompt
- **Specific > verbose** — 10 precise words beat 100 vague ones
- **Include file paths** — the agent works faster when it knows where to look
- **Bound the scope** — "Do NOT modify files outside X" prevents scope creep
- **Test command always** — the agent should know how to verify its work
- **No local references** — the agent runs in a cloud sandbox, not your machine

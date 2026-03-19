"""Dynamic workflow prompts for advanced Codegen scenarios.

Extends the base prompt templates with:
- ``review_run``      — guided PR review after an agent run
- ``debug_run``       — structured debugging of a failed run
- ``multi_repo_task`` — coordinating work across multiple repositories
- ``code_review``     — thorough code review prompt for a PR
"""

from __future__ import annotations

from fastmcp import FastMCP

from bridge.icons import ICON_DEBUG, ICON_MULTI_REPO, ICON_REVIEW


def register_dynamic_prompts(mcp: FastMCP) -> None:
    """Register advanced workflow prompts on the given FastMCP server."""

    @mcp.prompt(icons=ICON_REVIEW)
    def review_run(run_id: str, focus_areas: str = "") -> str:
        """Create a prompt for reviewing an agent run and its outputs.

        Guides the user through reviewing the agent's PR, checking test
        results, and verifying the implementation against the original task.

        Args:
            run_id: The agent run ID to review.
            focus_areas: Optional comma-separated areas to focus on
                         (e.g. ``"tests,error-handling,performance"``).
        """
        parts = [
            f"# Review Agent Run #{run_id}\n",
            f"## Step 1 — Load Run Details\n"
            f"Use `codegen_get_run` with run_id={run_id} to get the run status, "
            f"prompt, and PR link.\n",
            "## Step 2 — Examine the PR\n"
            "If a PR was created, review the diff for:\n"
            "- Correctness: does the code do what was asked?\n"
            "- Tests: are they comprehensive and passing?\n"
            "- Style: does it follow project conventions?\n"
            "- Edge cases: are they handled?\n",
        ]
        if focus_areas:
            areas = [a.strip() for a in focus_areas.split(",")]
            parts.append("## Focus Areas\n" + "".join(f"- **{a}**\n" for a in areas))
        parts.append(
            "## Step 3 — Verdict\n"
            "Summarize findings and recommend: approve, request changes, "
            "or re-run with adjusted prompt.\n"
        )
        return "\n".join(parts)

    @mcp.prompt(icons=ICON_DEBUG)
    def debug_run(run_id: str, error_context: str = "") -> str:
        """Create a prompt for debugging a failed or paused agent run.

        Structures the debugging process: load logs, identify the failure
        point, check for common issues, and suggest a fix or re-run strategy.

        Args:
            run_id: The agent run ID to debug.
            error_context: Optional additional error context or stack trace.
        """
        parts = [
            f"# Debug Agent Run #{run_id}\n",
            f"## Step 1 — Load Logs\n"
            f"Use `codegen_get_logs` with run_id={run_id} to fetch log entries.\n"
            f"Also read `codegen://runs/{run_id}/logs` for the full history.\n",
            "## Step 2 — Identify Failure Point\n"
            "Look for:\n"
            "- Last successful log entry\n"
            "- Error messages or stack traces\n"
            "- Tool call failures (e.g. API timeouts, auth errors)\n"
            "- Resource exhaustion (context too large)\n",
        ]
        if error_context:
            parts.append(f"## Known Error Context\n```\n{error_context}\n```\n")
        parts.append(
            "## Step 3 — Root Cause Analysis\n"
            "Classify the failure:\n"
            "- **Transient**: network/timeout → retry with `codegen_resume_run`\n"
            "- **Auth**: permissions → check org settings and OAuth\n"
            "- **Logic**: bad prompt → refine and create new run\n"
            "- **Resource**: context overflow → break task into smaller pieces\n"
        )
        parts.append(
            "## Step 4 — Resolution\n"
            "Recommend one of:\n"
            "1. Resume the run (if paused and transient error)\n"
            "2. Create a new run with improved prompt\n"
            "3. Fix the underlying issue (e.g. missing permissions)\n"
        )
        return "\n".join(parts)

    @mcp.prompt(icons=ICON_MULTI_REPO)
    def multi_repo_task(
        repos: str,
        task_description: str,
        dependencies: str = "",
    ) -> str:
        """Create a prompt for coordinating work across multiple repositories.

        Structures a multi-repo workflow: identify repos, plan the
        dependency order, delegate sub-tasks, and track completion.

        Args:
            repos: Comma-separated list of repository names.
            task_description: What needs to be accomplished across repos.
            dependencies: Optional comma-separated dependency pairs
                          (e.g. ``"api→frontend,shared→api"``).
        """
        repo_list = [r.strip() for r in repos.split(",")]
        parts = [
            "# Multi-Repository Task\n",
            f"## Repositories ({len(repo_list)})\n" + "".join(f"- `{r}`\n" for r in repo_list),
            f"\n## Task\n{task_description}\n",
        ]
        if dependencies:
            dep_pairs = [d.strip() for d in dependencies.split(",")]
            parts.append(
                "## Dependency Order\n"
                + "".join(f"- {d}\n" for d in dep_pairs)
                + "\n*Process repos in dependency order.*\n"
            )
        parts.append(
            "## Workflow\n"
            "For each repository:\n"
            "1. Create a branch from the default branch\n"
            "2. Delegate the sub-task using `codegen_create_agent_run`\n"
            "3. Monitor with `codegen_list_runs`\n"
            "4. Once all runs complete, verify cross-repo compatibility\n"
            "5. Create PRs in dependency order\n"
        )
        parts.append(
            "## Completion Criteria\n"
            "- All agent runs completed successfully\n"
            "- All PRs created and passing CI\n"
            "- Cross-repo interfaces verified\n"
        )
        return "\n".join(parts)

    @mcp.prompt(icons=ICON_REVIEW)
    def code_review(
        repo_name: str,
        pr_number: str,
        focus_areas: str = "",
    ) -> str:
        """Create a prompt for thorough code review of a pull request.

        Args:
            repo_name: Repository name (e.g. ``"codegen-bridge"``).
            pr_number: The PR number to review.
            focus_areas: Optional comma-separated review focus areas.
        """
        parts = [
            f"# Code Review: {repo_name} PR #{pr_number}\n",
            "## Step 1 — Context\n"
            f"Review PR #{pr_number} in `{repo_name}`.\n"
            "Load the PR diff and understand the change set.\n",
            "## Step 2 — Review Checklist\n"
            "- [ ] **Correctness**: Does the code work as intended?\n"
            "- [ ] **Tests**: Are new/changed paths covered?\n"
            "- [ ] **Types**: Are type hints accurate and complete?\n"
            "- [ ] **Error handling**: Are edge cases handled gracefully?\n"
            "- [ ] **Performance**: Any obvious bottlenecks?\n"
            "- [ ] **Security**: No secrets, no unsafe inputs?\n"
            "- [ ] **Style**: Follows project conventions (ruff, mypy)?\n",
        ]
        if focus_areas:
            areas = [a.strip() for a in focus_areas.split(",")]
            parts.append("## Special Focus\n" + "".join(f"- **{a}**\n" for a in areas))
        parts.append(
            "## Step 3 — Feedback\n"
            "Provide line-level comments where applicable and an overall\n"
            "summary with: approve / request changes / needs discussion.\n"
        )
        return "\n".join(parts)

"""Build structured prompts for Codegen agents from execution context.

Provides helpers to assemble Codegen-specific prompt sections covering
platform capabilities, CLI tool hints, integration guidance, and
operational constraints.  The top-level ``build_task_prompt`` function
composes all sections into a single Markdown prompt.
"""

from __future__ import annotations

from bridge.context import ExecutionContext

_DISPLAY_NAMES: dict[str, str] = {
    "github": "GitHub",
    "linear": "Linear",
    "slack": "Slack",
}

# ── Codegen-specific content blocks ──────────────────────────────────

_CAPABILITIES_SECTION = (
    "## Codegen Platform Capabilities\n"
    "You are running as a Codegen cloud agent. Key capabilities:\n"
    "- **Sandboxed execution** — code runs in an isolated cloud sandbox, "
    "not on the user's machine.\n"
    "- **Git operations** — create branches, commit, push, and open PRs "
    "directly from the sandbox.\n"
    "- **Multi-language support** — the sandbox supports Python, "
    "TypeScript/JavaScript, Go, Rust, and more.\n"
    "- **CI awareness** — Codegen can detect and retry failed CI checks "
    "on your PRs.\n"
    "- **Context enrichment** — execution context (previous tasks, PRs, "
    "decisions) is provided automatically."
)

_CLI_HINTS_SECTION = (
    "## CLI Tool Hints\n"
    "When working with the Codegen platform, use these tools effectively:\n"
    "- `codegen_create_run` — delegate a task to a new agent run. "
    "Always include an `execution_id` for context tracking.\n"
    "- `codegen_get_run` — check status of an agent run. "
    "Pass `execution_id` for auto-parsed results.\n"
    "- `codegen_get_logs` — inspect agent activity and debug failures. "
    "Use `limit=20` for recent activity.\n"
    "- `codegen_resume_run` — provide guidance to a paused agent. "
    "Include clear, specific instructions.\n"
    "- `codegen_stop_run` — cancel a run that is stuck or no longer "
    "needed.\n"
    "- `codegen_list_runs` — see all recent runs and their statuses.\n"
    "- `codegen_start_execution` — initialize a multi-task execution "
    "plan for coordinated work.\n"
    "- `codegen_get_execution_context` — review overall progress "
    "across all tasks."
)

_INTEGRATION_HINTS: dict[str, str] = {
    "github": (
        "**GitHub** is connected. PRs will be created automatically. "
        "Use conventional commit messages and reference issues with "
        "`#<number>` in commit messages. Check PR status after each task."
    ),
    "linear": (
        "**Linear** is connected. Reference Linear issue IDs (e.g. "
        "`ENG-123`) in PR descriptions and commit messages so progress "
        "is tracked automatically."
    ),
    "slack": (
        "**Slack** is connected. Status updates can be posted to "
        "linked channels. Mention relevant team members for review "
        "requests."
    ),
}

_BEST_PRACTICES_CONTENT = """\
# Codegen Agent Best Practices

## Prompt Construction
- **Be specific:** Include exact file paths, function names, and expected behavior.
- **Provide context:** Share architecture decisions, tech stack, and completed work.
- **Set constraints:** Always specify branching strategy, test requirements, and PR expectations.
- **One task per run:** Each agent run should have a single, clear objective.

## Execution Patterns
- **Sequential tasks:** Use `execution_id` to chain tasks with shared context.
- **Context enrichment:** Previous task results (PRs, files changed, decisions) are \
automatically included when using execution context.
- **Error recovery:** When a run fails, review logs before resuming. Provide specific \
fix instructions, not vague guidance.
- **Polling cadence:** Check run status every 30 seconds. Set a 10-minute timeout per task.

## Code Quality
- Create a feature branch from the default branch (usually `main`).
- Run tests after every meaningful change.
- Use conventional commit messages (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`).
- Create a PR when the task is complete — include a clear title and description.

## Integration Tips
- **GitHub:** Reference issues with `#<number>`. Use PR descriptions to explain "why".
- **Linear:** Include issue IDs (e.g. `ENG-123`) in commits and PR descriptions.
- **Slack:** Post completion summaries to linked channels for team visibility.

## When to Pause
- Missing prerequisites or dependencies that cannot be resolved.
- Ambiguous requirements that could lead to incorrect implementation.
- External service failures (API errors, CI timeouts).
- Billing limits reached (HTTP 402).
- If blocked or unsure: **PAUSE and report the issue** — don't guess.
"""


# ── Public helpers ───────────────────────────────────────────────────


def build_capabilities_section() -> str:
    """Return Markdown section describing Codegen platform capabilities.

    Suitable for inclusion in agent prompts to inform the agent about the
    execution environment and available platform features.
    """
    return _CAPABILITIES_SECTION


def build_cli_hints() -> str:
    """Return Markdown section with CLI tool usage hints.

    Lists the key MCP tools with brief guidance on when and how to use
    each one effectively.
    """
    return _CLI_HINTS_SECTION


def build_integration_hints(integrations: dict[str, bool]) -> str:
    """Return Markdown section with tips for active integrations.

    Args:
        integrations: Mapping of integration name to enabled flag
            (e.g. ``{"github": True, "linear": False}``).

    Returns:
        A Markdown section with guidance for each *active* integration,
        or an empty string if none are active.
    """
    active = {k for k, v in integrations.items() if v}
    if not active:
        return ""
    lines: list[str] = ["## Integration Hints"]
    for name in sorted(active):
        hint = _INTEGRATION_HINTS.get(name)
        if hint:
            lines.append(f"\n{hint}")
        else:
            display = _DISPLAY_NAMES.get(name, name.replace("_", " ").title())
            lines.append(f"\n**{display}** is connected and available.")
    return "\n".join(lines)


def build_best_practices() -> str:
    """Return the full Codegen agent best-practices document.

    This content is also served as the ``codegen://prompts/best-practices``
    MCP resource.
    """
    return _BEST_PRACTICES_CONTENT


# ── Main prompt builder ──────────────────────────────────────────────


def build_task_prompt(ctx: ExecutionContext, task_index: int) -> str:
    """Build a full structured prompt for a Codegen agent.

    Generates a Markdown-formatted prompt that includes the goal, current task,
    tech stack, architecture, completed task history, capabilities, CLI hints,
    integrations, and operational constraints.

    Args:
        ctx: The full execution context containing plan metadata and tasks.
        task_index: Zero-based index of the task to build the prompt for.

    Returns:
        A structured Markdown string ready to be sent to an agent.
    """
    task = ctx.tasks[task_index]
    total = len(ctx.tasks)
    sections: list[str] = []

    sections.append(f"# Agent Task: {task.title}")
    sections.append(f"## Goal\n{ctx.goal}")

    if ctx.mode == "plan":
        sections.append(f"## Your Task (Task {task_index + 1} of {total})\n{task.description}")
    else:
        sections.append(f"## Your Task\n{task.description}")

    _add_tech_section(ctx, sections)

    if ctx.repo_structure:
        sections.append(f"## Repository Structure\n```\n{ctx.repo_structure}\n```")

    if ctx.agent_rules:
        sections.append(f"## Agent Rules (Organization)\n{ctx.agent_rules}")

    # Codegen-specific sections
    sections.append(build_capabilities_section())

    _add_completed_tasks(ctx, task_index, sections)
    _add_integrations(ctx, sections)

    integration_hints = build_integration_hints(ctx.integrations)
    if integration_hints:
        sections.append(integration_hints)

    sections.append(build_cli_hints())

    sections.append(
        "## Constraints\n"
        "- Create a branch from main (or the current default branch)\n"
        "- Run tests after each step\n"
        "- Commit with conventional commit messages\n"
        "- Create a PR when done\n"
        "- If blocked or unsure: PAUSE and report the issue (don't guess)"
    )

    return "\n\n".join(sections)


# ── Internal helpers ─────────────────────────────────────────────────


def _add_tech_section(ctx: ExecutionContext, sections: list[str]) -> None:
    """Append architecture and tech stack section if data is present."""
    parts: list[str] = []
    if ctx.architecture:
        parts.append(f"**Architecture:** {ctx.architecture}")
    if ctx.tech_stack:
        parts.append(f"**Tech Stack:** {', '.join(ctx.tech_stack)}")
    if parts:
        sections.append("## Architecture & Tech Stack\n" + "\n".join(parts))


def _add_completed_tasks(ctx: ExecutionContext, current_index: int, sections: list[str]) -> None:
    """Append a summary of previously completed/failed tasks."""
    completed = [t for t in ctx.tasks[:current_index] if t.status in ("completed", "failed")]
    if not completed:
        return
    lines: list[str] = ["## Previously Completed Tasks"]
    for t in completed:
        lines.append(f'\n### Task {t.index + 1}: "{t.title}" ({t.status})')
        if t.run_id:
            lines.append(f"- **Run ID:** {t.run_id}")
        if t.report:
            r = t.report
            lines.append(f"- **Summary:** {r.summary}")
            if r.web_url:
                lines.append(f"- **Web URL:** {r.web_url}")
            for pr in r.pull_requests:
                lines.append(f"- **PR:** [{pr.title}]({pr.url}) (#{pr.number}, {pr.state})")
            if r.files_changed:
                lines.append(f"- **Files changed:** {', '.join(r.files_changed)}")
            if r.key_decisions:
                lines.append("- **Key decisions:** " + "; ".join(r.key_decisions))
            if r.agent_notes:
                lines.append(f"- **Agent notes:** {r.agent_notes}")
    sections.append("\n".join(lines))


def _add_integrations(ctx: ExecutionContext, sections: list[str]) -> None:
    """Append active integrations section."""
    active = {k: v for k, v in ctx.integrations.items() if v}
    if not active:
        return
    lines: list[str] = ["## Integrations & Cross-References"]
    for name in sorted(active):
        display = _DISPLAY_NAMES.get(name, name.replace("_", " ").title())
        lines.append(f"\n### {display}\nAvailable and connected.")
    sections.append("\n".join(lines))

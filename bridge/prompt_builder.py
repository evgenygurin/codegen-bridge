"""Build structured prompts for Codegen agents from execution context."""

from __future__ import annotations

from bridge.context import ExecutionContext

_DISPLAY_NAMES: dict[str, str] = {
    "github": "GitHub",
    "linear": "Linear",
    "slack": "Slack",
}


def build_task_prompt(ctx: ExecutionContext, task_index: int) -> str:
    """Build a full structured prompt for a Codegen agent.

    Generates a Markdown-formatted prompt that includes the goal, current task,
    tech stack, architecture, completed task history, integrations, and
    operational constraints.

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

    _add_completed_tasks(ctx, task_index, sections)
    _add_integrations(ctx, sections)

    sections.append(
        "## Constraints\n"
        "- Create a branch from main (or the current default branch)\n"
        "- Run tests after each step\n"
        "- Commit with conventional commit messages\n"
        "- Create a PR when done\n"
        "- If blocked or unsure: PAUSE and report the issue (don't guess)"
    )

    return "\n\n".join(sections)


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

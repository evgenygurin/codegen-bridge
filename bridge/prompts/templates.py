"""Prompt templates for common Codegen workflows."""

from __future__ import annotations

from fastmcp import FastMCP

from bridge.icons import ICON_DELEGATE, ICON_MONITOR, ICON_SUMMARY, ICON_TEMPLATE


def register_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompts on the given FastMCP server."""

    @mcp.prompt(icons=ICON_DELEGATE)
    def delegate_task(task_description: str, context: str = "") -> str:
        """Create a prompt for delegating a task to a Codegen agent."""
        parts = []
        if context:
            parts.append(f"## Context\n{context}\n")
        parts.append(f"## Task\n{task_description}\n")
        parts.append(
            "## Constraints\n"
            "- Create a branch from main (or the current default branch)\n"
            "- Run tests after each step\n"
            "- Commit with conventional commit messages\n"
            "- Create a PR when done\n"
        )
        return "\n".join(parts)

    @mcp.prompt(icons=ICON_MONITOR)
    def monitor_runs() -> str:
        """Prompt for checking status of all active agent runs."""
        return (
            "List all active Codegen agent runs using codegen_list_runs. "
            "For any run with status 'running' or 'queued', show its progress. "
            "For 'paused' runs, show what the agent needs. "
            "For 'completed' runs, show PR links if available."
        )

    @mcp.prompt(icons=ICON_TEMPLATE)
    def build_task_prompt_template(
        goal: str, task_description: str, context: str = ""
    ) -> str:
        """Build a structured prompt for delegating a task to a Codegen agent."""
        parts = [
            f"# Agent Task\n\n## Goal\n{goal}",
            f"\n## Your Task\n{task_description}",
        ]
        if context:
            parts.append(f"\n## Context\n{context}")
        parts.append(
            "\n## Constraints\n"
            "- Create a branch from main\n"
            "- Run tests after each step\n"
            "- Commit with conventional commit messages\n"
            "- Create a PR when done\n"
            "- If blocked: PAUSE and report"
        )
        return "\n".join(parts)

    @mcp.prompt(icons=ICON_SUMMARY)
    def execution_summary() -> str:
        """Prompt for generating a final summary of an execution."""
        return (
            "Use codegen_get_execution_context to load the full execution state. "
            "Then summarize:\n"
            "1. All completed tasks with PR links\n"
            "2. Any failed/skipped tasks with reasons\n"
            "3. Total agent runs created\n"
            "4. Key decisions made across all tasks\n"
            "5. Suggest: review PRs on GitHub and merge when ready"
        )

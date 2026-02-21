"""System-prompt templates for sampling requests.

Each function returns a plain string — the *system prompt* passed to
``ctx.sample(system_prompt=...)``.  Keeping these as pure functions
makes them trivially testable and easy to evolve.
"""

from __future__ import annotations

# ── Summary prompts ──────────────────────────────────────────────────


def system_prompt_run_summary() -> str:
    """System prompt for summarising an agent run."""
    return (
        "You are a technical summariser for a software engineering AI agent platform. "
        "Given the raw run data (status, result text, PR info, and optional parsed logs), "
        "produce a concise, actionable summary in Markdown.\n\n"
        "Guidelines:\n"
        "- Lead with a one-sentence status verdict.\n"
        "- List created PRs with links.\n"
        "- Highlight key files changed and important decisions.\n"
        "- Mention test results if available.\n"
        "- Keep it under 300 words.\n"
        "- Do NOT invent information that is not in the input."
    )


def system_prompt_execution_summary() -> str:
    """System prompt for summarising a full execution context."""
    return (
        "You are summarising a multi-task execution plan for a software engineering project. "
        "You will receive the full execution context in JSON format.\n\n"
        "Produce a Markdown summary that includes:\n"
        "1. Overall goal and current status.\n"
        "2. Per-task breakdown: title, status, PR links, key decisions.\n"
        "3. Aggregate statistics (tasks completed/failed/pending, total files changed).\n"
        "4. Actionable next steps or recommendations.\n\n"
        "Be factual and concise — no longer than 500 words."
    )


# ── Prompt-generation prompts ────────────────────────────────────────


def system_prompt_task_prompt_generator() -> str:
    """System prompt for generating a task prompt for a Codegen agent."""
    return (
        "You are a prompt engineer for AI coding agents. "
        "Given a high-level goal, task description, and optional context "
        "(tech stack, architecture, previously completed tasks), "
        "generate a detailed, actionable prompt for the agent.\n\n"
        "The prompt should:\n"
        "- Be specific and self-contained.\n"
        "- Include acceptance criteria.\n"
        "- Reference relevant files/modules if context is provided.\n"
        "- End with clear constraints (branch from main, run tests, commit conventionally).\n"
        "- Use Markdown formatting.\n\n"
        "Output ONLY the generated prompt — no meta-commentary."
    )


# ── Analysis prompts ─────────────────────────────────────────────────


def system_prompt_log_analysis() -> str:
    """System prompt for analysing agent execution logs."""
    return (
        "You are a senior engineer reviewing AI agent execution logs. "
        "Identify:\n"
        "1. What the agent accomplished (files changed, PRs created).\n"
        "2. Any errors, retries, or unusual patterns.\n"
        "3. Whether tests passed or failed.\n"
        "4. Suggestions for improving the agent's approach.\n\n"
        "Be concise and structured. Use bullet points."
    )

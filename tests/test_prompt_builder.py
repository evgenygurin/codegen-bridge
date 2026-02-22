"""Tests for structured prompt builder."""

from __future__ import annotations

from bridge.context import (
    ExecutionContext,
    PRInfo,
    TaskContext,
    TaskReport,
)
from bridge.prompt_builder import (
    build_best_practices,
    build_capabilities_section,
    build_cli_hints,
    build_integration_hints,
    build_task_prompt,
)


def _make_context(**overrides) -> ExecutionContext:
    defaults = {
        "id": "test",
        "mode": "plan",
        "goal": "Build auth system",
        "status": "active",
        "tech_stack": ["Python", "FastAPI"],
        "tasks": [TaskContext(index=0, title="Task 1", description="Create User model")],
    }
    defaults.update(overrides)
    return ExecutionContext(**defaults)


class TestBuildTaskPrompt:
    def test_includes_goal(self):
        ctx = _make_context()
        prompt = build_task_prompt(ctx, task_index=0)
        assert "Build auth system" in prompt

    def test_includes_task_description(self):
        ctx = _make_context()
        prompt = build_task_prompt(ctx, task_index=0)
        assert "Create User model" in prompt

    def test_includes_task_number(self):
        ctx = _make_context(
            tasks=[
                TaskContext(index=0, title="T1", description="First"),
                TaskContext(index=1, title="T2", description="Second"),
            ]
        )
        prompt = build_task_prompt(ctx, task_index=1)
        assert "Task 2 of 2" in prompt

    def test_includes_tech_stack(self):
        ctx = _make_context(tech_stack=["Python", "FastAPI", "PostgreSQL"])
        prompt = build_task_prompt(ctx, task_index=0)
        assert "Python" in prompt
        assert "FastAPI" in prompt

    def test_includes_agent_rules(self):
        ctx = _make_context(agent_rules="Use conventional commits\nAdd type hints")
        prompt = build_task_prompt(ctx, task_index=0)
        assert "conventional commits" in prompt

    def test_includes_completed_tasks(self):
        ctx = _make_context(
            tasks=[
                TaskContext(
                    index=0,
                    title="Setup DB",
                    description="Create tables",
                    status="completed",
                    run_id=99,
                    report=TaskReport(
                        summary="Created User table",
                        web_url="https://codegen.com/run/99",
                        pull_requests=[
                            PRInfo(
                                url="https://github.com/o/r/pull/5",
                                number=5,
                                title="feat: add user table",
                                state="merged",
                            )
                        ],
                        files_changed=["models/user.py", "migrations/001.py"],
                        key_decisions=["Used UUID primary keys"],
                    ),
                ),
                TaskContext(index=1, title="Add auth", description="Add login endpoint"),
            ]
        )
        prompt = build_task_prompt(ctx, task_index=1)
        assert "Setup DB" in prompt
        assert "Created User table" in prompt
        assert "pull/5" in prompt
        assert "models/user.py" in prompt
        assert "UUID primary keys" in prompt

    def test_includes_integrations(self):
        ctx = _make_context(integrations={"github": True, "linear": True, "slack": False})
        prompt = build_task_prompt(ctx, task_index=0)
        assert "GitHub" in prompt or "github" in prompt
        assert "Linear" in prompt or "linear" in prompt

    def test_includes_constraints(self):
        ctx = _make_context()
        prompt = build_task_prompt(ctx, task_index=0)
        assert "Constraints" in prompt
        assert "branch" in prompt.lower()

    def test_includes_architecture(self):
        ctx = _make_context(architecture="Modular monolith with service layer")
        prompt = build_task_prompt(ctx, task_index=0)
        assert "Modular monolith" in prompt

    def test_includes_repo_structure(self):
        ctx = _make_context(repo_structure="src/\n  app/\n  tests/")
        prompt = build_task_prompt(ctx, task_index=0)
        assert "src/" in prompt

    def test_adhoc_mode_works(self):
        ctx = ExecutionContext(
            id="adhoc-1",
            mode="adhoc",
            goal="Fix the login bug",
            status="active",
            tasks=[TaskContext(index=0, title="Fix the login bug", description="Fix it")],
        )
        prompt = build_task_prompt(ctx, task_index=0)
        assert "Fix the login bug" in prompt

    def test_includes_capabilities_section(self):
        ctx = _make_context()
        prompt = build_task_prompt(ctx, task_index=0)
        assert "Codegen Platform Capabilities" in prompt
        assert "Sandboxed execution" in prompt

    def test_includes_cli_hints(self):
        ctx = _make_context()
        prompt = build_task_prompt(ctx, task_index=0)
        assert "CLI Tool Hints" in prompt
        assert "codegen_create_run" in prompt

    def test_includes_integration_hints_when_active(self):
        ctx = _make_context(integrations={"github": True, "linear": True})
        prompt = build_task_prompt(ctx, task_index=0)
        assert "Integration Hints" in prompt
        assert "conventional commit" in prompt
        assert "ENG-123" in prompt

    def test_no_integration_hints_when_none_active(self):
        ctx = _make_context(integrations={"github": False})
        prompt = build_task_prompt(ctx, task_index=0)
        assert "Integration Hints" not in prompt

    def test_section_ordering(self):
        """Capabilities, integrations, CLI hints, and constraints appear in order."""
        ctx = _make_context(integrations={"github": True})
        prompt = build_task_prompt(ctx, task_index=0)
        cap_pos = prompt.index("Codegen Platform Capabilities")
        cli_pos = prompt.index("CLI Tool Hints")
        con_pos = prompt.index("## Constraints")
        assert cap_pos < cli_pos < con_pos


class TestBuildCapabilitiesSection:
    def test_returns_nonempty_string(self):
        result = build_capabilities_section()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_heading(self):
        result = build_capabilities_section()
        assert "## Codegen Platform Capabilities" in result

    def test_mentions_sandboxed_execution(self):
        result = build_capabilities_section()
        assert "Sandboxed execution" in result

    def test_mentions_git_operations(self):
        result = build_capabilities_section()
        assert "Git operations" in result

    def test_mentions_ci_awareness(self):
        result = build_capabilities_section()
        assert "CI awareness" in result

    def test_mentions_context_enrichment(self):
        result = build_capabilities_section()
        assert "Context enrichment" in result

    def test_mentions_multi_language(self):
        result = build_capabilities_section()
        assert "Multi-language" in result


class TestBuildCliHints:
    def test_returns_nonempty_string(self):
        result = build_cli_hints()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_heading(self):
        result = build_cli_hints()
        assert "## CLI Tool Hints" in result

    def test_mentions_create_run(self):
        result = build_cli_hints()
        assert "codegen_create_run" in result

    def test_mentions_get_run(self):
        result = build_cli_hints()
        assert "codegen_get_run" in result

    def test_mentions_get_logs(self):
        result = build_cli_hints()
        assert "codegen_get_logs" in result

    def test_mentions_resume_run(self):
        result = build_cli_hints()
        assert "codegen_resume_run" in result

    def test_mentions_stop_run(self):
        result = build_cli_hints()
        assert "codegen_stop_run" in result

    def test_mentions_list_runs(self):
        result = build_cli_hints()
        assert "codegen_list_runs" in result

    def test_mentions_start_execution(self):
        result = build_cli_hints()
        assert "codegen_start_execution" in result

    def test_mentions_get_execution_context(self):
        result = build_cli_hints()
        assert "codegen_get_execution_context" in result


class TestBuildIntegrationHints:
    def test_empty_when_no_integrations(self):
        result = build_integration_hints({})
        assert result == ""

    def test_empty_when_all_disabled(self):
        result = build_integration_hints({"github": False, "linear": False})
        assert result == ""

    def test_github_hints(self):
        result = build_integration_hints({"github": True})
        assert "Integration Hints" in result
        assert "GitHub" in result
        assert "conventional commit" in result

    def test_linear_hints(self):
        result = build_integration_hints({"linear": True})
        assert "Linear" in result
        assert "ENG-123" in result

    def test_slack_hints(self):
        result = build_integration_hints({"slack": True})
        assert "Slack" in result
        assert "linked channels" in result

    def test_multiple_integrations(self):
        result = build_integration_hints({"github": True, "linear": True, "slack": False})
        assert "GitHub" in result
        assert "Linear" in result
        # Slack is disabled, should not appear with hint text
        assert "linked channels" not in result

    def test_unknown_integration_fallback(self):
        result = build_integration_hints({"jira": True})
        assert "Jira" in result
        assert "connected and available" in result

    def test_sorted_order(self):
        result = build_integration_hints({"slack": True, "github": True, "linear": True})
        github_pos = result.index("GitHub")
        linear_pos = result.index("Linear")
        slack_pos = result.index("Slack")
        assert github_pos < linear_pos < slack_pos


class TestBuildBestPractices:
    def test_returns_nonempty_string(self):
        result = build_best_practices()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_title(self):
        result = build_best_practices()
        assert "# Codegen Agent Best Practices" in result

    def test_contains_prompt_construction_section(self):
        result = build_best_practices()
        assert "## Prompt Construction" in result

    def test_contains_execution_patterns_section(self):
        result = build_best_practices()
        assert "## Execution Patterns" in result

    def test_contains_code_quality_section(self):
        result = build_best_practices()
        assert "## Code Quality" in result

    def test_contains_integration_tips_section(self):
        result = build_best_practices()
        assert "## Integration Tips" in result

    def test_contains_when_to_pause_section(self):
        result = build_best_practices()
        assert "## When to Pause" in result

    def test_mentions_execution_id(self):
        result = build_best_practices()
        assert "execution_id" in result

    def test_mentions_conventional_commits(self):
        result = build_best_practices()
        assert "conventional commit" in result

    def test_mentions_pause_and_report(self):
        result = build_best_practices()
        assert "PAUSE and report" in result

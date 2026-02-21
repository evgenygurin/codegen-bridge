"""Tests for structured prompt builder."""

from __future__ import annotations

from bridge.context import (
    ExecutionContext,
    PRInfo,
    TaskContext,
    TaskReport,
)
from bridge.prompt_builder import build_task_prompt


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

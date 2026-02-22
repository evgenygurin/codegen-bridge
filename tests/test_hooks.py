"""Tests for Claude Code plugin hooks configuration and scripts.

Validates:
- hooks.json schema and structure
- PostToolUse hook for codegen_create_run (auto-show run URL)
- PostToolUse hook for codegen_get_run (auto-format status)
- Stop hook (session summary via prompt-based hook)
- Hook scripts parse tool responses correctly
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

# ── Paths ─────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = PROJECT_ROOT / "hooks"
HOOKS_JSON = HOOKS_DIR / "hooks.json"
SCRIPTS_DIR = HOOKS_DIR / "scripts"
POST_CREATE_RUN_SCRIPT = SCRIPTS_DIR / "post-create-run.sh"
POST_GET_RUN_SCRIPT = SCRIPTS_DIR / "post-get-run.sh"

# ── Valid hook event names per Claude Code spec ───────────────

VALID_HOOK_EVENTS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PostToolUseFailure",
    "Notification",
    "SubagentStart",
    "SubagentStop",
    "Stop",
    "TeammateIdle",
    "TaskCompleted",
    "PreCompact",
    "SessionEnd",
    "ConfigChange",
    "Setup",
}

VALID_HOOK_TYPES = {"command", "prompt", "agent"}


# ── hooks.json structure tests ────────────────────────────────


class TestHooksJsonStructure:
    """Verify hooks.json is valid and follows the Claude Code plugin schema."""

    def test_hooks_json_exists(self):
        assert HOOKS_JSON.exists(), f"hooks.json not found at {HOOKS_JSON}"

    def test_hooks_json_is_valid_json(self):
        data = json.loads(HOOKS_JSON.read_text())
        assert isinstance(data, dict)

    def test_hooks_json_has_hooks_key(self):
        data = json.loads(HOOKS_JSON.read_text())
        assert "hooks" in data, "hooks.json must have a top-level 'hooks' key"

    def test_hooks_json_has_description(self):
        data = json.loads(HOOKS_JSON.read_text())
        assert "description" in data, "hooks.json should have a 'description' field"
        assert isinstance(data["description"], str)
        assert len(data["description"]) > 0

    def test_all_events_are_valid(self):
        data = json.loads(HOOKS_JSON.read_text())
        for event_name in data["hooks"]:
            assert event_name in VALID_HOOK_EVENTS, (
                f"Unknown hook event '{event_name}'. "
                f"Valid events: {sorted(VALID_HOOK_EVENTS)}"
            )

    def test_event_values_are_lists(self):
        data = json.loads(HOOKS_JSON.read_text())
        for event_name, matchers in data["hooks"].items():
            assert isinstance(matchers, list), (
                f"Event '{event_name}' value must be a list of matcher groups"
            )

    def test_matcher_groups_have_hooks(self):
        data = json.loads(HOOKS_JSON.read_text())
        for event_name, matchers in data["hooks"].items():
            for i, group in enumerate(matchers):
                assert isinstance(group, dict), (
                    f"{event_name}[{i}] must be a dict (matcher group)"
                )
                assert "hooks" in group, (
                    f"{event_name}[{i}] must have a 'hooks' key"
                )
                assert isinstance(group["hooks"], list)
                assert len(group["hooks"]) > 0, (
                    f"{event_name}[{i}]['hooks'] must not be empty"
                )

    def test_all_hook_handlers_have_type(self):
        data = json.loads(HOOKS_JSON.read_text())
        for event_name, matchers in data["hooks"].items():
            for i, group in enumerate(matchers):
                for j, handler in enumerate(group["hooks"]):
                    assert "type" in handler, (
                        f"{event_name}[{i}].hooks[{j}] must have 'type'"
                    )
                    assert handler["type"] in VALID_HOOK_TYPES, (
                        f"{event_name}[{i}].hooks[{j}] has invalid type "
                        f"'{handler['type']}'. Valid: {VALID_HOOK_TYPES}"
                    )

    def test_command_hooks_have_command(self):
        data = json.loads(HOOKS_JSON.read_text())
        for event_name, matchers in data["hooks"].items():
            for i, group in enumerate(matchers):
                for j, handler in enumerate(group["hooks"]):
                    if handler["type"] == "command":
                        assert "command" in handler, (
                            f"{event_name}[{i}].hooks[{j}] is type=command "
                            "but missing 'command' field"
                        )

    def test_prompt_hooks_have_prompt(self):
        data = json.loads(HOOKS_JSON.read_text())
        for event_name, matchers in data["hooks"].items():
            for i, group in enumerate(matchers):
                for j, handler in enumerate(group["hooks"]):
                    if handler["type"] == "prompt":
                        assert "prompt" in handler, (
                            f"{event_name}[{i}].hooks[{j}] is type=prompt "
                            "but missing 'prompt' field"
                        )

    def test_timeouts_are_positive_numbers(self):
        data = json.loads(HOOKS_JSON.read_text())
        for event_name, matchers in data["hooks"].items():
            for i, group in enumerate(matchers):
                for j, handler in enumerate(group["hooks"]):
                    if "timeout" in handler:
                        assert isinstance(handler["timeout"], (int, float)), (
                            f"{event_name}[{i}].hooks[{j}] timeout must be a number"
                        )
                        assert handler["timeout"] > 0, (
                            f"{event_name}[{i}].hooks[{j}] timeout must be positive"
                        )


# ── PostToolUse hook configuration tests ──────────────────────


class TestPostToolUseHooks:
    """Verify PostToolUse hooks are configured correctly."""

    @pytest.fixture
    def hooks_data(self):
        return json.loads(HOOKS_JSON.read_text())

    def test_has_post_tool_use_event(self, hooks_data):
        assert "PostToolUse" in hooks_data["hooks"]

    def test_has_create_run_matcher(self, hooks_data):
        matchers = [g.get("matcher", "") for g in hooks_data["hooks"]["PostToolUse"]]
        create_run_found = any("codegen_create_run" in m for m in matchers)
        assert create_run_found, (
            f"No PostToolUse matcher for codegen_create_run. Found: {matchers}"
        )

    def test_has_get_run_matcher(self, hooks_data):
        matchers = [g.get("matcher", "") for g in hooks_data["hooks"]["PostToolUse"]]
        get_run_found = any("codegen_get_run" in m for m in matchers)
        assert get_run_found, (
            f"No PostToolUse matcher for codegen_get_run. Found: {matchers}"
        )

    def test_create_run_matcher_is_valid_regex(self, hooks_data):
        for group in hooks_data["hooks"]["PostToolUse"]:
            matcher = group.get("matcher", "")
            if "codegen_create_run" in matcher:
                # Should compile as valid regex
                re.compile(matcher)
                # Should match MCP tool names
                assert re.search(matcher, "mcp__codegen_bridge__codegen_create_run")

    def test_get_run_matcher_is_valid_regex(self, hooks_data):
        for group in hooks_data["hooks"]["PostToolUse"]:
            matcher = group.get("matcher", "")
            if "codegen_get_run" in matcher:
                re.compile(matcher)
                assert re.search(matcher, "mcp__codegen_bridge__codegen_get_run")

    def test_create_run_matcher_does_not_match_get_run(self, hooks_data):
        """Ensure create_run and get_run hooks don't cross-match."""
        for group in hooks_data["hooks"]["PostToolUse"]:
            matcher = group.get("matcher", "")
            if "codegen_create_run" in matcher:
                pat = re.compile(matcher)
                assert not pat.search("mcp__codegen_bridge__codegen_get_run"), (
                    "create_run matcher should not match get_run tool"
                )

    def test_create_run_hook_uses_plugin_root(self, hooks_data):
        for group in hooks_data["hooks"]["PostToolUse"]:
            if "codegen_create_run" in group.get("matcher", ""):
                for handler in group["hooks"]:
                    if handler["type"] == "command":
                        assert "${CLAUDE_PLUGIN_ROOT}" in handler["command"]

    def test_get_run_hook_uses_plugin_root(self, hooks_data):
        for group in hooks_data["hooks"]["PostToolUse"]:
            if "codegen_get_run" in group.get("matcher", ""):
                for handler in group["hooks"]:
                    if handler["type"] == "command":
                        assert "${CLAUDE_PLUGIN_ROOT}" in handler["command"]


# ── Stop hook configuration tests ─────────────────────────────


class TestStopHook:
    """Verify the Stop hook for session summary is configured correctly."""

    @pytest.fixture
    def hooks_data(self):
        return json.loads(HOOKS_JSON.read_text())

    def test_has_stop_event(self, hooks_data):
        assert "Stop" in hooks_data["hooks"]

    def test_stop_hook_is_prompt_based(self, hooks_data):
        stop_groups = hooks_data["hooks"]["Stop"]
        assert len(stop_groups) > 0
        found_prompt = False
        for group in stop_groups:
            for handler in group["hooks"]:
                if handler["type"] == "prompt":
                    found_prompt = True
        assert found_prompt, "Stop hook should use a prompt-based handler"

    def test_stop_hook_has_no_matcher(self, hooks_data):
        """Stop hooks don't support matchers per the spec."""
        for group in hooks_data["hooks"]["Stop"]:
            assert "matcher" not in group or group.get("matcher") in (None, "", "*"), (
                "Stop hooks do not support matchers"
            )

    def test_stop_hook_prompt_mentions_codegen(self, hooks_data):
        for group in hooks_data["hooks"]["Stop"]:
            for handler in group["hooks"]:
                if handler["type"] == "prompt":
                    prompt = handler["prompt"].lower()
                    assert "codegen" in prompt, (
                        "Stop prompt should mention Codegen context"
                    )

    def test_stop_hook_prompt_mentions_agent_runs(self, hooks_data):
        for group in hooks_data["hooks"]["Stop"]:
            for handler in group["hooks"]:
                if handler["type"] == "prompt":
                    prompt = handler["prompt"].lower()
                    assert "agent run" in prompt or "codegen_create_run" in prompt, (
                        "Stop prompt should reference agent runs"
                    )

    def test_stop_hook_prompt_always_allows_stopping(self, hooks_data):
        """The stop hook should be informational — never block stopping."""
        for group in hooks_data["hooks"]["Stop"]:
            for handler in group["hooks"]:
                if handler["type"] == "prompt":
                    prompt = handler["prompt"].lower()
                    assert "ok" in prompt and "true" in prompt, (
                        "Stop prompt should instruct LLM to always return ok=true"
                    )

    def test_stop_hook_has_timeout(self, hooks_data):
        for group in hooks_data["hooks"]["Stop"]:
            for handler in group["hooks"]:
                if handler["type"] == "prompt":
                    assert "timeout" in handler, "Stop prompt hook should have a timeout"
                    assert handler["timeout"] <= 60, (
                        "Stop prompt timeout should be reasonable (<=60s)"
                    )

    def test_stop_prompt_uses_arguments_placeholder(self, hooks_data):
        for group in hooks_data["hooks"]["Stop"]:
            for handler in group["hooks"]:
                if handler["type"] == "prompt":
                    assert "$ARGUMENTS" in handler["prompt"], (
                        "Stop prompt should use $ARGUMENTS to receive session context"
                    )


# ── Hook script file tests ────────────────────────────────────


class TestHookScripts:
    """Verify hook scripts exist, are executable, and have correct structure."""

    def test_scripts_directory_exists(self):
        assert SCRIPTS_DIR.exists()
        assert SCRIPTS_DIR.is_dir()

    def test_post_create_run_script_exists(self):
        assert POST_CREATE_RUN_SCRIPT.exists()

    def test_post_get_run_script_exists(self):
        assert POST_GET_RUN_SCRIPT.exists()

    def test_post_create_run_script_is_executable(self):
        assert os.access(POST_CREATE_RUN_SCRIPT, os.X_OK)

    def test_post_get_run_script_is_executable(self):
        assert os.access(POST_GET_RUN_SCRIPT, os.X_OK)

    def test_post_create_run_script_has_shebang(self):
        content = POST_CREATE_RUN_SCRIPT.read_text()
        assert content.startswith("#!/"), "Script must have a shebang line"

    def test_post_get_run_script_has_shebang(self):
        content = POST_GET_RUN_SCRIPT.read_text()
        assert content.startswith("#!/"), "Script must have a shebang line"


# ── Hook script execution tests ───────────────────────────────


def _run_script(script_path: Path, stdin_data: str) -> subprocess.CompletedProcess:
    """Run a hook script with the given stdin and return the result."""
    return subprocess.run(
        ["bash", str(script_path)],
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=10,
    )


class TestPostCreateRunScript:
    """Test the post-create-run.sh hook script with mock inputs."""

    def test_successful_run_creation(self):
        """Script should output additionalContext with run URL."""
        tool_response = json.dumps({
            "id": 12345,
            "status": "running",
            "web_url": "https://app.codegen.com/runs/12345",
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_create_run",
            "tool_input": {"prompt": "Fix the bug"},
            "tool_response": tool_response,
        })
        result = _run_script(POST_CREATE_RUN_SCRIPT, hook_input)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "hookSpecificOutput" in output
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "12345" in ctx
        assert "running" in ctx
        assert "https://app.codegen.com/runs/12345" in ctx

    def test_run_creation_without_web_url(self):
        """Script should handle missing web_url gracefully."""
        tool_response = json.dumps({
            "id": 99,
            "status": "queued",
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_create_run",
            "tool_input": {"prompt": "Deploy"},
            "tool_response": tool_response,
        })
        result = _run_script(POST_CREATE_RUN_SCRIPT, hook_input)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "99" in ctx
        assert "queued" in ctx

    def test_empty_tool_response(self):
        """Script should exit 0 silently on empty tool_response."""
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_create_run",
            "tool_input": {"prompt": "Test"},
            "tool_response": "",
        })
        result = _run_script(POST_CREATE_RUN_SCRIPT, hook_input)
        assert result.returncode == 0

    def test_cancelled_run(self):
        """Script should exit 0 silently when run was cancelled."""
        tool_response = json.dumps({
            "action": "cancelled",
            "reason": "User declined to create run",
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_create_run",
            "tool_input": {"prompt": "Test"},
            "tool_response": tool_response,
        })
        result = _run_script(POST_CREATE_RUN_SCRIPT, hook_input)
        # Should exit 0 — no run_id means silent exit
        assert result.returncode == 0

    def test_contains_monitoring_hint(self):
        """Output should hint at how to check run status."""
        tool_response = json.dumps({
            "id": 42,
            "status": "running",
            "web_url": "https://app.codegen.com/runs/42",
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_create_run",
            "tool_input": {"prompt": "Build feature"},
            "tool_response": tool_response,
        })
        result = _run_script(POST_CREATE_RUN_SCRIPT, hook_input)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "codegen_get_run" in ctx


class TestPostGetRunScript:
    """Test the post-get-run.sh hook script with mock inputs."""

    def test_completed_run(self):
        """Script should format completed run with checkmark."""
        tool_response = json.dumps({
            "id": 100,
            "status": "completed",
            "web_url": "https://app.codegen.com/runs/100",
            "summary": "Fixed the authentication bug",
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_get_run",
            "tool_input": {"run_id": 100},
            "tool_response": tool_response,
        })
        result = _run_script(POST_GET_RUN_SCRIPT, hook_input)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "✅" in ctx
        assert "100" in ctx
        assert "completed" in ctx
        assert "Fixed the authentication bug" in ctx

    def test_failed_run_suggests_logs(self):
        """Failed run should suggest checking logs."""
        tool_response = json.dumps({
            "id": 200,
            "status": "failed",
            "web_url": "https://app.codegen.com/runs/200",
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_get_run",
            "tool_input": {"run_id": 200},
            "tool_response": tool_response,
        })
        result = _run_script(POST_GET_RUN_SCRIPT, hook_input)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "❌" in ctx
        assert "codegen_get_logs" in ctx

    def test_running_run_suggests_polling(self):
        """Running run should suggest polling again."""
        tool_response = json.dumps({
            "id": 300,
            "status": "running",
            "web_url": "https://app.codegen.com/runs/300",
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_get_run",
            "tool_input": {"run_id": 300},
            "tool_response": tool_response,
        })
        result = _run_script(POST_GET_RUN_SCRIPT, hook_input)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "⏳" in ctx
        assert "codegen_get_run" in ctx

    def test_paused_run_suggests_resume(self):
        """Paused run should suggest resuming."""
        tool_response = json.dumps({
            "id": 400,
            "status": "paused",
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_get_run",
            "tool_input": {"run_id": 400},
            "tool_response": tool_response,
        })
        result = _run_script(POST_GET_RUN_SCRIPT, hook_input)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "codegen_resume_run" in ctx

    def test_run_with_pull_requests(self):
        """Script should show PR count and URLs."""
        tool_response = json.dumps({
            "id": 500,
            "status": "completed",
            "web_url": "https://app.codegen.com/runs/500",
            "summary": "Added dark mode",
            "pull_requests": [
                {"url": "https://github.com/org/repo/pull/42", "number": 42},
                {"url": "https://github.com/org/repo/pull/43", "number": 43},
            ],
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_get_run",
            "tool_input": {"run_id": 500},
            "tool_response": tool_response,
        })
        result = _run_script(POST_GET_RUN_SCRIPT, hook_input)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "2 PR(s)" in ctx
        assert "github.com/org/repo/pull/42" in ctx

    def test_empty_tool_response(self):
        """Script should exit 0 silently on empty tool_response."""
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_get_run",
            "tool_input": {"run_id": 999},
            "tool_response": "",
        })
        result = _run_script(POST_GET_RUN_SCRIPT, hook_input)
        assert result.returncode == 0

    def test_queued_status_emoji(self):
        """Queued runs should show the correct emoji."""
        tool_response = json.dumps({
            "id": 600,
            "status": "queued",
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_get_run",
            "tool_input": {"run_id": 600},
            "tool_response": tool_response,
        })
        result = _run_script(POST_GET_RUN_SCRIPT, hook_input)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "🔄" in ctx

    def test_result_field_fallback(self):
        """When summary is absent, result field should be used."""
        tool_response = json.dumps({
            "id": 700,
            "status": "completed",
            "result": "All tests passed",
        })
        hook_input = json.dumps({
            "tool_name": "mcp__codegen_bridge__codegen_get_run",
            "tool_input": {"run_id": 700},
            "tool_response": tool_response,
        })
        result = _run_script(POST_GET_RUN_SCRIPT, hook_input)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "All tests passed" in ctx

---
description: "Delegate a task to Codegen cloud agent"
---

Use the codegen MCP tools to handle this request.

If the user provided a task description, use `codegen_create_run` to create an agent run with that task.

If no task was provided, show available actions:
- Create new agent run: `codegen_create_run`
- Check status: `codegen_get_run` or `codegen_list_runs`
- View logs: `codegen_get_logs`
- Resume paused run: `codegen_resume_run`
- List repos: `codegen_list_repos`

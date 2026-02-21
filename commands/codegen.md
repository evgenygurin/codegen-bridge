---
description: "Delegate a task to Codegen cloud agent"
---

Use the codegen MCP tools to handle this request.

If the user provided a task description:
1. Call `codegen_start_execution` with the task as goal (mode="adhoc")
2. Call `codegen_create_run` with execution_id for auto-enriched prompt
3. Report the run ID and web URL

If no task was provided, show available actions:
- Create new agent run: `codegen_start_execution` + `codegen_create_run`
- Check status: `codegen_get_run` or `codegen_list_runs`
- View execution: `codegen_get_execution_context`
- View logs: `codegen_get_logs`
- Resume paused run: `codegen_resume_run`
- List repos: `codegen_list_repos`
- Get rules: `codegen_get_agent_rules`

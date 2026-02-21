---
description: "View execution logs for a Codegen agent run"
---

Call `codegen_get_logs` for the specified run_id. If no run_id provided, call `codegen_list_runs` first and ask the user which run to show logs for.

Format logs showing: timestamp, thought, tool calls, and errors. Truncate long tool outputs.

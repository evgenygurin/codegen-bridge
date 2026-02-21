---
description: "Quick overview of active Codegen agent runs"
---

First check for an active execution context using `codegen_get_execution_context`.

If an active execution exists, show:
- Execution ID, goal, and mode
- Each task: index, title, status, run_id, PR link (if completed)
- Overall progress: N/M tasks completed

If no active execution, fall back to `codegen_list_runs` and format as a concise table showing: ID, status, summary, and PR link (if any). Group by status: running first, then queued, then recently completed.

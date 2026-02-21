---
description: "View and manage Codegen plugin settings"
---

Manage plugin settings stored in `.claude-plugin/settings.json`.

If no arguments provided, show current settings:
1. Call `codegen_get_settings` to read current values
2. Display each setting with its current value and description:
   - **default_model**: LLM model for agent runs (null = org default)
   - **auto_monitor**: Whether to automatically poll runs after creation
   - **poll_interval**: Seconds between status polls (5-300)

If the user wants to change a setting:
1. Call `codegen_update_settings` with the field name and new value
2. Confirm the change: "Updated {setting} to {value}"

Examples:
- `/cg-settings` — show all current settings
- `/cg-settings default_model claude-sonnet` — set the default model
- `/cg-settings poll_interval 60` — set poll interval to 60 seconds
- `/cg-settings auto_monitor false` — disable auto-monitoring
- `/cg-settings default_model null` — reset model to org default

# Commands Reference

Codegen Bridge provides **5 slash commands** for quick access to common actions. Commands are discovered automatically by the `CommandsProvider` from the `commands/` directory.

## Available Commands

| Command | Description |
|---------|-------------|
| `/codegen` | Delegate a task to a Codegen cloud agent |
| `/cg-status` | Check status of active agent runs |
| `/cg-logs` | View execution logs for an agent run |
| `/cg-merge` | Merge pull requests from agent runs |
| `/cg-settings` | View and manage plugin settings |

---

## `/codegen` — Delegate a Task

**File:** `commands/codegen.md`

Creates a new agent run to handle a coding task.

### Usage

```text
/codegen <task description>
```

### Behavior

**With a task description:**
1. Calls `codegen_start_execution` with the task as goal (`mode="adhoc"`)
2. Calls `codegen_create_run` with `execution_id` for auto-enriched prompt
3. Reports the run ID and web URL

**Without a task description:**
Shows available actions:
- Create new agent run
- Check status
- View execution context
- View logs
- Resume paused run
- List repos
- Get agent rules

### Examples

```text
/codegen Add input validation to the signup form
/codegen Fix the timeout bug in file upload
/codegen Refactor the auth middleware into a shared module
```

---

## `/cg-status` — Check Status

**File:** `commands/cg-status.md`

Quick overview of active Codegen agent runs.

### Behavior

1. Checks for an active execution context via `codegen_get_execution_context`
2. If execution exists, shows:
   - Execution ID, goal, and mode
   - Each task: index, title, status, run_id, PR link
   - Overall progress: N/M tasks completed
3. If no execution, falls back to `codegen_list_runs` showing a table of:
   - ID, status, summary, PR link
   - Grouped by status: running → queued → completed

### Example Output

```
Execution: "Implement auth system" (3/5 tasks completed)

Task 1: Add user model          [completed] PR #40
Task 2: Add JWT middleware       [completed] PR #41
Task 3: Add login endpoint       [completed] PR #42
Task 4: Add registration flow    [running]   Run #789
Task 5: Add password reset       [pending]
```

---

## `/cg-logs` — View Logs

**File:** `commands/cg-logs.md`

View execution logs for a specific agent run.

### Usage

```text
/cg-logs              # Lists runs, asks which to show
/cg-logs <run_id>     # Shows logs for the specified run
```

### Behavior

1. If no `run_id` provided, calls `codegen_list_runs` first and asks which run to show
2. Calls `codegen_get_logs` for the specified run
3. Formats logs showing: timestamp, thought, tool calls, and errors
4. Truncates long tool outputs

---

## `/cg-merge` — Merge PRs

**File:** `commands/cg-merge.md`

Manage merging of pull requests created by Codegen agent runs.

### Behavior

**List PRs:**
1. Calls `codegen_list_runs` (limit=20) to find recent completed runs
2. Filters for runs with open PRs
3. Shows: run ID, summary, PR number, title, URL, state

**Merge a specific run's PR:**
1. Calls `codegen_get_run` for the specified run
2. If PR is in draft, marks as `ready_for_review`
3. Informs user: "PR is ready for review. Merge via GitHub or `gh pr merge`."

**Merge all PRs from a plan:**
1. Gets execution context for all tasks
2. Lists all PRs with status
3. Processes each sequentially with user confirmation

> **Note:** The Codegen API can change PR state but actual GitHub merge requires repository write access via GitHub CLI or the GitHub UI.

---

## `/cg-settings` — Plugin Settings

**File:** `commands/cg-settings.md`

View and manage plugin settings stored in `.claude-plugin/settings.json`.

### Usage

```text
/cg-settings                           # Show all current settings
/cg-settings default_model claude-sonnet  # Set default model
/cg-settings poll_interval 60            # Set poll interval
/cg-settings auto_monitor false          # Disable auto-monitoring
/cg-settings default_model null          # Reset to org default
```

### Available Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `default_model` | `string \| null` | `null` | LLM model for agent runs (`null` = org default) |
| `auto_monitor` | `bool` | `true` | Automatically poll runs after creation |
| `poll_interval` | `int` | `30` | Seconds between status polls (5-300) |

---

## See Also

- **[[Tools-Reference]]** — Underlying tools that commands use
- **[[Skills-Guide]]** — Skills that provide richer workflows
- **[[Getting-Started]]** — How to install and configure

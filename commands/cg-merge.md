---
description: "Merge pull requests created by Codegen agent runs"
---

List recent Codegen agent runs that have open PRs and offer to merge them.

1. Call `codegen_list_runs` with limit=20 to get recent runs
2. Filter runs with status "completed" that have `github_pull_requests`
3. For each run with open PRs, show:
   - Run ID and summary
   - PR number, title, URL, and current state
4. If no open PRs found, say: "No open PRs from recent Codegen runs."

If the user specified a run ID:
1. Call `codegen_get_run` for that run
2. Show its PRs and ask for confirmation before merging

To merge a specific PR:
1. Call `codegen_edit_pr_simple` with `pr_id` and `state="ready_for_review"` if the PR is in draft
2. Inform the user: "PR #N is now ready for review. Merge it on GitHub or via `gh pr merge`."

If the user wants to merge all open PRs from a plan execution:
1. Call `codegen_get_execution_context` to get all tasks and their PR links
2. List all PRs with their status
3. Confirm with user before marking each as ready for review
4. Process each PR sequentially, reporting progress

Note: The Codegen API supports changing PR state (open, closed, draft, ready_for_review) but actual GitHub merge requires repository write access via GitHub CLI or the GitHub UI.

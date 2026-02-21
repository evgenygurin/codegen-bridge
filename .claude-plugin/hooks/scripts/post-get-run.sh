#!/usr/bin/env bash
# PostToolUse hook for codegen_get_run
# Parses the tool response and injects a formatted status summary.
#
# Input (stdin): JSON with tool_name, tool_input, tool_response fields
# Output (stdout): JSON with additionalContext for Claude
set -euo pipefail

INPUT=$(cat)

# Extract tool_response
TOOL_RESPONSE=$(echo "$INPUT" | jq -r '.tool_response // empty')
if [ -z "$TOOL_RESPONSE" ]; then
  exit 0
fi

# tool_response from MCP tools is often a string containing JSON
# Try direct parse first, then try treating as JSON string
RUN_ID=$(echo "$TOOL_RESPONSE" | jq -r '.id // empty' 2>/dev/null || echo "")
STATUS=$(echo "$TOOL_RESPONSE" | jq -r '.status // empty' 2>/dev/null || echo "")
WEB_URL=$(echo "$TOOL_RESPONSE" | jq -r '.web_url // empty' 2>/dev/null || echo "")
SUMMARY=$(echo "$TOOL_RESPONSE" | jq -r '.summary // empty' 2>/dev/null || echo "")
RESULT=$(echo "$TOOL_RESPONSE" | jq -r '.result // empty' 2>/dev/null || echo "")
PR_COUNT=$(echo "$TOOL_RESPONSE" | jq -r '.pull_requests | length // 0' 2>/dev/null || echo "0")

# If tool_response is a JSON string (double-encoded), try parsing the inner JSON
if [ -z "$RUN_ID" ]; then
  INNER=$(echo "$TOOL_RESPONSE" | jq -r '.' 2>/dev/null || echo "$TOOL_RESPONSE")
  RUN_ID=$(echo "$INNER" | jq -r '.id // empty' 2>/dev/null || echo "")
  STATUS=$(echo "$INNER" | jq -r '.status // empty' 2>/dev/null || echo "")
  WEB_URL=$(echo "$INNER" | jq -r '.web_url // empty' 2>/dev/null || echo "")
  SUMMARY=$(echo "$INNER" | jq -r '.summary // empty' 2>/dev/null || echo "")
  RESULT=$(echo "$INNER" | jq -r '.result // empty' 2>/dev/null || echo "")
  PR_COUNT=$(echo "$INNER" | jq -r '.pull_requests | length // 0' 2>/dev/null || echo "0")
fi

# If we still can't parse, exit silently
if [ -z "$RUN_ID" ]; then
  exit 0
fi

# Pick status emoji
case "$STATUS" in
  completed) EMOJI="✅" ;;
  failed)    EMOJI="❌" ;;
  running)   EMOJI="⏳" ;;
  queued)    EMOJI="🔄" ;;
  paused)    EMOJI="⏸️" ;;
  *)         EMOJI="ℹ️" ;;
esac

# Build context message
CONTEXT="${EMOJI} Agent run ${RUN_ID} — ${STATUS:-unknown}"

if [ -n "$WEB_URL" ]; then
  CONTEXT="${CONTEXT}
• URL: ${WEB_URL}"
fi

if [ -n "$SUMMARY" ]; then
  CONTEXT="${CONTEXT}
• Summary: ${SUMMARY}"
elif [ -n "$RESULT" ]; then
  CONTEXT="${CONTEXT}
• Result: ${RESULT}"
fi

if [ "$PR_COUNT" != "0" ] && [ -n "$PR_COUNT" ]; then
  CONTEXT="${CONTEXT}
• Pull requests: ${PR_COUNT} PR(s) created"

  # Extract PR URLs if available
  PR_URLS=$(echo "$TOOL_RESPONSE" | jq -r '.pull_requests[]?.url // empty' 2>/dev/null || echo "")
  if [ -z "$PR_URLS" ]; then
    PR_URLS=$(echo "$INNER" | jq -r '.pull_requests[]?.url // empty' 2>/dev/null || echo "")
  fi
  if [ -n "$PR_URLS" ]; then
    while IFS= read -r url; do
      if [ -n "$url" ]; then
        CONTEXT="${CONTEXT}
  → ${url}"
      fi
    done <<< "$PR_URLS"
  fi
fi

# Add next-step suggestion based on status
case "$STATUS" in
  running|queued)
    CONTEXT="${CONTEXT}
💡 Run is still in progress. Poll again with codegen_get_run(run_id=${RUN_ID}) in ~30 seconds."
    ;;
  paused)
    CONTEXT="${CONTEXT}
💡 Agent is paused and needs input. Use codegen_resume_run(run_id=${RUN_ID}, prompt=<instructions>) to continue."
    ;;
  failed)
    CONTEXT="${CONTEXT}
💡 Check logs with codegen_get_logs(run_id=${RUN_ID}) to see what went wrong."
    ;;
esac

# Output JSON with additionalContext
jq -n --arg ctx "$CONTEXT" '{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": $ctx
  }
}'

exit 0

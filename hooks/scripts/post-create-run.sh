#!/usr/bin/env bash
# PostToolUse hook for codegen_create_run
# Parses the tool response and injects a user-friendly message with the run URL.
#
# Input (stdin): JSON with tool_name, tool_input, tool_response fields
# Output (stdout): JSON with additionalContext for Claude
set -euo pipefail

INPUT=$(cat)

# Extract tool_response — it may be a string (JSON-encoded) or an object
TOOL_RESPONSE=$(echo "$INPUT" | jq -r '.tool_response // empty')
if [ -z "$TOOL_RESPONSE" ]; then
  exit 0
fi

# tool_response from MCP tools is often a string containing JSON
# Try to parse it; if it fails, treat as plain text
RUN_ID=$(echo "$TOOL_RESPONSE" | jq -r '.id // empty' 2>/dev/null || echo "")
STATUS=$(echo "$TOOL_RESPONSE" | jq -r '.status // empty' 2>/dev/null || echo "")
WEB_URL=$(echo "$TOOL_RESPONSE" | jq -r '.web_url // empty' 2>/dev/null || echo "")

# If tool_response is a JSON string (double-encoded), try parsing the inner JSON
if [ -z "$RUN_ID" ]; then
  INNER=$(echo "$TOOL_RESPONSE" | jq -r '.' 2>/dev/null || echo "$TOOL_RESPONSE")
  RUN_ID=$(echo "$INNER" | jq -r '.id // empty' 2>/dev/null || echo "")
  STATUS=$(echo "$INNER" | jq -r '.status // empty' 2>/dev/null || echo "")
  WEB_URL=$(echo "$INNER" | jq -r '.web_url // empty' 2>/dev/null || echo "")
fi

# If we still can't parse, exit silently
if [ -z "$RUN_ID" ]; then
  exit 0
fi

# Build context message
CONTEXT="🚀 Agent run created successfully!
• Run ID: ${RUN_ID}
• Status: ${STATUS:-unknown}"

if [ -n "$WEB_URL" ]; then
  CONTEXT="${CONTEXT}
• Monitor: ${WEB_URL}"
fi

CONTEXT="${CONTEXT}
Use codegen_get_run(run_id=${RUN_ID}) to check progress."

# Output JSON with additionalContext
jq -n --arg ctx "$CONTEXT" '{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": $ctx
  }
}'

exit 0

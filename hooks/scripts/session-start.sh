#!/usr/bin/env bash
# SessionStart hook — inject using-codegen-bridge meta-skill into conversation context.
# Detects whether superpowers plugin is also installed and adjusts messaging.
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
SKILL_FILE="${PLUGIN_ROOT}/skills/using-codegen-bridge/SKILL.md"

if [ ! -f "$SKILL_FILE" ]; then
  echo '{"error": "using-codegen-bridge skill not found"}'
  exit 0
fi

# Read skill content
SKILL_CONTENT=$(cat "$SKILL_FILE")

# Detect superpowers plugin presence
HAS_SUPERPOWERS="false"
# Check common installation paths
for check_path in \
  "${PLUGIN_ROOT}/../superpowers" \
  "${PLUGIN_ROOT}/../superpowers-marketplace/superpowers" \
  "${HOME}/.claude/plugins/superpowers" \
  "${HOME}/.claude/plugins/cache/superpowers-marketplace"; do
  if [ -d "$check_path" ] 2>/dev/null; then
    HAS_SUPERPOWERS="true"
    break
  fi
done

# Build context message
if [ "$HAS_SUPERPOWERS" = "true" ]; then
  CONTEXT_PREFIX="Codegen Bridge plugin detected alongside Superpowers. Use superpowers skills for process (TDD, brainstorming, planning, debugging, code review) and codegen-bridge skills for cloud agent delegation and monitoring."
else
  CONTEXT_PREFIX="Codegen Bridge plugin active. Use its skills for delegating tasks to cloud agents, monitoring runs, and managing PRs."
fi

# JSON-escape the content
ESCAPED_CONTENT=$(printf '%s' "$SKILL_CONTENT" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')

# Output JSON with additionalContext
cat <<ENDJSON
{"additionalContext": "${CONTEXT_PREFIX}\n\n${ESCAPED_CONTENT:1:-1}"}
ENDJSON

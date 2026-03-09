"""MCP tool definitions for the Codegen Bridge server.

Tools are split by domain, with large modules further decomposed into
focused SOLID submodules:

- agent/ — Agent run management (9 tools in 4 submodules):
  - lifecycle: create, resume, stop
  - queries: get, list
  - moderation: ban, unban, remove-from-pr
  - logs: get_logs
- execution: Execution context management (start, get context, rules)
- pr: Pull request management (edit PR, edit PR simple)
- setup/ — Organization and repository setup (12 tools in 4 submodules):
  - users: get current user, list users, get user
  - organizations: list orgs, get org settings, list repos, generate setup commands
  - oauth: get MCP providers, get OAuth status, revoke OAuth
  - check_suite: get/update check suite settings
- integrations: Integrations, webhooks, sandbox analysis, Slack connect
- settings: Plugin settings management (get, update)
"""

from bridge.tools.agent import register_agent_tools
from bridge.tools.execution import register_execution_tools
from bridge.tools.integrations import register_integration_tools
from bridge.tools.pr import register_pr_tools
from bridge.tools.session import register_session_tools
from bridge.tools.settings import register_settings_tools
from bridge.tools.setup import register_setup_tools

__all__ = [
    "register_agent_tools",
    "register_execution_tools",
    "register_integration_tools",
    "register_pr_tools",
    "register_session_tools",
    "register_settings_tools",
    "register_setup_tools",
]

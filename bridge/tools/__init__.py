"""MCP tool definitions for the Codegen Bridge server.

Tools are split by domain:
- agent: Agent run management (create, get, list, resume, stop, logs)
- execution: Execution context management (start, get context, rules)
- pr: Pull request management (edit PR, edit PR simple)
- setup: Organization and repository setup (list orgs, list repos, setup commands)
- integrations: Integrations, webhooks, sandbox analysis, Slack connect
"""

from bridge.tools.agent import register_agent_tools
from bridge.tools.execution import register_execution_tools
from bridge.tools.integrations import register_integration_tools
from bridge.tools.pr import register_pr_tools
from bridge.tools.setup import register_setup_tools

__all__ = [
    "register_agent_tools",
    "register_execution_tools",
    "register_integration_tools",
    "register_pr_tools",
    "register_setup_tools",
]

"""Service layer: business logic extracted from MCP tool functions.

Services encapsulate domain operations (API calls, context mutations,
prompt enrichment) and return plain dicts.  MCP tools remain thin
wrappers responsible for elicitation, progress reporting, and JSON
serialisation.
"""

from __future__ import annotations

from bridge.services.execution import ExecutionService
from bridge.services.runs import RunService

__all__ = ["ExecutionService", "RunService"]

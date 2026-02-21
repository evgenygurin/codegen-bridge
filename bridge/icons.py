"""Centralized icon definitions for MCP tools, resources, and prompts.

Uses inline SVG data URIs (base64-encoded) so icons are fully self-contained
with no external dependencies. All SVGs follow the Lucide icon style:
24×24 viewBox, stroke-based, monochrome.

Usage::

    from bridge.icons import ICON_RUN, ICON_LOGS
    @mcp.tool(icons=ICON_RUN)
    async def my_tool(): ...
"""

from __future__ import annotations

import base64

from mcp.types import Icon


def _svg_icon(svg_body: str) -> list[Icon]:
    """Create an Icon list from an SVG body (inner elements only).

    Wraps *svg_body* in a standard 24×24 SVG envelope, base64-encodes it,
    and returns a single-element list suitable for the ``icons=`` parameter.
    """
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f"{svg_body}</svg>"
    )
    b64 = base64.b64encode(svg.encode()).decode()
    return [Icon(src=f"data:image/svg+xml;base64,{b64}", mimeType="image/svg+xml")]


# ── Tool Icons ────────────────────────────────────────────

# Agent run management
ICON_RUN = _svg_icon(  # play-circle: create agent run
    '<circle cx="12" cy="12" r="10"/>'
    '<polygon points="10 8 16 12 10 16 10 8"/>'
)

ICON_GET_RUN = _svg_icon(  # info-circle: get run status
    '<circle cx="12" cy="12" r="10"/>'
    '<line x1="12" y1="16" x2="12" y2="12"/>'
    '<line x1="12" y1="8" x2="12.01" y2="8"/>'
)

ICON_LIST = _svg_icon(  # list: list runs
    '<line x1="8" y1="6" x2="21" y2="6"/>'
    '<line x1="8" y1="12" x2="21" y2="12"/>'
    '<line x1="8" y1="18" x2="21" y2="18"/>'
    '<line x1="3" y1="6" x2="3.01" y2="6"/>'
    '<line x1="3" y1="12" x2="3.01" y2="12"/>'
    '<line x1="3" y1="18" x2="3.01" y2="18"/>'
)

ICON_RESUME = _svg_icon(  # fast-forward: resume run
    '<polygon points="13 19 22 12 13 5 13 19"/>'
    '<polygon points="2 19 11 12 2 5 2 19"/>'
)

ICON_STOP = _svg_icon(  # stop-circle: stop run
    '<circle cx="12" cy="12" r="10"/>'
    '<rect x="9" y="9" width="6" height="6"/>'
)

ICON_BAN = _svg_icon(  # slash: ban checks
    '<circle cx="12" cy="12" r="10"/>'
    '<line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>'
)

ICON_UNBAN = _svg_icon(  # check-circle: unban checks
    '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
    '<polyline points="22 4 12 14.01 9 11.01"/>'
)

ICON_REMOVE_FROM_PR = _svg_icon(  # git-pull-request-closed: remove from PR
    '<line x1="6" y1="3" x2="6" y2="15"/>'
    '<circle cx="18" cy="6" r="3"/>'
    '<circle cx="6" cy="18" r="3"/>'
    '<line x1="16" y1="8" x2="18" y2="10"/>'
    '<line x1="18" y1="8" x2="16" y2="10"/>'
)

ICON_LOGS = _svg_icon(  # file-text: logs
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<polyline points="14 2 14 8 20 8"/>'
    '<line x1="16" y1="13" x2="8" y2="13"/>'
    '<line x1="16" y1="17" x2="8" y2="17"/>'
    '<polyline points="10 9 9 9 8 9"/>'
)

# Execution context management
ICON_EXECUTION = _svg_icon(  # rocket: start execution
    '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>'
    '<path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>'
    '<path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>'
    '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>'
)

ICON_CONTEXT = _svg_icon(  # layers: execution context
    '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
    '<polyline points="2 17 12 22 22 17"/>'
    '<polyline points="2 12 12 17 22 12"/>'
)

ICON_RULES = _svg_icon(  # shield: agent rules
    '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
)

# Users
ICON_USER = _svg_icon(  # user: user profile
    '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>'
    '<circle cx="12" cy="7" r="4"/>'
)

ICON_USERS = _svg_icon(  # users: user list
    '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
    '<circle cx="9" cy="7" r="4"/>'
    '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
    '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
)

# Organization & repository setup
ICON_ORG = _svg_icon(  # building: organization
    '<rect x="4" y="2" width="16" height="20" rx="2" ry="2"/>'
    '<path d="M9 22v-4h6v4"/>'
    '<path d="M8 6h.01"/>'
    '<path d="M16 6h.01"/>'
    '<path d="M12 6h.01"/>'
    '<path d="M12 10h.01"/>'
    '<path d="M12 14h.01"/>'
    '<path d="M16 10h.01"/>'
    '<path d="M16 14h.01"/>'
    '<path d="M8 10h.01"/>'
    '<path d="M8 14h.01"/>'
)

ICON_REPO = _svg_icon(  # git-branch: repository
    '<line x1="6" y1="3" x2="6" y2="15"/>'
    '<circle cx="18" cy="6" r="3"/>'
    '<circle cx="6" cy="18" r="3"/>'
    '<path d="M18 9a9 9 0 0 1-9 9"/>'
)

# Pull request management
ICON_PR_EDIT = _svg_icon(  # git-pull-request: edit PR
    '<circle cx="18" cy="18" r="3"/>'
    '<circle cx="6" cy="6" r="3"/>'
    '<path d="M13 6h3a2 2 0 0 1 2 2v7"/>'
    '<line x1="6" y1="9" x2="6" y2="21"/>'
)

ICON_MCP = _svg_icon(  # plug: MCP provider
    '<path d="M12 22v-5"/>'
    '<path d="M9 8V2"/>'
    '<path d="M15 8V2"/>'
    '<path d="M18 8v5a6 6 0 0 1-6 6 6 6 0 0 1-6-6V8z"/>'
)

ICON_OAUTH = _svg_icon(  # key: OAuth token
    '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778'
    ' 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>'
)

# ── Resource Icons ────────────────────────────────────────

ICON_CONFIG = _svg_icon(  # settings: configuration
    '<circle cx="12" cy="12" r="3"/>'
    '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
)

ICON_DASHBOARD = _svg_icon(  # activity: execution state
    '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'
)

# ── Prompt Icons ──────────────────────────────────────────

ICON_DELEGATE = _svg_icon(  # send: delegate task
    '<line x1="22" y1="2" x2="11" y2="13"/>'
    '<polygon points="22 2 15 22 11 13 2 9 22 2"/>'
)

ICON_MONITOR = _svg_icon(  # eye: monitor runs
    '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>'
    '<circle cx="12" cy="12" r="3"/>'
)

ICON_TEMPLATE = _svg_icon(  # layout: build task prompt
    '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>'
    '<line x1="3" y1="9" x2="21" y2="9"/>'
    '<line x1="9" y1="21" x2="9" y2="9"/>'
)

ICON_SUMMARY = _svg_icon(  # clipboard: execution summary
    '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
    '<rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>'
)

ICON_BEST_PRACTICES = _svg_icon(  # book-open: best practices guide
    '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
    '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>'
)

# ── Sampling Icons ───────────────────────────────────────────

ICON_SAMPLING_SUMMARY = _svg_icon(  # sparkles: AI-powered summary
    '<path d="M12 3l1.912 5.813a2 2 0 0 0 1.275 1.275L21 12'
    'l-5.813 1.912a2 2 0 0 0-1.275 1.275L12 21'
    'l-1.912-5.813a2 2 0 0 0-1.275-1.275L3 12'
    'l5.813-1.912a2 2 0 0 0 1.275-1.275L12 3z"/>'
)

ICON_SAMPLING_PROMPT = _svg_icon(  # wand: AI-generated prompt
    '<path d="M15 4V2"/>'
    '<path d="M15 16v-2"/>'
    '<path d="M8 9h2"/>'
    '<path d="M20 9h2"/>'
    '<path d="M17.8 11.8L19 13"/>'
    '<path d="M15 9h.01"/>'
    '<path d="M17.8 6.2L19 5"/>'
    '<path d="m3 21 9-9"/>'
    '<path d="M12.2 6.2L11 5"/>'
)

ICON_SAMPLING_ANALYSIS = _svg_icon(  # search-code: AI log analysis
    '<path d="m9 9-2 2 2 2"/>'
    '<path d="m13 13 2-2-2-2"/>'
    '<circle cx="11" cy="11" r="8"/>'
    '<path d="m21 21-4.3-4.3"/>'
)

# ── Integration / platform Icons ────────────────────────

ICON_INTEGRATIONS = _svg_icon(  # puzzle: integrations
    '<path d="M19.439 7.85c-.049.322.059.648.289.878l1.568 1.568c.47.47.706 1.087.706'
    ' 1.704s-.235 1.233-.706 1.704l-1.611 1.611a.98.98 0 0 1-.837.276c-.47-.07-.802'
    '-.48-.968-.925a2.501 2.501 0 1 0-3.214 3.214c.446.166.855.497.925.968a.979.979 0'
    ' 0 1-.276.837l-1.61 1.61a2.404 2.404 0 0 1-1.705.707 2.402 2.402 0 0 1-1.704'
    '-.706l-1.568-1.568a1.026 1.026 0 0 0-.877-.29c-.493.074-.84.504-1.005.95a2.5 2.5'
    ' 0 1 1-3.214-3.214c.446-.166.876-.516.95-1.005.043-.322-.059-.648-.289-.878'
    'l-1.568-1.568A2.41 2.41 0 0 1 1.998 12c0-.617.236-1.234.706-1.704L4.23 8.77'
    'c.24-.24.581-.35.837-.276.47.07.802.48.968.925a2.501 2.501 0 1 0 3.214-3.214'
    'c-.446-.166-.855-.497-.925-.968a.979.979 0 0 1 .276-.837l1.61-1.61A2.404 2.404'
    ' 0 0 1 11.914 2c.617 0 1.234.236 1.704.706l1.568 1.568c.23.23.556.338.877.29'
    '.493-.074.84-.504 1.005-.95a2.5 2.5 0 1 1 3.214 3.214c-.446.166-.876.516-.95'
    ' 1.005z"/>'
)

ICON_WEBHOOK = _svg_icon(  # webhook: webhook config
    '<path d="M18 16.98h-5.99c-1.1 0-1.95.94-2.48 1.9A4 4 0 0 1 2 17c.01-.7.2-1.4.57-2"/>'
    '<path d="m6 17 3.13-5.78c.53-.97.1-2.18-.5-3.1a4 4 0 1 1 6.89-4.06"/>'
    '<path d="m12 6 3.13 5.73C15.66 12.7 16.9 13 18 13a4 4 0 0 1 0 8"/>'
)

ICON_SETUP_CMD = _svg_icon(  # terminal: setup commands
    '<polyline points="4 17 10 11 4 5"/>'
    '<line x1="12" y1="19" x2="20" y2="19"/>'
)

ICON_SANDBOX = _svg_icon(  # box: sandbox
    '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8'
    'a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>'
    '<polyline points="3.27 6.96 12 12.01 20.73 6.96"/>'
    '<line x1="12" y1="22.08" x2="12" y2="12"/>'
)

ICON_CHECK_SUITE = _svg_icon(  # check-square: check suite settings
    '<polyline points="9 11 12 14 22 4"/>'
    '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>'
)

ICON_SLACK = _svg_icon(  # message-circle: slack connect
    '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0'
    ' 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38'
    ' 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>'
)

ICON_GUIDE = _svg_icon(  # book-open: integrations guide
    '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
    '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>'
)

ICON_CLI = _svg_icon(  # terminal: CLI/SDK docs
    '<polyline points="4 17 10 11 4 5"/>'
    '<line x1="12" y1="19" x2="20" y2="19"/>'
)

"""Integration, webhook, sandbox, and Slack connect tools.

Covers the following Codegen API domains:
- Organization integrations (GET /organizations/{org_id}/integrations)
- Webhook CRUD (GET/POST/DELETE /organizations/{org_id}/webhooks/agent-run)
- Webhook test (POST /organizations/{org_id}/webhooks/agent-run/test)
- Sandbox log analysis (POST /organizations/{org_id}/sandbox/{sandbox_id}/analyze-logs)
- Slack connect token (POST /slack-connect/generate-token)
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.elicitation import confirm_action
from bridge.icons import (
    ICON_INTEGRATIONS,
    ICON_SANDBOX,
    ICON_SLACK,
    ICON_WEBHOOK,
)


def register_integration_tools(mcp: FastMCP) -> None:
    """Register all integration, webhook, sandbox, and Slack tools."""

    # ── Integrations ─────────────────────────────────────

    @mcp.tool(tags={"integrations"}, icons=ICON_INTEGRATIONS)
    async def codegen_get_integrations(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Get all integration statuses for the organization.

        Returns a comprehensive overview of configured integrations including
        OAuth-based (Slack, Linear, Notion, Figma, etc.), GitHub app installations,
        and API key-based integrations (CircleCI).
        """
        await ctx.info("Fetching organization integrations")
        result = await client.get_integrations()
        await ctx.info(
            f"Found {result.total_active_integrations} active integrations "
            f"out of {len(result.integrations)} total"
        )
        return json.dumps(
            {
                "organization_id": result.organization_id,
                "organization_name": result.organization_name,
                "total_active": result.total_active_integrations,
                "integrations": [
                    {
                        "type": i.integration_type,
                        "active": i.active,
                        **({"token_id": i.token_id} if i.token_id else {}),
                        **({"installation_id": i.installation_id} if i.installation_id else {}),
                        **({"metadata": i.metadata} if i.metadata else {}),
                    }
                    for i in result.integrations
                ],
            }
        )

    # ── Webhooks ─────────────────────────────────────────

    @mcp.tool(tags={"webhooks"}, icons=ICON_WEBHOOK)
    async def codegen_get_webhook_config(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Get webhook configuration for agent run completion events.

        Returns the current webhook URL, enabled status, and whether a secret
        is configured. The actual secret value is never returned.
        """
        await ctx.info("Fetching webhook configuration")
        config = await client.get_webhook_config()
        await ctx.info(f"Webhook enabled={config.enabled}, has_secret={config.has_secret}")
        return json.dumps(
            {
                "url": config.url,
                "enabled": config.enabled,
                "has_secret": config.has_secret,
            }
        )

    @mcp.tool(tags={"webhooks"}, icons=ICON_WEBHOOK)
    async def codegen_set_webhook_config(
        url: str,
        secret: str | None = None,
        enabled: bool = True,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Configure webhook for agent run completion events.

        Set the URL where notifications will be sent when agent runs complete.
        Optionally configure a secret for HMAC signature verification.

        Args:
            url: Webhook endpoint URL (must be a valid HTTPS URL).
            secret: Optional secret for HMAC signature verification.
            enabled: Whether the webhook is active (default True).
            confirmed: Skip interactive confirmation when True.
        """
        if not confirmed:
            user_confirmed = await confirm_action(
                ctx,
                f"Set webhook URL to {url} (enabled={enabled})?",
            )
            if not user_confirmed:
                return json.dumps(
                    {"action": "cancelled", "reason": "User declined to set webhook"}
                )

        await ctx.info(f"Setting webhook config: url={url}, enabled={enabled}")
        result = await client.set_webhook_config(url, secret=secret, enabled=enabled)
        await ctx.info("Webhook configuration updated")
        return json.dumps({"status": "configured", "result": result})

    @mcp.tool(tags={"webhooks", "dangerous"}, icons=ICON_WEBHOOK)
    async def codegen_delete_webhook_config(
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Remove webhook configuration for agent run completion events.

        Deletes the webhook URL, secret, and disables notifications.

        Args:
            confirmed: Skip interactive confirmation when True.
        """
        if not confirmed:
            user_confirmed = await confirm_action(
                ctx,
                "Are you sure you want to delete the webhook configuration? "
                "This will stop all webhook notifications.",
            )
            if not user_confirmed:
                return json.dumps(
                    {"action": "cancelled", "reason": "User declined to delete webhook"}
                )

        await ctx.warning("Deleting webhook configuration")
        result = await client.delete_webhook_config()
        await ctx.info("Webhook configuration deleted")
        return json.dumps({"status": "deleted", "result": result})

    @mcp.tool(tags={"webhooks"}, icons=ICON_WEBHOOK)
    async def codegen_test_webhook(
        url: str,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Send a test webhook to verify the endpoint is reachable.

        Sends a test payload to the provided URL to verify connectivity.

        Args:
            url: Webhook endpoint URL to test.
        """
        await ctx.info(f"Testing webhook: url={url}")
        result = await client.test_webhook(url)
        await ctx.info("Webhook test sent")
        return json.dumps({"status": "test_sent", "result": result})

    # ── Sandbox ──────────────────────────────────────────

    @mcp.tool(tags={"sandbox"}, icons=ICON_SANDBOX)
    async def codegen_analyze_sandbox_logs(
        sandbox_id: int,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Analyze sandbox setup logs using an AI agent.

        Creates an AI agent that analyzes the setup logs, identifies errors,
        provides insights, and suggests solutions. The analysis runs
        asynchronously — use the returned agent_run_id to check results.

        Args:
            sandbox_id: Sandbox ID whose logs to analyze.
        """
        await ctx.info(f"Analyzing sandbox logs: sandbox_id={sandbox_id}")
        result = await client.analyze_sandbox_logs(sandbox_id)
        await ctx.info(
            f"Sandbox analysis started: agent_run_id={result.agent_run_id}, status={result.status}"
        )
        return json.dumps(
            {
                "agent_run_id": result.agent_run_id,
                "status": result.status,
                "message": result.message,
            }
        )

    # ── Slack Connect ────────────────────────────────────

    @mcp.tool(tags={"slack"}, icons=ICON_SLACK)
    async def codegen_generate_slack_token(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Generate a temporary token for Slack account connection.

        The token expires in 10 minutes and can only be used once.
        Send it to the Codegen bot in a DM with format:
        ``Connect my account: {token}``
        """
        await ctx.info("Generating Slack connect token")
        result = await client.generate_slack_connect_token()
        await ctx.info(f"Slack token generated, expires in {result.expires_in_minutes} minutes")
        return json.dumps(
            {
                "token": result.token,
                "message": result.message,
                "expires_in_minutes": result.expires_in_minutes,
            }
        )

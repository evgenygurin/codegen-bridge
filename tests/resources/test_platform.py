"""Tests for platform documentation resources (integrations guide, CLI/SDK docs)."""

from __future__ import annotations

import json

from fastmcp import Client


class TestIntegrationsGuideResource:
    """Tests for codegen://platform/integrations-guide."""

    async def test_resource_registered(self, client: Client):
        resources = await client.list_resources()
        uris = {str(r.uri) for r in resources}
        assert "codegen://platform/integrations-guide" in uris

    async def test_returns_valid_json(self, client: Client):
        result = await client.read_resource("codegen://platform/integrations-guide")
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    async def test_has_title(self, client: Client):
        result = await client.read_resource("codegen://platform/integrations-guide")
        data = json.loads(result[0].text)
        assert "title" in data
        assert "Integrations Guide" in data["title"]

    async def test_has_description(self, client: Client):
        result = await client.read_resource("codegen://platform/integrations-guide")
        data = json.loads(result[0].text)
        assert "description" in data
        assert len(data["description"]) > 0

    async def test_contains_all_integrations(self, client: Client):
        result = await client.read_resource("codegen://platform/integrations-guide")
        data = json.loads(result[0].text)
        names = {i["name"] for i in data["integrations"]}
        expected = {"GitHub", "Linear", "Slack", "Jira", "Figma", "Notion", "Sentry"}
        assert names == expected

    async def test_each_integration_has_required_fields(self, client: Client):
        result = await client.read_resource("codegen://platform/integrations-guide")
        data = json.loads(result[0].text)
        required_fields = {"name", "type", "description", "capabilities", "setup", "auth_method"}
        for integration in data["integrations"]:
            missing = required_fields - set(integration.keys())
            assert not missing, f"{integration['name']} missing fields: {missing}"

    async def test_each_integration_has_capabilities(self, client: Client):
        result = await client.read_resource("codegen://platform/integrations-guide")
        data = json.loads(result[0].text)
        for integration in data["integrations"]:
            assert isinstance(integration["capabilities"], list)
            assert len(integration["capabilities"]) > 0, (
                f"{integration['name']} has no capabilities"
            )

    async def test_has_notes(self, client: Client):
        result = await client.read_resource("codegen://platform/integrations-guide")
        data = json.loads(result[0].text)
        assert "notes" in data
        assert "codegen_get_integrations" in data["notes"]


class TestCliSdkResource:
    """Tests for codegen://platform/cli-sdk."""

    async def test_resource_registered(self, client: Client):
        resources = await client.list_resources()
        uris = {str(r.uri) for r in resources}
        assert "codegen://platform/cli-sdk" in uris

    async def test_returns_valid_json(self, client: Client):
        result = await client.read_resource("codegen://platform/cli-sdk")
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    async def test_has_title(self, client: Client):
        result = await client.read_resource("codegen://platform/cli-sdk")
        data = json.loads(result[0].text)
        assert "title" in data
        assert "CLI" in data["title"]

    async def test_has_cli_section(self, client: Client):
        result = await client.read_resource("codegen://platform/cli-sdk")
        data = json.loads(result[0].text)
        assert "cli" in data
        cli = data["cli"]
        assert "installation" in cli
        assert "commands" in cli

    async def test_cli_has_key_commands(self, client: Client):
        result = await client.read_resource("codegen://platform/cli-sdk")
        data = json.loads(result[0].text)
        commands = {c["command"] for c in data["cli"]["commands"]}
        assert "codegen" in commands
        assert "cg status" in commands
        assert "cg logs" in commands

    async def test_each_command_has_required_fields(self, client: Client):
        result = await client.read_resource("codegen://platform/cli-sdk")
        data = json.loads(result[0].text)
        required_fields = {"command", "description", "usage", "examples"}
        for cmd in data["cli"]["commands"]:
            missing = required_fields - set(cmd.keys())
            assert not missing, f"Command '{cmd['command']}' missing fields: {missing}"

    async def test_has_sdk_section(self, client: Client):
        result = await client.read_resource("codegen://platform/cli-sdk")
        data = json.loads(result[0].text)
        assert "sdk" in data
        sdk = data["sdk"]
        assert "installation" in sdk
        assert "quick_start" in sdk
        assert "key_classes" in sdk

    async def test_sdk_key_classes(self, client: Client):
        result = await client.read_resource("codegen://platform/cli-sdk")
        data = json.loads(result[0].text)
        class_names = {c["name"] for c in data["sdk"]["key_classes"]}
        assert "Codegen" in class_names
        assert "AgentRun" in class_names

    async def test_has_environment_variables(self, client: Client):
        result = await client.read_resource("codegen://platform/cli-sdk")
        data = json.loads(result[0].text)
        assert "environment_variables" in data
        env_names = {e["name"] for e in data["environment_variables"]}
        assert "CODEGEN_API_KEY" in env_names
        assert "CODEGEN_ORG_ID" in env_names

    async def test_has_links(self, client: Client):
        result = await client.read_resource("codegen://platform/cli-sdk")
        data = json.loads(result[0].text)
        assert "links" in data
        assert "documentation" in data["links"]
        assert "api_reference" in data["links"]

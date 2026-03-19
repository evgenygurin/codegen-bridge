"""Tests for the remote Codegen MCP proxy provider factory."""

from __future__ import annotations

import os
from unittest.mock import patch

from bridge.providers.remote import DEFAULT_REMOTE_MCP_URL, create_remote_proxy


class TestCreateRemoteProxy:
    def test_returns_none_when_api_key_empty(self):
        result = create_remote_proxy(api_key="")
        assert result is None

    def test_returns_none_when_creation_fails(self):
        """Exception during proxy creation returns None (graceful degradation)."""
        with patch(
            "bridge.providers.remote.StreamableHttpTransport",
            side_effect=RuntimeError("boom"),
        ):
            result = create_remote_proxy(api_key="test-key")
            assert result is None

    def test_default_url_used_when_no_override(self):
        """Without override, uses DEFAULT_REMOTE_MCP_URL."""
        with (
            patch.dict(os.environ, {}, clear=False),
            patch("bridge.providers.remote.StreamableHttpTransport") as mock_transport,
            patch("bridge.providers.remote.Client"),
            patch("bridge.providers.remote.create_proxy") as mock_create,
        ):
            mock_create.return_value = object()  # sentinel proxy
            # Remove env override if present
            os.environ.pop("CODEGEN_REMOTE_MCP_URL", None)

            result = create_remote_proxy(api_key="test-key")
            assert result is not None
            mock_transport.assert_called_once_with(url=DEFAULT_REMOTE_MCP_URL, auth="test-key")

    def test_env_var_overrides_default_url(self):
        """CODEGEN_REMOTE_MCP_URL env var takes precedence."""
        custom_url = "https://custom.mcp.example.com/mcp/"
        with (
            patch.dict(os.environ, {"CODEGEN_REMOTE_MCP_URL": custom_url}),
            patch("bridge.providers.remote.StreamableHttpTransport") as mock_transport,
            patch("bridge.providers.remote.Client"),
            patch("bridge.providers.remote.create_proxy") as mock_create,
        ):
            mock_create.return_value = object()
            result = create_remote_proxy(api_key="my-key")
            assert result is not None
            mock_transport.assert_called_once_with(url=custom_url, auth="my-key")

    def test_explicit_url_overrides_env_var(self):
        """Explicit remote_url param takes precedence over env var."""
        explicit = "https://explicit.example.com/mcp/"
        with (
            patch.dict(os.environ, {"CODEGEN_REMOTE_MCP_URL": "https://env.example.com/"}),
            patch("bridge.providers.remote.StreamableHttpTransport") as mock_transport,
            patch("bridge.providers.remote.Client"),
            patch("bridge.providers.remote.create_proxy") as mock_create,
        ):
            mock_create.return_value = object()
            result = create_remote_proxy(api_key="key", remote_url=explicit)
            assert result is not None
            mock_transport.assert_called_once_with(url=explicit, auth="key")

    def test_proxy_created_with_client_and_name(self):
        """Verify create_proxy receives Client and correct name."""
        with (
            patch("bridge.providers.remote.StreamableHttpTransport"),
            patch("bridge.providers.remote.Client") as mock_client_cls,
            patch("bridge.providers.remote.create_proxy") as mock_create,
        ):
            sentinel = object()
            mock_create.return_value = sentinel
            client_instance = mock_client_cls.return_value

            result = create_remote_proxy(api_key="k", namespace="custom")
            assert result is sentinel
            mock_create.assert_called_once_with(client_instance, name="Codegen Remote (custom)")

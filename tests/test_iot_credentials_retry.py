"""Regression tests for Anthbot IoT credential refresh handling."""

from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).parents[1]
PACKAGE = "custom_components.anthbot_map"


def _load_api_module():
    """Load api.py without importing the full Home Assistant integration."""
    homeassistant = types.ModuleType("homeassistant")
    homeassistant_exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        """Minimal Home Assistant error stub."""

    homeassistant_exceptions.HomeAssistantError = HomeAssistantError
    homeassistant.exceptions = homeassistant_exceptions
    sys.modules.setdefault("homeassistant", homeassistant)
    sys.modules.setdefault("homeassistant.exceptions", homeassistant_exceptions)

    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        """Minimal aiohttp client error stub."""

    class ClientSession:
        """Minimal aiohttp client session stub."""

    aiohttp.ClientError = ClientError
    aiohttp.ClientSession = ClientSession
    sys.modules.setdefault("aiohttp", aiohttp)

    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    sys.modules.setdefault("custom_components", custom_components)

    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components/anthbot_map")]
    sys.modules.setdefault(PACKAGE, package)

    const_name = f"{PACKAGE}.const"
    if const_name not in sys.modules:
        const_spec = importlib.util.spec_from_file_location(
            const_name,
            ROOT / "custom_components/anthbot_map/const.py",
        )
        const_module = importlib.util.module_from_spec(const_spec)
        sys.modules[const_name] = const_module
        assert const_spec.loader is not None
        const_spec.loader.exec_module(const_module)

    api_name = f"{PACKAGE}.api"
    api_spec = importlib.util.spec_from_file_location(
        api_name,
        ROOT / "custom_components/anthbot_map/api.py",
    )
    api_module = importlib.util.module_from_spec(api_spec)
    sys.modules[api_name] = api_module
    assert api_spec.loader is not None
    api_spec.loader.exec_module(api_module)
    return api_module


api = _load_api_module()


def _credentials(*, expires_in: int = 3600):
    return api.AnthbotTemporaryIotCredentials(
        access_key_id="access",
        secret_access_key="secret",
        session_token="session",
        region_name="eu-central-1",
        endpoint="example.iot.eu-central-1.amazonaws.com",
        expiration=int(time.time()) + expires_in,
    )


class TestIotCredentialRetry(unittest.IsolatedAsyncioTestCase):
    """Verify retry, reauthentication and cached credential behavior."""

    def _client(self, account_client):
        return api.AnthbotShadowApiClient(
            session=object(),
            serial_number="TEST123",
            region_name="eu-central-1",
            iot_endpoint="example.iot.eu-central-1.amazonaws.com",
            account_client=account_client,
        )

    async def test_temporary_failures_retry_without_reauthentication(self) -> None:
        account_client = types.SimpleNamespace(
            async_get_device_iot_credentials=AsyncMock(
                side_effect=[
                    api.AnthbotGenieApiError(
                        "IoT STS failed (500)",
                        status_code=500,
                    ),
                    api.AnthbotGenieApiError(
                        "Request timed out",
                        temporary=True,
                    ),
                    _credentials(),
                ]
            ),
            async_reauthenticate=AsyncMock(),
        )
        client = self._client(account_client)

        with patch.object(api.asyncio, "sleep", new=AsyncMock()) as sleep:
            result = await client._async_get_credentials()

        self.assertEqual(result.access_key_id, "access")
        self.assertEqual(
            account_client.async_get_device_iot_credentials.await_count,
            3,
        )
        account_client.async_reauthenticate.assert_not_awaited()
        self.assertEqual([call.args[0] for call in sleep.await_args_list], [1, 3])

    async def test_authentication_error_reauthenticates_once(self) -> None:
        account_client = types.SimpleNamespace(
            async_get_device_iot_credentials=AsyncMock(
                side_effect=[
                    api.AnthbotGenieApiError(
                        "IoT STS failed (401)",
                        status_code=401,
                    ),
                    _credentials(),
                ]
            ),
            async_reauthenticate=AsyncMock(),
        )
        client = self._client(account_client)

        result = await client._async_get_credentials()

        self.assertEqual(result.access_key_id, "access")
        account_client.async_reauthenticate.assert_awaited_once_with()
        self.assertEqual(
            account_client.async_get_device_iot_credentials.await_count,
            2,
        )

    async def test_temporary_failure_uses_only_unexpired_cached_credentials(
        self,
    ) -> None:
        failure = api.AnthbotGenieApiError(
            "IoT STS failed (502)",
            status_code=502,
        )
        account_client = types.SimpleNamespace(
            async_get_device_iot_credentials=AsyncMock(side_effect=failure),
            async_reauthenticate=AsyncMock(),
        )
        client = self._client(account_client)
        cached = _credentials(expires_in=30)
        client._credentials = cached
        client._credentials_acquired_at = time.time()

        with (
            patch.object(api.asyncio, "sleep", new=AsyncMock()),
            patch.object(api._LOGGER, "warning"),
        ):
            result = await client._async_get_credentials()

        self.assertIs(result, cached)
        account_client.async_reauthenticate.assert_not_awaited()

        client._credentials = replace(cached, expiration=int(time.time()) - 1)
        with (
            patch.object(api.asyncio, "sleep", new=AsyncMock()),
            patch.object(api._LOGGER, "warning"),
        ):
            with self.assertRaises(api.AnthbotGenieApiError):
                await client._async_get_credentials()

    async def test_forced_refresh_never_reuses_rejected_credentials(self) -> None:
        failure = api.AnthbotGenieApiError(
            "IoT STS failed (503)",
            status_code=503,
        )
        account_client = types.SimpleNamespace(
            async_get_device_iot_credentials=AsyncMock(side_effect=failure),
            async_reauthenticate=AsyncMock(),
        )
        client = self._client(account_client)
        client._credentials = _credentials()
        client._credentials_acquired_at = time.time()

        with (
            patch.object(api.asyncio, "sleep", new=AsyncMock()),
            patch.object(api._LOGGER, "warning"),
        ):
            with self.assertRaises(api.AnthbotGenieApiError):
                await client._async_get_credentials(force_refresh=True)

        account_client.async_reauthenticate.assert_not_awaited()

    async def test_non_temporary_failure_is_not_retried_or_cached(self) -> None:
        failure = api.AnthbotGenieApiError(
            "IoT STS failed (400)",
            status_code=400,
        )
        account_client = types.SimpleNamespace(
            async_get_device_iot_credentials=AsyncMock(side_effect=failure),
            async_reauthenticate=AsyncMock(),
        )
        client = self._client(account_client)
        client._credentials = _credentials(expires_in=-1)
        client._credentials_acquired_at = time.time()

        with patch.object(api._LOGGER, "warning"):
            with self.assertRaises(api.AnthbotGenieApiError) as raised:
                await client._async_get_credentials()

        self.assertIs(raised.exception, failure)
        account_client.async_get_device_iot_credentials.assert_awaited_once_with(
            "TEST123"
        )
        account_client.async_reauthenticate.assert_not_awaited()

    def test_sts_lifetime_is_normalized_to_absolute_expiration(self) -> None:
        """Anthbot's duration-style STS value must not resolve to 1970."""
        with patch.object(api.time, "time", return_value=1_700_000_000):
            self.assertEqual(
                api.AnthbotCloudApiClient._parse_expiration(3600),
                1_700_003_600,
            )

    async def test_live_mqtt_transport_is_preferred_for_commands(self) -> None:
        """An active MQTT socket should carry commands without an HTTP call."""
        account_client = types.SimpleNamespace(
            async_get_device_iot_credentials=AsyncMock(),
            async_reauthenticate=AsyncMock(),
        )
        client = self._client(account_client)
        publisher = AsyncMock()
        client.set_live_command_publisher(publisher)

        with patch.object(
            client,
            "_async_signed_post",
            new=AsyncMock(),
        ) as signed_post:
            await client.async_publish_service_command(cmd="get_all_props", data=1)

        publisher.assert_awaited_once()
        topic, payload = publisher.await_args.args
        self.assertEqual(
            topic,
            "$aws/things/TEST123/shadow/name/service/update",
        )
        self.assertEqual(
            payload,
            b'{"state":{"desired":{"cmd":"get_all_props","data":1}}}',
        )
        signed_post.assert_not_awaited()

    async def test_failed_mqtt_command_is_not_replayed_over_http(self) -> None:
        """Match the app: a failed MQTT command has no HTTP Publish fallback."""
        account_client = types.SimpleNamespace(
            async_get_device_iot_credentials=AsyncMock(),
            async_reauthenticate=AsyncMock(),
        )
        client = self._client(account_client)
        publisher = AsyncMock(side_effect=RuntimeError("socket closed"))
        client.set_live_command_publisher(publisher)
        signed_post = AsyncMock(return_value=(200, "", None, {}))

        with patch.object(client, "_async_signed_post", new=signed_post):
            with self.assertRaisesRegex(RuntimeError, "socket closed"):
                await client.async_publish_service_command(cmd="charge_start")

        publisher.assert_awaited_once()
        signed_post.assert_not_awaited()
        self.assertEqual(
            publisher.await_args.args[1],
            b'{"state":{"desired":{"cmd":"charge_start"}}}',
        )

    async def test_disconnected_command_is_not_published_over_http(self) -> None:
        """The mobile app sends service-shadow commands only over MQTT."""
        account_client = types.SimpleNamespace(
            async_get_device_iot_credentials=AsyncMock(),
            async_reauthenticate=AsyncMock(),
        )
        client = self._client(account_client)
        signed_post = AsyncMock()

        with (
            patch.object(client, "_async_signed_post", new=signed_post),
        ):
            with self.assertRaises(api.AnthbotGenieApiError):
                await client.async_publish_service_command(cmd="start", data=1)

        signed_post.assert_not_awaited()
        account_client.async_reauthenticate.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()

"""Config flow for Anthbot Genie."""

from __future__ import annotations

import logging
import uuid

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, __version__ as HA_VERSION
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AnthbotCloudApiClient, AnthbotGenieApiError
from .const import (
    CONF_API_HOST,
    CONF_AREA_CODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_BATTERY_SAVER_CONFIGS,
    CONF_CHARGE_LIMIT,
    CONF_CHARGER_SWITCH,
    CONF_DEVELOPER_INSTALLATION_ID,
    CONF_MAINTENANCE_LEVEL,
    CONF_RESUME_LEVEL,
    CONF_SEND_AUTOMATIC_DIAGNOSTICS,
    CONF_SHARE_ANONYMOUS_USAGE,
    CONF_SHARED_RTK_POWER,
    CONF_USERNAME,
    COUNTRY_AREA_CODES,
    DEFAULT_API_HOST,
    DEFAULT_AREA_CODE,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_BATTERY_SAVER_CHARGE_LIMIT,
    DEFAULT_BATTERY_SAVER_MAINTENANCE_LEVEL,
    DEFAULT_BATTERY_SAVER_RESUME_LEVEL,
    DEFAULT_SEND_AUTOMATIC_DIAGNOSTICS,
    DEFAULT_SHARE_ANONYMOUS_USAGE,
    DEVELOPER_TELEMETRY_ENDPOINT,
    DOMAIN,
)
from .developer_reporting import async_send_anonymous_usage_report

_LOGGER = logging.getLogger(__name__)
_PRIVACY_URL = (
    "https://github.com/Mqbretrofit/ha-anthbot-map-v2/blob/"
    "test/no-go-path-crossing-diagnostics/PRIVACY.md"
)


class AnthbotGenieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Anthbot configuration flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AnthbotGenieOptionsFlow:
        """Return Anthbot integration options."""
        return AnthbotGenieOptionsFlow()

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if self._async_current_entries():
                return self.async_abort(reason="already_configured")

            session = async_get_clientsession(self.hass)
            cloud_client = AnthbotCloudApiClient(
                session=session,
                host=user_input[CONF_API_HOST],
            )
            try:
                await cloud_client.async_login(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    area_code=user_input[CONF_AREA_CODE],
                )
                devices = await cloud_client.async_get_bound_devices()
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    entry_data = dict(user_input)
                    installation_id = str(uuid.uuid4())
                    entry_data[CONF_DEVELOPER_INSTALLATION_ID] = installation_id

                    if bool(user_input.get(CONF_SHARE_ANONYMOUS_USAGE, False)):
                        # Best effort only: reporting must never delay or block
                        # successful Anthbot setup.
                        self.hass.async_create_task(
                            async_send_anonymous_usage_report(
                                session,
                                DEVELOPER_TELEMETRY_ENDPOINT,
                                installation_id=installation_id,
                                area_code=user_input[CONF_AREA_CODE],
                                devices=devices,
                                home_assistant_version=HA_VERSION,
                                event="installation",
                            )
                        )

                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=entry_data,
                    )
            except AnthbotGenieApiError as err:
                _LOGGER.warning("Anthbot login or device discovery failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

        country_options = [
            selector.SelectOptionDict(value=code, label=label)
            for label, code in COUNTRY_AREA_CODES
        ]
        non_empty_string = vol.All(str, vol.Strip, vol.Length(min=1))

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): non_empty_string,
                vol.Required(CONF_USERNAME): non_empty_string,
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_API_HOST, default=DEFAULT_API_HOST): non_empty_string,
                vol.Required(CONF_AREA_CODE, default=DEFAULT_AREA_CODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=country_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                vol.Optional(
                    CONF_SHARE_ANONYMOUS_USAGE,
                    default=DEFAULT_SHARE_ANONYMOUS_USAGE,
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_SEND_AUTOMATIC_DIAGNOSTICS,
                    default=DEFAULT_SEND_AUTOMATIC_DIAGNOSTICS,
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"privacy_url": _PRIVACY_URL},
        )


class AnthbotGenieOptionsFlow(config_entries.OptionsFlow):
    """Configure developer reporting and optional battery-saving behavior."""

    def __init__(self) -> None:
        self._serial_number: str | None = None

    def _coordinators(self) -> list:
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, [])

    def _current_option(self, key: str, default: bool = False) -> bool:
        if key in self.config_entry.options:
            return bool(self.config_entry.options.get(key))
        return bool(self.config_entry.data.get(key, default))

    def _installation_id(self) -> str:
        """Return a stable local reporting ID, creating one for legacy entries."""
        value = self.config_entry.options.get(CONF_DEVELOPER_INSTALLATION_ID)
        if not isinstance(value, str) or not value:
            value = self.config_entry.data.get(CONF_DEVELOPER_INSTALLATION_ID)
        if isinstance(value, str) and value:
            return value
        return str(uuid.uuid4())

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Choose which group of integration settings to edit."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["developer_reporting", "battery_saver"],
        )

    async def async_step_developer_reporting(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure the two independent opt-in developer-reporting choices."""
        current_usage = self._current_option(
            CONF_SHARE_ANONYMOUS_USAGE, DEFAULT_SHARE_ANONYMOUS_USAGE
        )
        current_diagnostics = self._current_option(
            CONF_SEND_AUTOMATIC_DIAGNOSTICS,
            DEFAULT_SEND_AUTOMATIC_DIAGNOSTICS,
        )

        if user_input is not None:
            new_usage = bool(user_input.get(CONF_SHARE_ANONYMOUS_USAGE, False))
            new_diagnostics = bool(
                user_input.get(CONF_SEND_AUTOMATIC_DIAGNOSTICS, False)
            )
            installation_id = self._installation_id()
            options = dict(self.config_entry.options)
            options[CONF_SHARE_ANONYMOUS_USAGE] = new_usage
            options[CONF_SEND_AUTOMATIC_DIAGNOSTICS] = new_diagnostics
            options[CONF_DEVELOPER_INSTALLATION_ID] = installation_id

            # If an existing user opts in later, send the same minimal
            # installation payload once at the moment of opt-in.
            if new_usage and not current_usage:
                coordinators = self._coordinators()
                if coordinators:
                    session = async_get_clientsession(self.hass)
                    self.hass.async_create_task(
                        async_send_anonymous_usage_report(
                            session,
                            DEVELOPER_TELEMETRY_ENDPOINT,
                            installation_id=installation_id,
                            area_code=self.config_entry.data.get(CONF_AREA_CODE),
                            devices=[coordinator.device for coordinator in coordinators],
                            home_assistant_version=HA_VERSION,
                            event="opt_in",
                        )
                    )

            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="developer_reporting",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SHARE_ANONYMOUS_USAGE,
                        default=current_usage,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_SEND_AUTOMATIC_DIAGNOSTICS,
                        default=current_diagnostics,
                    ): selector.BooleanSelector(),
                }
            ),
            description_placeholders={"privacy_url": _PRIVACY_URL},
        )

    async def async_step_battery_saver(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Choose the mower whose battery-saver settings should be edited."""
        coordinators = self._coordinators()
        if not coordinators:
            return self.async_abort(reason="no_devices")
        if len(coordinators) == 1:
            self._serial_number = coordinators[0].client.serial_number
            return await self.async_step_battery_saver_settings()
        if user_input is not None:
            self._serial_number = user_input["mower"]
            return await self.async_step_battery_saver_settings()
        options = [
            selector.SelectOptionDict(
                value=coordinator.client.serial_number,
                label=f"{coordinator.device.alias} ({coordinator.client.serial_number})",
            )
            for coordinator in coordinators
        ]
        return self.async_show_form(
            step_id="battery_saver",
            data_schema=vol.Schema(
                {
                    vol.Required("mower"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_battery_saver_settings(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure charger entity and charge thresholds."""
        if self._serial_number is None:
            return await self.async_step_battery_saver()
        stored_configs = self.config_entry.options.get(CONF_BATTERY_SAVER_CONFIGS, {})
        configs = dict(stored_configs) if isinstance(stored_configs, dict) else {}
        current = configs.get(self._serial_number, {})
        if not isinstance(current, dict):
            current = {}
        errors: dict[str, str] = {}
        if user_input is not None:
            if (
                user_input[CONF_RESUME_LEVEL] >= user_input[CONF_CHARGE_LIMIT]
                or user_input[CONF_MAINTENANCE_LEVEL]
                >= user_input[CONF_CHARGE_LIMIT]
            ):
                errors["base"] = "invalid_battery_thresholds"
            else:
                saved_config = dict(user_input)
                saved_config[CONF_SHARED_RTK_POWER] = bool(
                    user_input.get(
                        CONF_SHARED_RTK_POWER,
                        current.get(CONF_SHARED_RTK_POWER, False),
                    )
                )
                configs[self._serial_number] = saved_config
                options = dict(self.config_entry.options)
                options[CONF_BATTERY_SAVER_CONFIGS] = configs
                return self.async_create_entry(title="", data=options)
        charger_entity = current.get(CONF_CHARGER_SWITCH)
        charger_field = (
            vol.Required(CONF_CHARGER_SWITCH, default=charger_entity)
            if isinstance(charger_entity, str) and charger_entity
            else vol.Required(CONF_CHARGER_SWITCH)
        )
        schema_fields = {
            charger_field: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Required(
                CONF_CHARGE_LIMIT,
                default=current.get(
                    CONF_CHARGE_LIMIT,
                    DEFAULT_BATTERY_SAVER_CHARGE_LIMIT,
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=20, max=100)),
            vol.Required(
                CONF_MAINTENANCE_LEVEL,
                default=current.get(
                    CONF_MAINTENANCE_LEVEL,
                    DEFAULT_BATTERY_SAVER_MAINTENANCE_LEVEL,
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=99)),
            vol.Required(
                CONF_RESUME_LEVEL,
                default=current.get(
                    CONF_RESUME_LEVEL,
                    DEFAULT_BATTERY_SAVER_RESUME_LEVEL,
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=99)),
            vol.Required(
                CONF_SHARED_RTK_POWER,
                default=bool(current.get(CONF_SHARED_RTK_POWER, False)),
            ): selector.BooleanSelector(),
        }
        return self.async_show_form(
            step_id="battery_saver_settings",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
            description_placeholders={"serial_number": self._serial_number},
        )

"""Config flow for Anthbot Genie."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
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
    CONF_DEVELOPER_AGENT_ENABLED,
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
    DEFAULT_DEVELOPER_AGENT_ENABLED,
    DEFAULT_SEND_AUTOMATIC_DIAGNOSTICS,
    DEFAULT_SHARE_ANONYMOUS_USAGE,
    DOMAIN,
)
from .developer_agent_optin import SERVICE_UPDATE_DEVELOPER_AGENT
from .developer_optin import SERVICE_UPDATE_DEVELOPER_REPORTING

_LOGGER = logging.getLogger(__name__)


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
                    # Developer reporting is deliberately not mixed into account
                    # setup. Consent can be changed later from integration options.
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=dict(user_input),
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
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


class AnthbotGenieOptionsFlow(config_entries.OptionsFlow):
    """Configure Anthbot integration options."""

    def __init__(self) -> None:
        self._serial_number: str | None = None

    def _coordinators(self) -> list:
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, [])

    def _entry_option(self, key: str, default: bool = False) -> bool:
        if key in self.config_entry.options:
            return bool(self.config_entry.options.get(key))
        return bool(self.config_entry.data.get(key, default))

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Choose the settings section."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["battery_saver", "developer_reporting"],
        )

    async def async_step_battery_saver(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure the existing per-mower Battery Saver settings."""
        if self._serial_number is None:
            coordinators = self._coordinators()
            if not coordinators:
                return self.async_abort(reason="no_devices")
            if len(coordinators) == 1:
                self._serial_number = coordinators[0].client.serial_number
            else:
                return await self.async_step_battery_saver_mower()

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
                saved_config = {
                    CONF_CHARGER_SWITCH: user_input[CONF_CHARGER_SWITCH],
                    CONF_CHARGE_LIMIT: user_input[CONF_CHARGE_LIMIT],
                    CONF_MAINTENANCE_LEVEL: user_input[CONF_MAINTENANCE_LEVEL],
                    CONF_RESUME_LEVEL: user_input[CONF_RESUME_LEVEL],
                    CONF_SHARED_RTK_POWER: bool(
                        user_input.get(
                            CONF_SHARED_RTK_POWER,
                            current.get(CONF_SHARED_RTK_POWER, False),
                        )
                    ),
                }
                configs[self._serial_number] = saved_config

                # Preserve every unrelated option exactly as-is. Battery Saver
                # must never overwrite developer-reporting consent or other data.
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
            step_id="battery_saver",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
            description_placeholders={
                "serial_number": self._serial_number,
            },
        )

    async def async_step_battery_saver_mower(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Choose which discovered mower should use Battery Saver settings."""
        coordinators = self._coordinators()
        if not coordinators:
            return self.async_abort(reason="no_devices")
        if user_input is not None:
            self._serial_number = user_input["mower"]
            return await self.async_step_battery_saver()

        mower_options = [
            selector.SelectOptionDict(
                value=coordinator.client.serial_number,
                label=f"{coordinator.device.alias} ({coordinator.client.serial_number})",
            )
            for coordinator in coordinators
        ]
        return self.async_show_form(
            step_id="battery_saver_mower",
            data_schema=vol.Schema(
                {
                    vol.Required("mower"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=mower_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_developer_reporting(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure optional reporting and read-only developer access."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reporting_available = self.hass.services.has_service(
                DOMAIN, SERVICE_UPDATE_DEVELOPER_REPORTING
            )
            agent_available = self.hass.services.has_service(
                DOMAIN, SERVICE_UPDATE_DEVELOPER_AGENT
            )
            if not reporting_available or not agent_available:
                errors["base"] = "reporting_service_unavailable"
            else:
                await self.hass.services.async_call(
                    DOMAIN,
                    SERVICE_UPDATE_DEVELOPER_REPORTING,
                    {
                        CONF_SHARE_ANONYMOUS_USAGE: bool(
                            user_input[CONF_SHARE_ANONYMOUS_USAGE]
                        ),
                        CONF_SEND_AUTOMATIC_DIAGNOSTICS: bool(
                            user_input[CONF_SEND_AUTOMATIC_DIAGNOSTICS]
                        ),
                    },
                    blocking=True,
                    return_response=True,
                )
                await self.hass.services.async_call(
                    DOMAIN,
                    SERVICE_UPDATE_DEVELOPER_AGENT,
                    {
                        CONF_DEVELOPER_AGENT_ENABLED: bool(
                            user_input[CONF_DEVELOPER_AGENT_ENABLED]
                        )
                    },
                    blocking=True,
                    return_response=True,
                )
                # Both services update only their own consent fields and preserve
                # every unrelated option, including Battery Saver settings.
                return self.async_create_entry(
                    title="", data=dict(self.config_entry.options)
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SHARE_ANONYMOUS_USAGE,
                    default=self._entry_option(
                        CONF_SHARE_ANONYMOUS_USAGE,
                        DEFAULT_SHARE_ANONYMOUS_USAGE,
                    ),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_SEND_AUTOMATIC_DIAGNOSTICS,
                    default=self._entry_option(
                        CONF_SEND_AUTOMATIC_DIAGNOSTICS,
                        DEFAULT_SEND_AUTOMATIC_DIAGNOSTICS,
                    ),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_DEVELOPER_AGENT_ENABLED,
                    default=self._entry_option(
                        CONF_DEVELOPER_AGENT_ENABLED,
                        DEFAULT_DEVELOPER_AGENT_ENABLED,
                    ),
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="developer_reporting",
            data_schema=schema,
            errors=errors,
        )

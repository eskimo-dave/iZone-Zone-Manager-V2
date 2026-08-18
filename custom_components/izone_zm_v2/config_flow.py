"""
Config flow for iZone Zone Manager V2.

Prompts for the controller's host/IP, makes one real request against it to
validate connectivity, and auto-detects the number of zones from the
system response's NoOfZones field before creating the entry.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IZoneApiClient, IZoneApiError
from .const import (
    CONF_SCAN_INTERVAL_SECONDS,
    CONF_ZONE_COUNT,
    DEFAULT_NAME,
    DOMAIN,
    MIN_SCAN_INTERVAL_SECONDS,
    SCAN_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class IZoneLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iZone Zone Manager V2."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First (and only) step: ask for the host, then validate it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)
            client = IZoneApiClient(host, session)

            try:
                # One real request against the controller before we ever
                # create the entry - this both validates connectivity and
                # gives us NoOfZones so the user never has to type it in.
                system = await client.async_get_system()
            except IZoneApiError:
                _LOGGER.debug("Failed to contact iZone controller at %s", host, exc_info=True)
                errors["base"] = "cannot_connect"
            else:
                zone_count = system.get("NoOfZones")
                if not zone_count or not isinstance(zone_count, int):
                    _LOGGER.debug(
                        "Connected to %s but response had no usable NoOfZones: %s",
                        host,
                        system,
                    )
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"{DEFAULT_NAME} ({host})",
                        data={
                            CONF_HOST: host,
                            CONF_ZONE_COUNT: zone_count,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> IZoneOptionsFlow:
        """Get the options flow for this integration."""
        return IZoneOptionsFlow(config_entry)


class IZoneOptionsFlow(OptionsFlow):
    """Change host and poll interval."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options prompts for configuration."""
        errors: dict[str, str] = {}
        current_host = self.config_entry.data.get(CONF_HOST)
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_SECONDS, SCAN_INTERVAL_SECONDS
        )

        if user_input is not None:
            host = user_input[CONF_HOST]
            scan_interval = user_input[CONF_SCAN_INTERVAL_SECONDS]

            session = async_get_clientsession(self.hass)
            client = IZoneApiClient(host, session)
            try:
                # Same validate-before-saving approach as initial setup -
                # don't let a typo'd IP get saved silently.
                await client.async_get_system()
            except IZoneApiError:
                _LOGGER.debug(
                    "Failed to contact iZone controller at %s", host, exc_info=True
                )
                errors["base"] = "cannot_connect"
            else:
                # Host lives in entry.data (it's part of entry identity,
                # not options), so update it directly rather than through
                # the options dict this step otherwise returns.
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_HOST: host},
                )
                return self.async_create_entry(
                    title="",
                    data={CONF_SCAN_INTERVAL_SECONDS: scan_interval},
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current_host): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL_SECONDS, default=current_interval
                    ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL_SECONDS)),
                }
            ),
            errors=errors,
        )

"""The iZone Zone Manager V2 integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IZoneApiClient
from .const import (
    CONF_SCAN_INTERVAL_SECONDS,
    CONF_ZONE_COUNT,
    DOMAIN,
    SCAN_INTERVAL_SECONDS,
)
from .coordinator import IZoneCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iZone Local from a config entry."""
    host = entry.data[CONF_HOST]
    zone_count = entry.data[CONF_ZONE_COUNT]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL_SECONDS, SCAN_INTERVAL_SECONDS)

    session = async_get_clientsession(hass)
    api = IZoneApiClient(host, session)
    coordinator = IZoneCoordinator(hass, api, zone_count, scan_interval)

    # Raises ConfigEntryNotReady automatically if the first poll fails
    # (DataUpdateCoordinator wraps UpdateFailed for us here), which tells
    # HA to retry setup later rather than failing the entry outright.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry when its data/options change."""
    await hass.config_entries.async_reload(entry.entry_id)

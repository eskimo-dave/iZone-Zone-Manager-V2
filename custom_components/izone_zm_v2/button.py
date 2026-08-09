"""Button platform for iZone Local - favourite activation buttons."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import IZoneApiError
from .const import DOMAIN, NUM_FAVOURITES
from .coordinator import IZoneCoordinator

_LOGGER = logging.getLogger(__name__)


async def _async_get_favourite_name(coordinator: IZoneCoordinator, index: int) -> str | None:
    """Fetch one favourite's name, falling back to None on failure."""
    try:
        favourite = await coordinator.api.async_get_favourite(index)
    except IZoneApiError:
        _LOGGER.debug(
            "Could not fetch name for favourite %s, using default", index, exc_info=True
        )
        return None
    return favourite.get("Name")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up iZone favourite buttons from a config entry.

    Favourite names are fetched once at setup (they're set-and-forget on
    the controller, so there's no need to poll them continuously like zone
    state), all 9 concurrently rather than one at a time. If a name can't
    be fetched, falls back to "Favourite N" rather than failing the whole
    platform.
    """
    coordinator: IZoneCoordinator = hass.data[DOMAIN][entry.entry_id]

    names = await asyncio.gather(
        *(_async_get_favourite_name(coordinator, index) for index in range(NUM_FAVOURITES))
    )
    entities: list[ButtonEntity] = [
        IZoneFavouriteButton(coordinator, entry, index, name)
        for index, name in enumerate(names)
    ]
    async_add_entities(entities)


class IZoneFavouriteButton(CoordinatorEntity[IZoneCoordinator], ButtonEntity):
    """A button that activates one of the controller's saved favourites."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IZoneCoordinator,
        entry: ConfigEntry,
        index: int,
        name: str | None,
    ) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_favourite_{index}"
        self._attr_name = name or f"Favourite {index + 1}"
        # Grouped under the same "iZone" device as the system climate
        # entity, rather than getting their own devices.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    async def async_press(self) -> None:
        """Activate this favourite."""
        await self.coordinator.api.async_set_favourite(self._index)
        await self.coordinator.async_request_refresh()

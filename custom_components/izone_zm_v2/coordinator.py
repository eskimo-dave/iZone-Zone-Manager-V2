"""DataUpdateCoordinator for iZone ZM V2."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IZoneApiClient, IZoneApiError
from .const import DOMAIN, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


@dataclass
class IZoneData:
    """Snapshot of system + all zone states for one poll cycle."""

    system: dict[str, Any]
    zones: list[dict[str, Any]]


class IZoneCoordinator(DataUpdateCoordinator[IZoneData]):
    """Polls the iZone controller for system and zone state."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: IZoneApiClient,
        zone_count: int,
        scan_interval_seconds: int = SCAN_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval_seconds),
        )
        self.api = api
        self.zone_count = zone_count

    async def _async_update_data(self) -> IZoneData:
        try:
            system = await self.api.async_get_system()
            zones = [await self.api.async_get_zone(i) for i in range(self.zone_count)]
        except IZoneApiError as err:
            raise UpdateFailed(str(err)) from err
        return IZoneData(system=system, zones=zones)

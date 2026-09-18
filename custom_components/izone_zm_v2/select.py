"""Select platform for iZone ZM V2 - the system sleep timer."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SLEEP_TIMER_KEY,
    SLEEP_TIMER_MINUTES_TO_OPTION,
    SLEEP_TIMER_OPTIONS,
)
from .coordinator import IZoneCoordinator

_LOGGER = logging.getLogger(__name__)

SLEEP_TIMER_OFF = "Off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iZone sleep timer select from a config entry."""
    coordinator: IZoneCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Same defensive pattern as the zone skip in climate.py: if a firmware
    # doesn't report the field at all, don't create a dead entity.
    if SLEEP_TIMER_KEY not in coordinator.data.system:
        _LOGGER.debug("Controller reports no %s field, skipping", SLEEP_TIMER_KEY)
        return

    async_add_entities([IZoneSleepTimerSelect(coordinator, entry)])


class IZoneSleepTimerSelect(
    CoordinatorEntity[IZoneCoordinator], RestoreEntity, SelectEntity
):
    """
    The duration the sleep timer was last set to. "Off" cancels it.

    Deliberately NOT a live view of SleepTimer: if the controller counts
    the value down, mapping it back to an option would make a 2 hour timer
    read "1 hour" halfway through. This holds the duration that was
    requested, and the "Sleep timer remaining" sensor carries the live
    minutes. The two cases that do force a re-read from the controller are
    handled in _sync_from_controller below.
    """

    _attr_has_entity_name = True
    _attr_name = "Sleep timer"
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options: ClassVar[list[str]] = list(SLEEP_TIMER_OPTIONS)

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sleep timer select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_sleep_timer"
        # Grouped under the same "iZone" device as the system climate entity.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
        self._attr_current_option: str | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last selection, then reconcile with the controller."""
        # super() chains through CoordinatorEntity (listener) and
        # RestoreEntity (state store), so both still get set up.
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in SLEEP_TIMER_OPTIONS:
            self._attr_current_option = last_state.state

        self._sync_from_controller()

    @property
    def _minutes(self) -> int | None:
        value = self.coordinator.data.system.get(SLEEP_TIMER_KEY)
        return value if isinstance(value, int) else None

    def _sync_from_controller(self) -> None:
        """
        Reconcile the held selection against what the controller reports.

        Only two readings are trusted over what we're already showing:
        0, which means the timer finished or was cancelled; and a value
        LARGER than the selection, which a countdown can't produce and so
        must have been set from the iZone app or the wall controller.
        """
        minutes = self._minutes
        if minutes is None:
            return

        if minutes == 0:
            self._attr_current_option = SLEEP_TIMER_OFF
            return

        selected_minutes = SLEEP_TIMER_OPTIONS.get(
            self._attr_current_option or SLEEP_TIMER_OFF, 0
        )
        if minutes <= selected_minutes:
            return  # our own timer, counting down - leave the label alone

        # Set outside HA. Prefer an exact match, otherwise round up to the
        # shortest option that could still be running down to this value.
        self._attr_current_option = SLEEP_TIMER_MINUTES_TO_OPTION.get(minutes) or next(
            (
                option
                for option, value in SLEEP_TIMER_OPTIONS.items()
                if value >= minutes
            ),
            self._attr_options[-1],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle a coordinator poll."""
        self._sync_from_controller()
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Set the sleep timer to the selected duration."""
        await self.coordinator.api.async_set_sleep_timer(SLEEP_TIMER_OPTIONS[option])
        self._attr_current_option = option
        self.async_write_ha_state()  # optimistic, so the UI doesn't snap back
        await asyncio.sleep(0.5)  # same settle delay used elsewhere
        await self.coordinator.async_request_refresh()

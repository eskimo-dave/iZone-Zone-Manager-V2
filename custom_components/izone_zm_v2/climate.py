"""
Climate platform for iZone Local.

Exposes one ClimateEntity for the ducted system as a whole, plus one
ClimateEntity per zone (auto-detected at config-flow time from NoOfZones).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, ClassVar, cast

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_HOST, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FAN_MODE_TO_IZONE,
    HVAC_MODE_TO_IZONE,
    IZONE_FAN_TO_MODE,
    IZONE_MODE_TO_HVAC,
    ZONE_MODE_AUTO,
    ZONE_MODE_CLOSE,
    ZONE_MODE_OPEN,
    celsius_to_raw,
    raw_to_celsius,
)
from .coordinator import IZoneCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up iZone climate entities from a config entry."""
    coordinator: IZoneCoordinator = hass.data[DOMAIN][entry.entry_id]
    host = entry.data[CONF_HOST]

    entities: list[ClimateEntity] = [IZoneSystemClimate(coordinator, entry, host)]
    for zone_index in range(coordinator.zone_count):
        zone = coordinator.data.zones[zone_index]
        # A physically disabled/unused zone reports a raw Temp of 0, which
        # is otherwise indistinguishable from a genuine 0.00C reading -
        # skip creating an entity for it rather than showing a bogus zone.
        # Note: this only runs once at setup, so a zone enabled later on
        # the controller won't appear until the integration is reloaded.
        if zone.get("Temp") == 0:
            _LOGGER.debug(
                "Skipping zone %s (%s) - reports 0C, likely disabled",
                zone_index,
                zone.get("Name"),
            )
            continue
        entities.append(
            IZoneZoneClimate(coordinator, entry, zone_index, zone.get("Name"))
        )
    async_add_entities(entities)


class IZoneSystemClimate(CoordinatorEntity[IZoneCoordinator], ClimateEntity):
    """Representation of the iZone ducted system as a whole."""

    _attr_has_entity_name = True
    _attr_name = None  # use the device name as the entity name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 15
    _attr_max_temp = 30
    _attr_hvac_modes: ClassVar[tuple[str, ...]] = (
        HVACMode.OFF,
        *HVAC_MODE_TO_IZONE.keys(),
    )
    _attr_fan_modes: ClassVar[tuple[str, ...]] = tuple(FAN_MODE_TO_IZONE.keys())
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: IZoneCoordinator,
        entry: ConfigEntry,
        host: str,
    ) -> None:
        """Initialize the system climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_system"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="iZone",
            configuration_url=f"http://{host}",
        )

    @property
    def _system(self) -> dict[str, Any]:
        return cast("dict[str, Any]", self.coordinator.data.system)

    @property
    def current_temperature(self) -> float | None:
        """Return the current supply temperature in Celsius."""
        return raw_to_celsius(self._system.get("Supply"))

    @property
    def target_temperature(self) -> float | None:
        """Return the current system setpoint in Celsius."""
        return raw_to_celsius(self._system.get("Setpoint"))

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current system mode as a Home Assistant HVACMode."""
        if not self._system.get("SysOn"):
            return HVACMode.OFF
        return IZONE_MODE_TO_HVAC.get(
            cast("int", self._system.get("SysMode")), HVACMode.OFF
        )

    @property
    def fan_mode(self) -> str | None:
        """Return the current system fan mode."""
        return IZONE_FAN_TO_MODE.get(cast("int", self._system.get("SysFan")))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the system setpoint temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.api.async_set_setpoint(celsius_to_raw(temperature))
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the system HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.api.async_set_power(on=False)
        else:
            await self.coordinator.api.async_set_power(on=True)
            izone_mode = HVAC_MODE_TO_IZONE.get(hvac_mode)
            if izone_mode is not None:
                await asyncio.sleep(0.5)  # wait on controller before changing mode
                await self.coordinator.api.async_set_mode(izone_mode)
        await asyncio.sleep(0.5)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the system fan mode."""
        izone_fan = FAN_MODE_TO_IZONE.get(fan_mode)
        if izone_fan is not None:
            await self.coordinator.api.async_set_fan(izone_fan)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the system."""
        await self.coordinator.api.async_set_power(on=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off the system."""
        await self.coordinator.api.async_set_power(on=False)
        await self.coordinator.async_request_refresh()


class IZoneZoneClimate(CoordinatorEntity[IZoneCoordinator], ClimateEntity):
    """Representation of a single iZone zone."""

    _attr_has_entity_name = True
    _attr_name = (
        None  # use the device name (the controller's zone Name) as the entity name
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 15
    _attr_max_temp = 30
    _attr_hvac_modes: ClassVar[tuple[HVACMode, ...]] = (
        HVACMode.OFF,
        HVACMode.FAN_ONLY,
        HVACMode.AUTO,
    )
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: IZoneCoordinator,
        entry: ConfigEntry,
        zone_index: int,
        zone_name: str | None,
    ) -> None:
        """Initialize a zone climate entity."""
        super().__init__(coordinator)
        self._zone_index = zone_index
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_index}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_zone_{zone_index}")},
            name=zone_name or f"Zone {zone_index + 1}",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _zone(self) -> dict[str, Any]:
        return self.coordinator.data.zones[self._zone_index]

    @property
    def current_temperature(self) -> float | None:
        """Return the current zone temperature in Celsius."""
        return raw_to_celsius(self._zone.get("Temp"))

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature in Celsius."""
        return raw_to_celsius(self._zone.get("Setpoint"))

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current zone mode as a Home Assistant HVACMode."""
        zone_mode = self._zone.get("Mode")
        if zone_mode == ZONE_MODE_CLOSE:
            return HVACMode.OFF
        if zone_mode == ZONE_MODE_AUTO:
            return HVACMode.AUTO
        return HVACMode.FAN_ONLY

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the zone setpoint temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.api.async_set_zone_setpoint(
            self._zone_index, celsius_to_raw(temperature)
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the zone HVAC mode."""
        zone_mode = {
            HVACMode.OFF: ZONE_MODE_CLOSE,
            HVACMode.AUTO: ZONE_MODE_AUTO,
            HVACMode.FAN_ONLY: ZONE_MODE_OPEN,
        }.get(hvac_mode, ZONE_MODE_OPEN)
        await self.coordinator.api.async_set_zone_mode(self._zone_index, zone_mode)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the zone (open it to follow the system thermostatically)."""
        await self.coordinator.api.async_set_zone_mode(self._zone_index, ZONE_MODE_AUTO)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off the zone (close it)."""
        await self.coordinator.api.async_set_zone_mode(
            self._zone_index, ZONE_MODE_CLOSE
        )
        await self.coordinator.async_request_refresh()

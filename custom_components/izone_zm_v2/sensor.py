"""Sensor platform for iZone Local - supply air temperature."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, raw_to_celsius
from .coordinator import IZoneCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iZone supply temperature sensor from a config entry."""
    coordinator: IZoneCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IZoneSupplyTemperatureSensor(coordinator, entry)])


class IZoneSupplyTemperatureSensor(CoordinatorEntity[IZoneCoordinator], SensorEntity):
    """The ducted system's supply (discharge) air temperature."""

    _attr_has_entity_name = True
    _attr_name = "Supply temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_supply_temperature"
        # Grouped under the same "iZone" device as the system climate
        # entity and the favourite buttons, rather than its own device.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def native_value(self) -> float | None:
        return raw_to_celsius(self.coordinator.data.system.get("Supply"))

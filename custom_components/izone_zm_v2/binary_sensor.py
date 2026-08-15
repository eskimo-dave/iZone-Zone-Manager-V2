"""
Binary sensor platform for iZone Zone Manager V2 - per-zone sensor fault.

Disabled by default, same caveat as the battery voltage sensor in
sensor.py: the sample zone response used to build this had RfSignal: 0 and
SensorFault: 0, consistent with a wired (non-RF) zone sensor. Semantics of
SensorFault (0/1 boolean vs. something else) are inferred from the field
name only, not confirmed by triggering a real fault. Enable per-zone and
verify before relying on it for anything automated.
"""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IZoneCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up iZone binary sensors from a config entry."""
    coordinator: IZoneCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = []
    for zone_index in range(coordinator.zone_count):
        zone = coordinator.data.zones[zone_index]
        if zone.get("Temp") == 0:
            continue
        entities.append(IZoneZoneSensorFaultBinarySensor(coordinator, entry, zone_index))
    async_add_entities(entities)


class IZoneZoneSensorFaultBinarySensor(CoordinatorEntity[IZoneCoordinator], BinarySensorEntity):
    """Whether a zone's temperature sensor is reporting a fault."""

    _attr_has_entity_name = True
    _attr_name = "Sensor fault"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry, zone_index: int) -> None:
        super().__init__(coordinator)
        self._zone_index = zone_index
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_index}_sensor_fault"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_zone_{zone_index}")},
        )

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.zones[self._zone_index].get("SensorFault")
        if value is None:
            return None
        return bool(value)

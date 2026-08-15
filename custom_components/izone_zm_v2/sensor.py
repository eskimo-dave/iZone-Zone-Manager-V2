"""
Sensor platform for iZone ZM V2.

supply air temperature plus system
diagnostics (indoor humidity/CO2/VOC, filter status, warnings, runtime),
and a per-zone battery voltage sensor.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
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
    """Set up iZone sensors from a config entry."""
    coordinator: IZoneCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        IZoneSupplyTemperatureSensor(coordinator, entry),
        IZoneHumiditySensor(coordinator, entry),
        IZoneCO2Sensor(coordinator, entry),
        IZoneVOCSensor(coordinator, entry),
        IZoneFilterStatusSensor(coordinator, entry),
        IZoneWarningsSensor(coordinator, entry),
        IZoneErrorSensor(coordinator, entry),
        IZoneRunHoursSensor(coordinator, entry),
    ]

    for zone_index in range(coordinator.zone_count):
        zone = coordinator.data.zones[zone_index]
        # Same "disabled zone reports 0" skip used in climate.py, kept
        # consistent so a skipped zone doesn't get orphaned sensors either.
        if zone.get("Temp") == 0:
            continue
        entities.append(IZoneZoneBatterySensor(coordinator, entry, zone_index))

    async_add_entities(entities)


class _IZoneSystemSensor(CoordinatorEntity[IZoneCoordinator], SensorEntity):
    """Base for sensors reading a single field out of the SystemV2 response."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: IZoneCoordinator, entry: ConfigEntry, unique_suffix: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        # Grouped under the same "iZone" device as the system climate
        # entity, favourite buttons, and supply temperature sensor.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def _system(self) -> dict[str, Any]:
        return self.coordinator.data.system


class IZoneSupplyTemperatureSensor(_IZoneSystemSensor):
    """The ducted system's supply (discharge) air temperature."""

    _attr_name = "Supply temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "supply_temperature")

    @property
    def native_value(self) -> float | None:
        return raw_to_celsius(self._system.get("Supply"))


class IZoneHumiditySensor(_IZoneSystemSensor):
    """Indoor relative humidity, as measured at the return air sensor."""

    _attr_name = "Humidity"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "humidity")

    @property
    def native_value(self) -> int | None:
        return self._system.get("InRh")


class IZoneCO2Sensor(_IZoneSystemSensor):
    """Indoor CO2 level."""

    _attr_name = "CO2"
    _attr_device_class = SensorDeviceClass.CO2
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "co2")

    @property
    def native_value(self) -> int | None:
        return self._system.get("IneCO2")


class IZoneVOCSensor(_IZoneSystemSensor):
    """Indoor total volatile organic compounds level."""

    _attr_name = "VOC"
    _attr_device_class = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_BILLION
    #_attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "voc")

    @property
    def native_value(self) -> int | None:
        return self._system.get("InTVOC")


class IZoneFilterStatusSensor(_IZoneSystemSensor):
    """
    Raw filter-warning level from the controller.

    Semantics unconfirmed - FilterWarn is exposed as a raw integer
    (observed value: 3) rather than mapped to a friendly state, since it's
    unclear whether it's a 0-3 severity scale, a countdown, or something
    else. Need to wait until the clean cycle comes up to see what this value is,
    what it means, then this could become a proper enum or binary sensor.
    """

    _attr_name = "Filter status (raw)"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "filter_status")

    @property
    def native_value(self) -> int | None:
        return self._system.get("FilterWarn")


class IZoneWarningsSensor(_IZoneSystemSensor):
    """The controller's current warnings text (e.g. "none")."""

    _attr_name = "Warnings"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "warnings")

    @property
    def native_value(self) -> str | None:
        value = self._system.get("Warnings")
        return value.strip() if isinstance(value, str) else value


class IZoneErrorSensor(_IZoneSystemSensor):
    """The AC unit's current error text (e.g. " OK ")."""

    _attr_name = "AC error"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "ac_error")

    @property
    def native_value(self) -> str | None:
        value = self._system.get("ACError")
        return value.strip() if isinstance(value, str) else value


class IZoneRunHoursSensor(_IZoneSystemSensor):
    #Cumulative AC compressor/unit runtime hours - useful for tracking
    #service/maintenance intervals.

    _attr_name = "Runtime hours"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IZoneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "run_hours")

    @property
    def native_value(self) -> int | None:
        return self._system.get("AcRunH")


class IZoneZoneBatterySensor(CoordinatorEntity[IZoneCoordinator], SensorEntity):
    """
    A zone's wireless sensor battery voltage.

    Disabled by default - the sample zone response used to build this
    integration had RfSignal: 0 and BattVolt: 0, suggesting a wired
    (non-RF) zone sensor where this field isn't meaningful. Enable it
    manually per-zone if your zones actually use wireless sensors, and
    check that a real reading looks sane (BattVolt's unit/scale is also
    unconfirmed - it may need the same *100 style scaling as temperatures).
    """

    _attr_has_entity_name = True
    _attr_name = "Battery voltage"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: IZoneCoordinator, entry: ConfigEntry, zone_index: int
    ) -> None:
        super().__init__(coordinator)
        self._zone_index = zone_index
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_index}_battery"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_zone_{zone_index}")},
        )

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.zones[self._zone_index].get("BattVolt")

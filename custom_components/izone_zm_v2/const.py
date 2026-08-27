"""Constants for the iZone Zone Manager V2 integration."""

from __future__ import annotations

from homeassistant.components.climate.const import HVACMode

DOMAIN = "izone_zm_v2"
DEFAULT_NAME = "iZone"

CONF_ZONE_COUNT = "zone_count"
CONF_SCAN_INTERVAL_SECONDS = "scan_interval_seconds"

SCAN_INTERVAL_SECONDS = 45
MIN_SCAN_INTERVAL_SECONDS = 10
REQUEST_TIMEOUT = 10

# --- Protocol mode codes -------------------------------------------------
# CONFIRMED against the live controller by cycling modes in the app and
# polling SystemV2/ZonesV2 after each change.
HVAC_MODE_TO_IZONE: dict[HVACMode, int] = {
    HVACMode.COOL: 1,
    HVACMode.HEAT: 2,
    HVACMode.FAN_ONLY: 3,
    HVACMode.DRY: 4,
    HVACMode.AUTO: 5,
}
IZONE_MODE_TO_HVAC: dict[int, HVACMode] = {v: k for k, v in HVAC_MODE_TO_IZONE.items()}

FAN_MODE_TO_IZONE: dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "auto": 4,
}
IZONE_FAN_TO_MODE: dict[int, str] = {v: k for k, v in FAN_MODE_TO_IZONE.items()}

# Zone mode codes (open/close/auto) - CONFIRMED against the live controller.
ZONE_MODE_OPEN = 1
ZONE_MODE_CLOSE = 2
ZONE_MODE_AUTO = 3

# --- Favourites --------------------------------------------------------
# The old izone.yaml exposed 9 favourite-activation buttons with no
# NoOfFavourites-style count field visible anywhere in SystemV2, so this is
# hardcoded to match. CONFIRMED against a live controller: favourites are
# stored as schedule slots, fetched via Type 3 with envelope "SchedulesV2".
NUM_FAVOURITES = 9
FAVOURITE_REQUEST_TYPE = 3

# --- Temperature scaling ---------------------------------------------------
# CONFIRMED from a live /iZoneRequestV2 response: Setpoint/Temp/Supply are
# all Celsius * 100 as plain ints (e.g. 1900 == 19.00C, 4165 == 41.65C).
IZONE_TEMP_SCALE = 100


def raw_to_celsius(raw: int | None) -> float | None:
    """Convert a raw iZone temperature (Celsius * 100) to degrees C."""
    if raw is None:
        return None
    return raw / IZONE_TEMP_SCALE


def celsius_to_raw(value: float) -> int:
    """Convert a target temperature in degrees C to the raw iZone int format."""
    return round(value * IZONE_TEMP_SCALE)

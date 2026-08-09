"""Thin async client for the iZone local REST protocol (iZoneRequestV2 / iZoneCommandV2).

Read-side (iZoneRequestV2) field names and scaling are CONFIRMED against a
live controller - see async_get_system/async_get_zone docstrings.

Write-side (iZoneCommandV2) payloads below are sourced from the working
rest_command: templates in the original izone.yaml (not independently
re-tested against the live controller yet, but that YAML was in active use
controlling this exact unit) - flat, unwrapped fields like {"SysOn": 1},
not the nested guesses from earlier drafts of this file.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from .const import FAVOURITE_REQUEST_TYPE, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class IZoneApiError(Exception):
    """Raised when the iZone controller can't be reached or returns bad data."""


class IZoneApiClient:
    """Talks to a single iZone controller over its local REST API."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._request_url = f"http://{host}/iZoneRequestV2"
        self._command_url = f"http://{host}/iZoneCommandV2"
        self._session = session

    async def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to iZoneRequestV2 and parse the JSON response body.

        Only used for reads - iZoneRequestV2 always returns a real JSON
        body. iZoneCommandV2 (writes) does NOT reliably return valid JSON
        on success, so commands use _post_command below instead, which
        ignores the body entirely.
        """
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.post(url, json=payload)
                response.raise_for_status()
                # The controller's firmware pads fixed-size string buffers
                # (e.g. LockCode) with raw 0xFF bytes instead of proper
                # null-termination, which makes the body invalid strict
                # UTF-8 even though the JSON structure itself is fine.
                # aiohttp's response.json() decodes strictly and raises on
                # that, so read the raw bytes and decode leniently first.
                raw = await response.read()
                text = raw.decode("utf-8", errors="replace").strip()
                return json.loads(text)
        except TimeoutError as err:
            raise IZoneApiError(f"Timed out contacting iZone controller at {url}") from err
        except aiohttp.ClientError as err:
            raise IZoneApiError(f"Error contacting iZone controller at {url}: {err}") from err
        except (KeyError, ValueError) as err:
            raise IZoneApiError(f"Unexpected response from iZone controller: {err}") from err

    async def _post_command(self, url: str, payload: dict[str, Any]) -> None:
        """POST to iZoneCommandV2 and ignore the response body.

        The controller's command acknowledgement isn't reliably valid JSON
        (sometimes empty, sometimes something starting with "{" that isn't
        properly quoted) - we don't need its content anyway, since we
        re-poll via the coordinator after every command. Only the HTTP
        status matters here.
        """
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.post(url, json=payload)
                response.raise_for_status()
        except TimeoutError as err:
            raise IZoneApiError(f"Timed out contacting iZone controller at {url}") from err
        except aiohttp.ClientError as err:
            raise IZoneApiError(f"Error contacting iZone controller at {url}: {err}") from err

    async def async_get_system(self) -> dict[str, Any]:
        """Fetch system-level state (Type 1). Response includes NoOfZones.

        CONFIRMED shape from a live controller: top-level keys are
        AirStreamDeviceUId / DeviceType / SystemV2 (not "iZoneV2Response").
        """
        data = await self._post(
            self._request_url,
            {"iZoneV2Request": {"Type": 1, "No": 0, "No1": 0}},
        )
        try:
            return data["SystemV2"]
        except KeyError as err:
            raise IZoneApiError(f"Unexpected system response shape: {data}") from err

    async def async_get_zone(self, index: int) -> dict[str, Any]:
        """Fetch a single zone's state (Type 2).

        CONFIRMED shape from a live controller: envelope key is "ZonesV2"
        (plural), containing Name/Mode/Temp/Setpoint - Temp and Setpoint use
        the same Celsius*100 raw int scaling as the system response. Mode
        codes (1=open, 2=closed, 3=auto) confirmed by cycling in the app.
        """
        data = await self._post(
            self._request_url,
            {"iZoneV2Request": {"Type": 2, "No": index, "No1": 0}},
        )
        try:
            return data["ZonesV2"]
        except KeyError as err:
            raise IZoneApiError(f"Unexpected zone response shape: {data}") from err

    async def async_get_favourite(self, index: int) -> dict[str, Any]:
        """Fetch a single favourite's info, including its configured name.

        CONFIRMED shape from a live controller: envelope key is
        "SchedulesV2" (favourites are stored as the controller's schedule
        slots), containing Name/Index/Mode/Zones etc. Request Type 3 was
        correct on the first guess.
        """
        data = await self._post(
            self._request_url,
            {"iZoneV2Request": {"Type": FAVOURITE_REQUEST_TYPE, "No": index, "No1": 0}},
        )
        try:
            return data["SchedulesV2"]
        except KeyError as err:
            raise IZoneApiError(f"Unexpected favourite response shape: {data}") from err

    async def async_set_power(self, on: bool) -> None:
        await self._post_command(self._command_url, {"SysOn": 1 if on else 0})

    async def async_set_mode(self, mode: int) -> None:
        await self._post_command(self._command_url, {"SysMode": mode})

    async def async_set_fan(self, fan: int) -> None:
        await self._post_command(self._command_url, {"SysFan": fan})

    async def async_set_setpoint(self, raw_setpoint: int) -> None:
        """Set the system setpoint. Expects the raw protocol value (C * 100) -
        convert with const.celsius_to_raw() before calling this."""
        await self._post_command(self._command_url, {"SysSetpoint": raw_setpoint})

    async def async_set_zone_mode(self, index: int, mode: int) -> None:
        await self._post_command(
            self._command_url, {"ZoneMode": {"Index": index, "Mode": mode}}
        )

    async def async_set_zone_setpoint(self, index: int, raw_setpoint: int) -> None:
        """Set a zone's setpoint. Expects the raw protocol value (C * 100) -
        convert with const.celsius_to_raw() before calling this."""
        await self._post_command(
            self._command_url,
            {"ZoneSetpoint": {"Index": index, "Setpoint": raw_setpoint}},
        )

    async def async_set_favourite(self, favourite_index: int) -> None:
        """Activate a favourite. favourite_index is 0-based (matching the
        NUM_FAVOURITES range used elsewhere) - the controller itself is
        1-based, so we add 1 here."""
        await self._post_command(self._command_url, {"FavouriteSet": favourite_index + 1})

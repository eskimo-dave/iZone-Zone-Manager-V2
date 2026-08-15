# iZone Zone Manager V2

<p align="center">
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.10%2B-41BDF5?style=for-the-badge&logo=homeassistant&logoColor=white" alt="Home Assistant" />
  <img src="https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge" alt="HACS Custom" />

</p>

A local Home Assistant integration for newer Rinnai/iZone HVAC systems, designed to expose your zones and controls directly in the HA dashboard.

## Overview

This integration provides a practical way to connect a local iZone controller to Home Assistant without relying on cloud-based services. It focuses on zone-level control, temperature readings, and system sensors including the main duct/supply temperature, air quality readings, error messages.
This is designed to work on all systems using the iZoneRequestV2 API

## Supported versions

- Currently tested on: Rinnai Home CNTRLDRCIZHAW
- Firmware version: V4.36

> This integration is best suited to local network setups and has been validated against the hardware and firmware above.

## Features

### Working

- Automatic zone detection and naming
- Per-zone temperature control
- Reading current zone temperature
- Adjusting dampers: open, closed, and auto
- Reading duct temperature
- Automatic creation of favourite buttons with naming support
- Air quality readings
- Error messages and runtime hours
- Adjustable scan interval (default 45 seconds)

###  Known limitations

- Updating values in favourites may not be possible with the current implementation
- Sleep timer not created
- Unsure what the filter status is, waiting on more testing.

## Prerequisites

- Static IP configured for your iZone adapter
- A compatible Rinnai/iZone controller available on the local network.
    - This can be validated by running the following call and getting a valid response:
  ```bash
    curl -X POST http://<IP ADDRESS>/iZoneRequestV2 \
  -H "Content-Type: application/json" \
  -d '{"iZoneV2Request":{"Type":1,"No":0,"No1":0}}'
  ```
- Home Assistant running with HACS available

## Installation

1. Ensure your prerequisites are complete.
2. In HACS, add this repository as an integration type:
   [https://github.com/eskimo-dave/iZone-Zone-Manager-V2](https://github.com/eskimo-dave/iZone-Zone-Manager-V2)
3. Install the integration from HACS.
4. Add the iZone integration in Home Assistant and follow the setup prompts.

## Suggested dashboard setup

Once configured, the easiest way to control the system is with a simple thermostat card:

```yaml
type: custom:simple-thermostat
entity: climate.izone_ducted_ac
name: Master unit
hide_setpoint: true
step_size: 0.5
header:
  toggle: false
  name: Rinnai HVAC
  icon: mdi:air-conditioner
sensors:
  - entity: sensor.izone_supply_temperature
    name: Duct Temp
control:
  hvac:
    _name: Mode
    heat:
      name: Heat
    cool:
      name: Cool
    dry:
      name: Dry
    fan_only:
      name: Fan
    auto:
      name: Auto
    'off':
      name: 'Off'
  fan:
    _name: Fan speed
    low:
      name: Low
    medium:
      name: Medium
    high:
      name: High
    auto:
      name: Auto
layout:
  mode:
    headings: false
    names: true
```
With each zone configured as a mushroom card:
```yaml
- type: custom:mushroom-climate-card
    entity: climate.izone_zone_1
    name: Master
    icon: mdi:bed
    layout: vertical
    fill_container: true
    show_temperature_control: true
    collapsible_controls: true
    hvac_modes:
      - heat_cool
      - auto
      - 'off'
```

## Notes

This project is intended for local control and monitoring of compatible Rinnai/iZone systems. If you are using a different controller or firmware, it may require additional testing or compatibility work.

---

<p align="center">
  <em>Built for Home Assistant and local zone control.</em>
</p>


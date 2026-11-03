# Notification Lights

Show Home Assistant conditions as colour and placement on the outer ring of Aqara ceiling lights (T1M), instead of as a phone push. The same **Aqara Light Notification** looks the same on every light.

Requires [Aqara Advanced Lighting](https://github.com/absent42/Aqara-Advanced-Lighting) (HACS), set up first. Terms: [CONTEXT.md](CONTEXT.md). Design: [docs/design.md](docs/design.md).

## Install
1. HACS, Custom repositories, add this repository as an Integration.
2. Install Notification Lights and restart Home Assistant.
3. Settings, Devices and services, Add integration, Notification Lights. Optionally pick a quiet-hours entity.

## Set up
Everything is managed from the integration's **Configure** dialog, as groups (the integration page lists the same items under the same two headings, and devices are nested under a Notification lights and a Notifications device):
- **Notification lights**: the list of your lights, with their rooms. Pick *Add a notification light* and choose the `_rgb` entity (the ring, not the central room light). The name defaults to the entity's name; rooms and floor are prefilled from its device (list several rooms for an open-plan space, or none for a house-only light). Pick a light in the list to edit or remove it, e.g. to calibrate the offset: press **Calibration preview** on the light, and if eighth 1 starts further round than on your other lights, raise the offset by that many LEDs.
- **Notifications**: the list by priority. Pick *Add a notification*: name, colour, footprint (whole, half, quarter or eighth), priority, scope (house, floor or room), then its source. Pick one in the list to edit or remove it.
- **Quiet hours**: the entity that means quiet hours (a bedtime helper, a schedule). Change or clear it here at any time.

A notification shows exactly while its source is active. Lower priority numbers paint on top. For a notification that overrides everything, use the whole footprint and the top priority.

Each notification gets an **Enabled** switch, **Active** sensor, **Preview** (30 s) and **Dismiss** buttons. **Dismiss all** is a button and the `notification_lights.dismiss_all` service.

## Source examples
Entities in a state: pick the entities and the state (default `on`); active while any matches. The delay field makes the source hold for N seconds first.

Rain (house scope):
```
{{ states('weather.home') in ['rainy', 'pouring', 'lightning-rainy']
   and ['binary_sensor.bedroom_window', 'binary_sensor.patio_door'] | select('is_state', 'on') | list | count > 0
   and states('zone.home') | int(0) > 0 }}
```

Poor air in one room (room scope, one notification per room):
```
{{ states('sensor.office_co2') | float(0) > 1200 and is_state('binary_sensor.office_occupancy', 'on') }}
```

## Tests
`tests/test_logic.py` and `tests/test_validation.py` are plain Python and run anywhere. `tests/test_integration.py` needs `pytest-homeassistant-custom-component`, which only runs on Linux/macOS (it imports `fcntl`); it has not been run yet.

## Limits
Only Aqara T1M notification lights. Accent LEDs, ordinary bulbs and showing only in occupied rooms are not supported.

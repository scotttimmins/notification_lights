# Notification Lights

Show Home Assistant conditions as colour and placement on the outer ring of Aqara ceiling lights (T1M), instead of as a phone push. The same **Aqara Light Notification** looks the same on every light.

Requires [Aqara Advanced Lighting](https://github.com/absent42/Aqara-Advanced-Lighting) (HACS), set up first. Terms: [CONTEXT.md](CONTEXT.md). Design: [docs/design.md](docs/design.md).

## Install
1. HACS, Custom repositories, add this repository as an Integration.
2. Install Notification Lights and restart Home Assistant.
3. Settings, Devices and services, Add integration, Notification Lights. Optionally pick a quiet-hours entity.

## Set up
Everything is managed from the integration's **Configure** dialog, as groups (the integration page shows two devices, Notification lights and Notifications; each notification is its own device nested under Notifications, so click it to open its Enabled, Active, Colour, Preview and Dismiss entities):
- **Notification lights**: the list of your lights, with their rooms. Pick *Add a notification light* and choose the `_rgb` entity (the ring, not the central room light). The name defaults to the entity's name; rooms and floor are prefilled from its device (list several rooms for an open-plan space, or none for a house-only light). Pick a light in the list to edit or remove it, e.g. to calibrate the offset: press **Calibration preview** on the light, and if eighth 1 starts further round than on your other lights, raise the offset by that many LEDs.
- **Notifications**: the list by priority. Pick *Add a notification*: name, colour, footprint (whole, half, quarter or eighth), priority, scope (house, floor or room), then its source. Pick one in the list to edit or remove it.
- **Quiet hours**: the entity that means quiet hours (a bedtime helper, a schedule). Change or clear it here at any time.

A notification shows exactly while its source is active. Lower priority numbers paint on top. For a notification that overrides everything, use the whole footprint and the top priority.

Each notification gets an **Enabled** switch, **Active** sensor, **Colour** light, **Preview** (30 s) and **Dismiss** buttons. The Colour light is the colour picker and is always on: it stands for the notification's colour. Open it (tap the notification's tile on the dashboard) and choose a colour; it is saved and previewed on the lights. Its `status` attribute says showing, idle, dismissed, disabled or preview. Turning it on previews the notification; use Dismiss to dismiss. **Dismiss all** is a button and the `notification_lights.dismiss_all` service.

## Dashboard
A generated dashboard lists every notification by priority (a tile in its own colour, lit while it is showing, tap it to change the colour, then its scope, footprint and Enabled / Preview / Dismiss controls), a Dismiss all button and each light's calibration button. Create a new dashboard, open it, choose the three dots, Edit, then the three dots, Raw configuration editor, and paste:

```yaml
strategy:
  type: custom:notification-lights
  title: Notifications   # optional
```

It is built when the dashboard loads, so reload the page after adding or removing items.

## Print a guide
Press **Print guide** (on the Notifications device, and on the dashboard). A notification appears with a link to a printable page: one card per notification with its colour, a ring diagram with its section highlighted, when it is raised, and where it shows, plus your lights. Open it and print from the browser (Ctrl+P) to any printer, connected to Home Assistant or not, or save it as PDF. The link is signed and works for 10 minutes. If colours are missing, turn on background graphics in the print dialog.

To print from an automation, call the `notification_lights.print_sheet` action: it returns `url` and `html` (use a response variable), and also fires the `notification_lights_print_sheet` event with the link, so you can hand it to whatever print integration you use.

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
`tests/test_logic.py`, `tests/test_validation.py` and `tests/test_summary.py` are plain Python and run anywhere; `node tests/strategy_test.js` checks the dashboard strategy. `tests/test_integration.py` needs `pytest-homeassistant-custom-component`, which only runs on Linux/macOS (it imports `fcntl`); it has not been run yet.

## Limits
Only Aqara T1M notification lights. Accent LEDs, ordinary bulbs and showing only in occupied rooms are not supported.

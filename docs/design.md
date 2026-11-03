# Design

Status: decided 2026-11-03 in a design review; built, imports verified against Home Assistant 2026.10.4, behaviour not yet run in HA. Replaces `homeassistant-config/docs/notification-lights.md`. Terms: `CONTEXT.md`. Why an integration: `docs/adr/0001-custom-integration.md`.

## Delivery
HACS custom integration `notification_lights`, requires `aqara_advanced_lighting` (HACS), checked in the config flow (abort with install hint; `after_dependencies`, not `dependencies`, so the message shows). Standalone repo, GitHub origin. Config flow with subentries. Dashboard: native HA device/entity pages first, then a generated dashboard strategy (JS) as a follow-up.

## Notification light
Registered in two steps: pick the `light.*_rgb` entity (the central room light is rejected), then set where it shows. **Rooms** (one or more HA areas) and **floor** are prefilled from the light's device and can be changed; with neither it is house-only, so a light with no area is valid. A dining-room light lists dining_room and kitchen for the open-plan space. Per light also: segments (default 26), offset, brightness, quiet-hours flag, idle policy (turn off, default; or restore previous state). Editable later (reconfigure). Offset calibration: a Preview button showing eighth 1 for 30 s (not built yet).

## Notification
- **Source**: entity picker + active state + optional delay, or a template (advanced). Follows its source exactly.
- **Scope**: room, floor or house. Static. Dynamic per-occupied-room scope is out of this iteration.
- **Footprint**: whole, half (4 quarter-aligned positions), quarter, or eighth, on a fixed 8-slot grid (26 LEDs: 3 or 4 per slot).
- **Priority**: unique number, lower paints on top. Overlaps resolved by paint order.
- **Colour**: colour picker.
- **Show during quiet hours**: toggle, default off.
- **Entities**: Enabled (switch), Active (binary_sensor), Preview (button, 30 s), Dismiss (button). Clear-all service.
- A notification meant to override everything: whole footprint + top priority.

## Integration options
Quiet-hours entity (optional): any `input_boolean`, `binary_sensor`, `schedule` or `switch`.

## Examples (README, not code)
- Air, per room: poor air AND room occupied, room scope.
- Rain: raining AND window/door open AND someone home, house scope.

## Out of scope now
Accent LEDs, Aurora bulbs, notifications shown only in occupied rooms, auto-discovery of lights, drag-to-reorder priority.

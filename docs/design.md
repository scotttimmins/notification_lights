# Design

Status: decided 2026-11-03 in a design review; built; imports checked against Home Assistant 2026.10.4; live painting and multi-room (dining + kitchen) rings confirmed working on the owner's instance 2026-11-03. Still unconfirmed on hardware: the whole-ring Fire and Leak path, quiet hours, restore idle policy. Replaces `homeassistant-config/docs/notification-lights.md`. Terms: `CONTEXT.md`. Why an integration: `docs/adr/0001-custom-integration.md`.

## Delivery
HACS custom integration `notification_lights`, requires `aqara_advanced_lighting` (HACS), checked in the config flow (abort with install hint; `after_dependencies`, not `dependencies`, so the message shows). Standalone repo, GitHub origin. Setup asks only for the quiet-hours entity. Each light and each notification is a config subentry (id = item id), managed on the integration page: see Integration-page layout. Version 1 and 2 entries migrate on load, keeping item ids so unique ids and entity ids survive. Dashboard: the native device/entity pages, plus a generated dashboard strategy (`custom:notification-lights`, served from `www/` and loaded by the integration). It finds this integration's entities in the frontend and groups them per notification through two attributes every entity carries, `notification` (its name) and `part` (active, enabled, preview, dismiss, calibration, dismiss_all), sorting by the priority on the Active sensor. It is built when a dashboard loads.

## Notification light
Registered in two steps: pick the `light.*_rgb` entity (the central room light is rejected), then set where it shows. **Rooms** (one or more HA areas) and **floor** are prefilled from the light's device and can be changed; with neither it is house-only, so a light with no area is valid. The name defaults to the light entity friendly name and is editable. A dining-room light lists dining_room and kitchen for the open-plan space. Per light also: segments (default 26), offset, brightness, quiet-hours flag, idle policy (turn off, default; or restore previous state). Editable later (reconfigure). Offset calibration: a Calibration preview button showing eighth 1 for 30 s.

## Notification
- **Source**: entity picker + active state + optional delay, or a template (advanced). Follows its source exactly.
- **Scope**: room, floor or house. Static. Dynamic per-occupied-room scope is out of this iteration.
- **Footprint**: whole, half (4 quarter-aligned positions), quarter, or eighth, on a fixed 8-slot grid (26 LEDs: 3 or 4 per slot).
- **Priority**: unique number, lower paints on top. Overlaps resolved by paint order.
- **Colour**: colour picker.
- **Show during quiet hours**: toggle, default off.
- **Entities**: Enabled (switch), Active (binary_sensor), Colour (light: always on so the colour is always visible, colour wheel saves the colour, on = preview, off = no-op; `status` attribute says showing, idle, dismissed, disabled or preview), Preview (button, 30 s), Dismiss (button). Clear-all service.
- **Dismiss**: hides it until the source is definitely inactive and then active again. Unknown and unavailable are not inactive. Saved, so it survives restarts and reloads; it also ends a running preview. It does not disable the notification.
- A notification meant to override everything: whole footprint + top priority.

## Configure
Quiet-hours entity (optional): any `input_boolean`, `binary_sensor`, `schedule` or `switch`.

## Examples (README, not code)
- Air, per room: poor air AND room occupied, room scope.
- Rain: raining AND window/door open AND someone home, house scope.

## Out of scope now
Accent LEDs, Aurora bulbs, notifications shown only in occupied rooms, auto-discovery of lights, drag-to-reorder priority.

## Printable guide
A Print guide button (and the `print_sheet` action) produces a self-contained, print-styled HTML page: per notification its colour, a ring diagram with the footprint's slots highlighted, its source in words and where it shows, plus the lights. It is served at `/api/notification_lights/guide` behind login, so the button posts a signed link (10 minutes) as a Home Assistant notification; anyone prints it from the browser to any printer or saves it as PDF. For printers wired into Home Assistant, the action returns the link and HTML, and a `notification_lights_print_sheet` event carries the link, so an automation can pass it to the user's own print integration. No printer drivers or PDF library in the integration.

## Integration-page layout (v3)
Each light and each notification is a config subentry (id = item id), so the integration page gives two collapsible sections with an Add button each, and Reconfigure / Delete per item. Reconfigure and Add are single forms (a light's Add is pick-then-details so name and rooms can be prefilled). Each subentry has its own device holding that item's entities (Preview and Dismiss are on the device); Dismiss all and Print guide sit on an entry-level device. Configure only sets the quiet-hours entity. Preview and Dismiss cannot be placed on the subentry rows themselves (HA offers no hook), so they are on the device and the dashboard. This reverses the v2 options layout, which listed everything in one Configure dialog; v2 entries migrate to subentries with the same ids.

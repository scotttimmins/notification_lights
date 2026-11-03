# Custom integration, not blueprints or a YAML package

2026-11-03

The previous design was a YAML package, a blueprint per notification and a Jinja renderer in `homeassistant-config`. Notifications, rings and the renderer's trigger list were hard-coded, so adding one meant editing YAML in three places.

We build a HACS custom integration (`notification_lights`) with a config flow instead. It depends on `aqara_advanced_lighting` (also via HACS). Users add and remove notifications and lights from the UI, and the renderer is Python.

Rejected: a tidier YAML package/blueprint set (no runtime add/remove, trigger list stays static) and blueprints only (still needs YAML wiring and a registry).

Also dropped in the same rework: the separate `critical` importance. Scope covers "everywhere", the whole footprint at top priority covers "takes over the light", and a per-notification "show during quiet hours" toggle covers the rest.

# Notification Lights

Glossary. Terms carry a specific meaning beyond their plain-English sense.

**Aqara Light Notification**:
A condition the house wants noticed, shown as a fixed colour and placement on lights instead of as a phone push. The same notification looks the same on every light. Distinct from Home Assistant's own `notify` / persistent notifications. Short form "notification" is fine inside this project's docs, UI and voice ("dismiss fridge notification"), never elsewhere.
_Avoid_: notification (bare, outside this project), alert, signal

**Notification light**:
The outer segmented ring of an Aqara ceiling light (T1M), exposed as its own `light.*_rgb` entity, that can show [[Aqara Light Notification]]s. The only kind of light that does. Independent of the ceiling light's central room light, so taking it over never changes the room's main lighting.
_Avoid_: ring (informal only), accent LED, ceiling light (that is the whole fitting)

**Notification scope**:
Where a notification appears: one **room**, one **floor**, or the **whole house**. Fixed when the notification is defined. It shows on every [[Notification light]] that belongs to that room or floor; every light belongs to the whole house. A light belongs to one or more rooms and one floor, prefilled from its device and changeable per light.
_Avoid_: rooms attribute

**Notification footprint**:
The part of a [[Notification light]] a notification paints: the **whole** light, a **half**, a **quarter** or an **eighth**. Halves come in four quarter-aligned positions (two perpendicular orientations) and can overlap; quarters and eighths do not. The same footprint sits in the same physical place on every light.
_Avoid_: slot, segment (those are LED-level)

**Priority**:
A notification's paint order where footprints overlap. Lower number paints on top. Unique per installation.

**Source**:
What decides a notification is active: entities in a state (any-of, optional delay) or a template. The notification shows exactly while its source is active.

**Quiet hours**:
While the integration's quiet-hours entity is on, notifications without "show during quiet hours" are hidden on lights flagged quiet.

**Dismiss**:
Hide an active notification until its source next goes inactive and then active again. Not the same as disabling it.
_Avoid_: clear (names the clear-all action)

**Preview**:
Show a notification on its lights for about 30 seconds regardless of its source.

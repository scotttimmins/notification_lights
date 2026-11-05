"""Runtime: tracks every notification's source and draws the result on the lights."""

from __future__ import annotations

import logging
from copy import deepcopy
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    EventStateChangedData,
    TrackTemplate,
    async_call_later,
    async_track_state_change_event,
    async_track_template_result,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.template import Template, result_as_boolean

from .const import (
    AQARA_DOMAIN,
    CONF_AREAS,
    DOMAIN,
    CONF_BRIGHTNESS,
    CONF_COLOUR,
    CONF_DELAY,
    CONF_FLOOR,
    CONF_FOOTPRINT,
    CONF_IDLE_POLICY,
    CONF_LIGHT,
    CONF_OFFSET,
    CONF_PRIORITY,
    CONF_QUIET_ENTITY,
    CONF_QUIET_HOURS,
    CONF_SCOPE,
    CONF_SCOPE_AREA,
    CONF_SCOPE_FLOOR,
    CONF_SEGMENTS,
    CONF_SHOW_QUIET,
    CONF_SOURCE_ENTITIES,
    CONF_SOURCE_STATE,
    CONF_SOURCE_TEMPLATE,
    CONF_SOURCE_TYPE,
    IDLE_RESTORE,
    PREVIEW_SECONDS,
    SOURCE_TEMPLATE,
    KIND_LIGHT,
    KIND_NOTIFICATION,
)
from .paint import build_pattern
from .scope import applies

_LOGGER = logging.getLogger(__name__)


class NotificationRuntime:
    """One notification: follows its source and exposes enabled/dismissed/preview."""

    def __init__(
        self, hub: Hub, item_id: str, data: dict[str, Any], dismissed: bool = False
    ) -> None:
        """Create the runtime for one stored notification.

        Args:
            hub: The owning hub.
            item_id: The notification's id.
            data: The notification's stored data.
            dismissed: Whether it was dismissed before a restart or reload.
        """
        self.hub = hub
        self.item_id = item_id
        self.data: dict[str, Any] = dict(data)
        self.name: str = self.data["name"]
        self.priority: int = int(self.data[CONF_PRIORITY])
        self.footprint: str = self.data[CONF_FOOTPRINT]
        self.rgb: list[int] = [int(c) for c in self.data[CONF_COLOUR]]
        self.show_quiet: bool = bool(self.data.get(CONF_SHOW_QUIET, False))
        self.enabled = True
        self.source_active = False
        self.dismissed = False
        # Dismissed before a restart: applies once the source is next seen active, and
        # ends only when the source is definitely inactive (unknown is not inactive).
        self._keep_dismissed = dismissed
        self.previewing = False
        self._raw = False
        self._delay = float(self.data.get(CONF_DELAY, 0))
        self._timer: CALLBACK_TYPE | None = None
        self._preview_timer: CALLBACK_TYPE | None = None
        self._unsubs: list[CALLBACK_TYPE] = []
        self._listeners: list[Callable[[], None]] = []

    @property
    def status(self) -> str:
        """Plain-word state: preview, disabled, dismissed, showing or idle."""
        if self.previewing:
            return "preview"
        if not self.enabled:
            return "disabled"
        if self.source_active and self.dismissed:
            return "dismissed"
        return "showing" if self.showing else "idle"

    @property
    def showing(self) -> bool:
        """Whether the notification is currently drawn on lights in its scope."""
        if self.previewing:
            return True
        return self.enabled and self.source_active and not self.dismissed

    @callback
    def add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Call a function whenever this notification changes.

        Args:
            listener: Function called with no arguments.

        Returns:
            A function that removes the listener.
        """
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _changed(self) -> None:
        """Tell entities and the renderer something changed."""
        for listener in list(self._listeners):
            listener()
        self.hub.save_dismissed()
        self.hub.request_render()

    async def async_start(self) -> None:
        """Evaluate the source once and start following it."""
        hass = self.hub.hass
        if self.data[CONF_SOURCE_TYPE] == SOURCE_TEMPLATE:
            template = Template(self.data[CONF_SOURCE_TEMPLATE], hass)
            self._set_raw(self._render_bool(template))

            @callback
            def _template_changed(event: Event | None, updates: list[Any]) -> None:
                result = updates.pop().result
                if isinstance(result, Exception):
                    _LOGGER.warning("%s: template error: %s", self.name, result)
                    return
                self._set_raw(_truth(result))

            info = async_track_template_result(
                hass, [TrackTemplate(template, None)], _template_changed
            )
            self._unsubs.append(info.async_remove)
        else:
            entities: list[str] = self.data[CONF_SOURCE_ENTITIES]
            self._set_raw(self._entities_match())

            @callback
            def _state_changed(event: Event[EventStateChangedData]) -> None:
                self._set_raw(self._entities_match())

            self._unsubs.append(
                async_track_state_change_event(hass, entities, _state_changed)
            )

    @callback
    def async_stop(self) -> None:
        """Stop following the source and cancel timers."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for timer in (self._timer, self._preview_timer):
            if timer:
                timer()
        self._timer = self._preview_timer = None

    def _render_bool(self, template: Template) -> bool | None:
        """Render a template to a boolean; errors and unknown count as undecided."""
        try:
            return _truth(template.async_render(parse_result=False))
        except Exception as err:  # noqa: BLE001 - a bad template must not stop setup
            _LOGGER.warning("%s: template error: %s", self.name, err)
            return None

    def _entities_match(self) -> bool | None:
        """True when any source entity is in the configured state.

        Returns:
            None while the answer is unknown: no entity matches and some are unknown,
            unavailable or missing. Unknown is not inactive.
        """
        wanted = self.data[CONF_SOURCE_STATE]
        states = [self.hub.hass.states.get(e) for e in self.data[CONF_SOURCE_ENTITIES]]
        if any(st and st.state == wanted for st in states):
            return True
        if any(st is None or st.state in (STATE_UNKNOWN, STATE_UNAVAILABLE) for st in states):
            return None
        return False

    @callback
    def _set_raw(self, value: bool | None) -> None:
        """Apply the source's raw truth value, honouring the delay.

        The notification follows the source exactly: it turns on only after the source
        has been true for the delay, and off the moment the source is false. A dismissal
        ends when the source goes false. None (unknown) changes nothing.
        """
        if value is None or value == self._raw:
            return
        self._raw = value
        if self._timer:
            self._timer()
            self._timer = None
        if not value:
            self.source_active = False
            self.dismissed = self._keep_dismissed = False
            self._changed()
        elif self._delay > 0:
            self._timer = async_call_later(
                self.hub.hass, self._delay, self._delay_elapsed
            )
        else:
            self._activate()

    @callback
    def _activate(self) -> None:
        """The source is active (and has held for the delay)."""
        self.source_active = True
        self.dismissed = self._keep_dismissed
        self._changed()

    @callback
    def _delay_elapsed(self, _now: Any) -> None:
        """The source has held for the delay."""
        self._timer = None
        self._activate()

    @callback
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the notification (persistent).

        Args:
            enabled: New state.
        """
        if enabled != self.enabled:
            self.enabled = enabled
            self._changed()

    @callback
    def dismiss(self) -> None:
        """Hide it until its source next goes inactive and active again."""
        if self.previewing:
            self.previewing = False
            if self._preview_timer:
                self._preview_timer()
                self._preview_timer = None
            self._changed()
        if self.source_active and not self.dismissed:
            self.dismissed = self._keep_dismissed = True
            self._changed()

    @callback
    def preview(self) -> None:
        """Show it on its lights for PREVIEW_SECONDS regardless of its source."""
        if self._preview_timer:
            self._preview_timer()
        self.previewing = True
        self._preview_timer = async_call_later(
            self.hub.hass, PREVIEW_SECONDS, self._preview_done
        )
        self._changed()

    @callback
    def _preview_done(self, _now: Any) -> None:
        """End a preview."""
        self._preview_timer = None
        self.previewing = False
        self._changed()


class Hub:
    """Owns the notifications and the lights of one config entry and renders them."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Create the hub.

        Args:
            hass: Home Assistant instance.
            entry: The integration's config entry.
        """
        self.hass = hass
        self.entry = entry
        self.notifications: dict[str, NotificationRuntime] = {}
        self.lights: dict[str, dict[str, Any]] = {}
        self._quiet_entity: str | None = entry.data.get(CONF_QUIET_ENTITY)
        self._unsubs: list[CALLBACK_TYPE] = []
        self._light_previews: dict[str, CALLBACK_TYPE] = {}
        self._preview_lights: set[str] = set()
        self._painted: dict[str, list[dict[str, Any]]] = {}
        self._task: Any = None
        self._again = False
        self._applied: Any = None
        self._store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.dismissed")

    def _items(self, kind: str) -> dict[str, dict[str, Any]]:
        """Return the stored data of every subentry of one type, by id."""
        return {
            sid: dict(sub.data)
            for sid, sub in self.entry.subentries.items()
            if sub.subentry_type == kind
        }

    def _snapshot(self) -> Any:
        """Everything a reload would re-read: the entry's data and every subentry's data."""
        return deepcopy(
            (dict(self.entry.data), {s: dict(v.data) for s, v in self.entry.subentries.items()})
        )

    async def async_start(self) -> None:
        """Load the stored items, start following sources and draw the first frame."""
        self._applied = self._snapshot()
        dismissed = set((await self._store.async_load() or {}).get("dismissed", []))
        for item_id, data in self._items(KIND_NOTIFICATION).items():
            self.notifications[item_id] = NotificationRuntime(
                self, item_id, data, item_id in dismissed
            )
        self.lights = self._items(KIND_LIGHT)
        for runtime in self.notifications.values():
            await runtime.async_start()
        if self._quiet_entity:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, [self._quiet_entity], lambda _e: self.request_render()
                )
            )
        self.request_render()

    def _dismissed_data(self) -> dict[str, list[str]]:
        """The ids of dismissed notifications, as stored."""
        return {"dismissed": [i for i, n in self.notifications.items() if n._keep_dismissed]}

    @callback
    def save_dismissed(self) -> None:
        """Remember dismissals so a restart or reload does not bring a notification back."""
        self._store.async_delay_save(self._dismissed_data, 1)

    async def async_stop(self) -> None:
        """Stop following sources and put the lights back."""
        await self._store.async_save(self._dismissed_data())
        for runtime in self.notifications.values():
            runtime.async_stop()
        for unsub in self._unsubs:
            unsub()
        for cancel in self._light_previews.values():
            cancel()
        self._unsubs.clear()
        self._light_previews.clear()
        self.notifications.clear()
        self._preview_lights.clear()
        await self._render_once()

    def is_applied(self) -> bool:
        """Whether the entry's data and subentries are already what is running.

        Returns:
            True when they match what the hub last loaded or saved itself (no reload needed).
        """
        return self._snapshot() == self._applied

    @callback
    def set_colour(self, item_id: str, rgb: list[int]) -> None:
        """Change a notification's colour and save it, without reloading the entry.

        Args:
            item_id: The notification's id.
            rgb: New [r, g, b].
        """
        runtime = self.notifications[item_id]
        runtime.rgb = rgb
        runtime.data[CONF_COLOUR] = rgb
        sub = self.entry.subentries[item_id]
        self.hass.config_entries.async_update_subentry(
            self.entry, sub, data={**sub.data, CONF_COLOUR: rgb}
        )
        self._applied = self._snapshot()  # listeners run later, so they see no change
        runtime.preview()

    @callback
    def dismiss_all(self) -> None:
        """Dismiss every active notification."""
        for runtime in self.notifications.values():
            runtime.dismiss()

    @callback
    def preview_light(self, item_id: str) -> None:
        """Show eighth 1 on one light for PREVIEW_SECONDS, to calibrate its offset.

        Args:
            item_id: The light's id.
        """
        if cancel := self._light_previews.pop(item_id, None):
            cancel()
        self._preview_lights.add(item_id)

        @callback
        def _done(_now: Any) -> None:
            self._light_previews.pop(item_id, None)
            self._preview_lights.discard(item_id)
            self.request_render()

        self._light_previews[item_id] = async_call_later(
            self.hass, PREVIEW_SECONDS, _done
        )
        self.request_render()

    @callback
    def request_render(self) -> None:
        """Draw soon; changes arriving during a draw cause one more pass."""
        if self._task is not None and not self._task.done():
            self._again = True
            return
        self._task = self.hass.async_create_task(self._render_loop())

    async def _render_loop(self) -> None:
        """Render until no further change arrived during the last pass."""
        while True:
            self._again = False
            try:
                await self._render_once()
            except Exception:  # noqa: BLE001 - keep the loop alive for the next change
                _LOGGER.exception("Rendering notification lights failed")
            if not self._again:
                return

    def _quiet_active(self) -> bool:
        """Whether the configured quiet-hours entity is on."""
        return bool(self._quiet_entity) and self.hass.states.is_state(
            self._quiet_entity, "on"
        )

    async def _render_once(self) -> None:
        """Draw every light, or put it back when nothing is left to show."""
        quiet = self._quiet_active()
        for item_id, light in self.lights.items():
            layers = [
                (n.priority, n.footprint, n.rgb)
                for n in self.notifications.values()
                if n.showing
                and applies(
                    n.data[CONF_SCOPE],
                    n.data.get(CONF_SCOPE_AREA),
                    n.data.get(CONF_SCOPE_FLOOR),
                    light.get(CONF_AREAS, []),
                    light.get(CONF_FLOOR),
                )
                and not (quiet and light[CONF_QUIET_HOURS] and not n.show_quiet)
            ]
            if item_id in self._preview_lights:
                layers.append((0, "eighth_1", [255, 255, 255]))
            pattern = build_pattern(light[CONF_SEGMENTS], light[CONF_OFFSET], layers)
            await self._apply(light, pattern)

    async def _apply(self, light: dict[str, Any], pattern: list[dict[str, Any]]) -> None:
        """Send a pattern, or restore/turn off the light when the pattern is empty.

        Idempotent: nothing is sent when the pattern is unchanged, and an idle light is
        only touched once after it was painted.

        Args:
            light: The light's settings.
            pattern: Segment colours, or [] for nothing to show.
        """
        entity = light[CONF_LIGHT]
        snapshot = f"scene.notification_lights_{entity.split('.')[1]}"
        painted = entity in self._painted
        if pattern:
            if self._painted.get(entity) == pattern:
                return
            if not painted and light[CONF_IDLE_POLICY] == IDLE_RESTORE:
                await self.hass.services.async_call(
                    "scene",
                    "create",
                    {"scene_id": snapshot.split(".")[1], "snapshot_entities": [entity]},
                    blocking=True,
                )
            await self.hass.services.async_call(
                AQARA_DOMAIN,
                "set_segment_pattern",
                {
                    "segment_colors": pattern,
                    "brightness": light[CONF_BRIGHTNESS],
                    "turn_on": True,
                },
                target={"entity_id": entity},
                blocking=True,
            )
            self._painted[entity] = pattern
        elif painted:
            del self._painted[entity]
            if light[CONF_IDLE_POLICY] == IDLE_RESTORE and self.hass.states.get(snapshot):
                await self.hass.services.async_call(
                    "scene", "turn_on", {"entity_id": snapshot}, blocking=True
                )
                await self.hass.services.async_call(
                    "scene", "delete", {"entity_id": snapshot}, blocking=True
                )
            elif self.hass.states.is_state(entity, "on"):
                await self.hass.services.async_call(
                    "light", "turn_off", {"entity_id": entity}, blocking=True
                )


def _truth(result: Any) -> bool | None:
    """Read a template result as a boolean; unknown and unavailable are undecided (None)."""
    if isinstance(result, str) and result.strip().lower() in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    return result_as_boolean(result)

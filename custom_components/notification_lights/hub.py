"""Runtime: tracks every notification's source and draws the result on the lights."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    EventStateChangedData,
    TrackTemplate,
    async_call_later,
    async_track_state_change_event,
    async_track_template_result,
)
from homeassistant.helpers.template import Template, result_as_boolean

from .const import (
    AQARA_DOMAIN,
    CONF_AREAS,
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

    def __init__(self, hub: Hub, item_id: str, data: dict[str, Any]) -> None:
        """Create the runtime for one stored notification.

        Args:
            hub: The owning hub.
            item_id: The notification's id.
            data: The notification's stored data.
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
        self.previewing = False
        self._raw = False
        self._delay = float(self.data.get(CONF_DELAY, 0))
        self._timer: CALLBACK_TYPE | None = None
        self._preview_timer: CALLBACK_TYPE | None = None
        self._unsubs: list[CALLBACK_TYPE] = []
        self._listeners: list[Callable[[], None]] = []

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
                self._set_raw(result_as_boolean(result))

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

    def _render_bool(self, template: Template) -> bool:
        """Render a template to a boolean; errors count as inactive."""
        try:
            return result_as_boolean(template.async_render(parse_result=False))
        except Exception as err:  # noqa: BLE001 - a bad template must not stop setup
            _LOGGER.warning("%s: template error: %s", self.name, err)
            return False

    def _entities_match(self) -> bool:
        """True when any source entity is in the configured state."""
        wanted = self.data[CONF_SOURCE_STATE]
        return any(
            self.hub.hass.states.is_state(e, wanted)
            for e in self.data[CONF_SOURCE_ENTITIES]
        )

    @callback
    def _set_raw(self, value: bool) -> None:
        """Apply the source's raw truth value, honouring the delay.

        The notification follows the source exactly: it turns on only after the source
        has been true for the delay, and off the moment the source is false. A dismissal
        ends when the source goes false.
        """
        if value == self._raw:
            return
        self._raw = value
        if self._timer:
            self._timer()
            self._timer = None
        if not value:
            self.source_active = False
            self.dismissed = False
            self._changed()
        elif self._delay > 0:
            self._timer = async_call_later(
                self.hub.hass, self._delay, self._delay_elapsed
            )
        else:
            self.source_active = True
            self._changed()

    @callback
    def _delay_elapsed(self, _now: Any) -> None:
        """The source has held for the delay."""
        self._timer = None
        self.source_active = True
        self._changed()

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
        if self.source_active and not self.dismissed:
            self.dismissed = True
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

    async def async_start(self) -> None:
        """Load the stored items, start following sources and draw the first frame."""
        for item_id, data in self.entry.options.get(KIND_NOTIFICATION, {}).items():
            self.notifications[item_id] = NotificationRuntime(self, item_id, data)
        for item_id, data in self.entry.options.get(KIND_LIGHT, {}).items():
            self.lights[item_id] = dict(data)
        for runtime in self.notifications.values():
            await runtime.async_start()
        if self._quiet_entity:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, [self._quiet_entity], lambda _e: self.request_render()
                )
            )
        self.request_render()

    async def async_stop(self) -> None:
        """Stop following sources and put the lights back."""
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

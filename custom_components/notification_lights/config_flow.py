"""Config flow for Notification Lights: setup, plus one manager under Configure.

Lights and notifications are stored as subentries, but are managed as two groups from
the integration's Configure dialog rather than one add-flow per item.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.template import Template

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
    CONF_NAME,
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
    DOMAIN,
    IDLE_OFF,
    IDLE_POLICIES,
    SCOPE_FLOOR,
    SCOPE_HOUSE,
    SCOPE_ROOM,
    SCOPES,
    SOURCE_ENTITIES,
    SOURCE_TEMPLATE,
    SUBENTRY_LIGHT,
    SUBENTRY_NOTIFICATION,
)
from .footprint import FOOTPRINTS
from .summary import light_summary, notification_label, notification_summary
from .validation import validate_pick, validate_priority, validate_ring

CHOICE = "choice"
CHOICE_ADD = "__add__"
CHOICE_BACK = "__back__"
CONF_REMOVE = "remove"


def area_id_of(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the entity's area, falling back to its device's area.

    Args:
        hass: Home Assistant instance.
        entity_id: Entity to look up.

    Returns:
        The area id, or None when neither entity nor device has one.
    """
    entry = er.async_get(hass).async_get(entity_id)
    if entry is None:
        return None
    if entry.area_id:
        return entry.area_id
    if entry.device_id and (device := dr.async_get(hass).async_get(entry.device_id)):
        return device.area_id
    return None


def floor_id_of(hass: HomeAssistant, area_id: str | None) -> str | None:
    """Return the floor an area is on.

    Args:
        hass: Home Assistant instance.
        area_id: Area to look up, or None.

    Returns:
        The floor id, or None when the area is None or on no floor.
    """
    area = ar.async_get(hass).async_get_area(area_id) if area_id else None
    return area.floor_id if area else None


def friendly_name_of(hass: HomeAssistant, entity_id: str) -> str:
    """Return an entity's display name.

    Args:
        hass: Home Assistant instance.
        entity_id: Entity to look up.

    Returns:
        Its friendly name, else its registry name, else the entity id.
    """
    if (state := hass.states.get(entity_id)) and state.attributes.get("friendly_name"):
        return state.attributes["friendly_name"]
    entry = er.async_get(hass).async_get(entity_id)
    if entry and (entry.name or entry.original_name):
        return entry.name or entry.original_name
    return entity_id


class NotificationLightsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance setup: only the optional quiet-hours entity."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the manager shown under Configure.

        Args:
            config_entry: The integration's config entry.

        Returns:
            The manager flow.
        """
        return ManagerFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """No add-flows: items are managed as groups under Configure.

        Args:
            config_entry: The integration's config entry.

        Returns:
            An empty map.
        """
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the quiet-hours entity (optional) and create the entry."""
        # A hard `dependencies` entry would fail with a generic error before this flow
        # runs, so check here and tell the user what to install.
        if not self.hass.config_entries.async_entries(AQARA_DOMAIN):
            return self.async_abort(reason="aqara_missing")

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Notification Lights", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_quiet_schema())


def _quiet_schema() -> vol.Schema:
    """Schema for the optional quiet-hours entity."""
    return vol.Schema(
        {
            vol.Optional(CONF_QUIET_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["input_boolean", "binary_sensor", "schedule", "switch"]
                )
            )
        }
    )


def _pick_schema(options: list[dict[str, str]]) -> vol.Schema:
    """Schema for a group screen: one list to pick from."""
    return vol.Schema(
        {
            vol.Required(CHOICE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options, mode=selector.SelectSelectorMode.LIST
                )
            )
        }
    )


class ManagerFlow(OptionsFlow):
    """Manage quiet hours, Notification lights and Notifications from one place."""

    def __init__(self) -> None:
        """Start with nothing being edited."""
        self._data: dict[str, Any] = {}
        self._item_id: str | None = None
        self._light: str = ""

    # --- helpers ---------------------------------------------------------------

    def _items(self, subentry_type: str) -> dict[str, ConfigSubentry]:
        """Return this entry's subentries of one type."""
        return {
            sid: s
            for sid, s in self.config_entry.subentries.items()
            if s.subentry_type == subentry_type
        }

    def _save(self, subentry_type: str, title: str, data: dict[str, Any]) -> None:
        """Create the item being edited, or update it."""
        if self._item_id is None:
            self.hass.config_entries.async_add_subentry(
                self.config_entry,
                ConfigSubentry(
                    data=MappingProxyType(data),
                    subentry_type=subentry_type,
                    title=title,
                    unique_id=None,
                ),
            )
        else:
            self.hass.config_entries.async_update_subentry(
                self.config_entry,
                self.config_entry.subentries[self._item_id],
                data=data,
                title=title,
            )

    def _remove(self) -> None:
        """Remove the item being edited."""
        if self._item_id is not None:
            self.hass.config_entries.async_remove_subentry(
                self.config_entry, self._item_id
            )

    @property
    def _current(self) -> dict[str, Any]:
        """Values of the item being edited (empty when adding)."""
        return dict(self._data)

    # --- top menu --------------------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Show the top-level menu.

        Args:
            user_input: Unused; this is a menu.

        Returns:
            The menu.
        """
        return self.async_show_menu(
            step_id="init", menu_options=["lights", "notifications", "settings", "done"]
        )

    async def async_step_done(self, user_input: dict[str, Any] | None = None) -> Any:
        """Close the dialog.

        Args:
            user_input: Unused.

        Returns:
            A finished flow (options unchanged; items are saved as you go).
        """
        return self.async_create_entry(data=dict(self.config_entry.options))

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Pick the quiet-hours entity.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the menu once saved.
        """
        if user_input is not None:
            data = {k: v for k, v in self.config_entry.data.items() if k != CONF_QUIET_ENTITY}
            if user_input.get(CONF_QUIET_ENTITY):
                data[CONF_QUIET_ENTITY] = user_input[CONF_QUIET_ENTITY]
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
            return await self.async_step_init()
        return self.async_show_form(
            step_id="settings",
            data_schema=self.add_suggested_values_to_schema(
                _quiet_schema(), dict(self.config_entry.data)
            ),
        )

    # --- Notification lights ----------------------------------------------------

    async def async_step_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """List all Notification lights; add one or pick one to edit.

        Args:
            user_input: The submitted choice, or None to show the list.

        Returns:
            The list, or the next step.
        """
        items = self._items(SUBENTRY_LIGHT)
        if user_input is not None:
            choice = user_input[CHOICE]
            if choice == CHOICE_BACK:
                return await self.async_step_init()
            if choice == CHOICE_ADD:
                self._item_id, self._data = None, {}
                return await self.async_step_light_pick()
            self._item_id, self._data = choice, dict(items[choice].data)
            self._light = self._data[CONF_LIGHT]
            self._data.setdefault(CONF_NAME, friendly_name_of(self.hass, self._light))
            return await self.async_step_light_details()
        options = [
            {"value": CHOICE_ADD, "label": "Add a notification light"},
            *[
                {"value": sid, "label": s.data.get(CONF_NAME) or s.data[CONF_LIGHT]}
                for sid, s in sorted(items.items(), key=lambda kv: kv[1].data.get(CONF_NAME) or kv[1].data[CONF_LIGHT])
            ],
            {"value": CHOICE_BACK, "label": "Back"},
        ]
        return self.async_show_form(
            step_id="lights",
            data_schema=_pick_schema(options),
            description_placeholders={
                "summary": light_summary(s.data for s in items.values())
            },
        )

    async def async_step_light_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Pick the ring entity of a new Notification light.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the details step once a valid light is picked.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            others = [s.data[CONF_LIGHT] for s in self._items(SUBENTRY_LIGHT).values()]
            errors = validate_pick(user_input[CONF_LIGHT], others)
            if not errors:
                self._light = user_input[CONF_LIGHT]
                area = area_id_of(self.hass, self._light)
                self._data = {
                    CONF_NAME: friendly_name_of(self.hass, self._light),
                    CONF_AREAS: [area] if area else [],
                    CONF_FLOOR: floor_id_of(self.hass, area),
                }
                return await self.async_step_light_details()
        schema = vol.Schema(
            {
                vol.Required(CONF_LIGHT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="light")
                )
            }
        )
        return self.async_show_form(
            step_id="light_pick", data_schema=schema, errors=errors
        )

    async def async_step_light_details(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Rooms, floor and drawing options of a light (prefilled from its device).

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the group list once saved or removed.
        """
        errors: dict[str, str] = {}
        editing = self._item_id is not None
        if user_input is not None:
            if user_input.pop(CONF_REMOVE, False):
                self._remove()
                return await self.async_step_lights()
            # NumberSelector returns floats.
            for key in (CONF_SEGMENTS, CONF_OFFSET, CONF_BRIGHTNESS):
                user_input[key] = int(user_input[key])
            errors = validate_ring(user_input)
            if not errors:
                self._save(
                    SUBENTRY_LIGHT,
                    user_input[CONF_NAME],
                    {CONF_LIGHT: self._light, **user_input},
                )
                return await self.async_step_lights()

        fields: dict[Any, Any] = {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Optional(CONF_AREAS, default=[]): selector.AreaSelector(
                selector.AreaSelectorConfig(multiple=True)
            ),
            vol.Optional(CONF_FLOOR): selector.FloorSelector(),
            vol.Required(CONF_SEGMENTS, default=26): selector.NumberSelector(
                selector.NumberSelectorConfig(min=8, max=60, mode="box")
            ),
            vol.Required(CONF_OFFSET, default=0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, mode="box")
            ),
            vol.Required(CONF_BRIGHTNESS, default=100): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=100, unit_of_measurement="%")
            ),
            vol.Required(CONF_QUIET_HOURS, default=False): bool,
            vol.Required(CONF_IDLE_POLICY, default=IDLE_OFF): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=IDLE_POLICIES, translation_key=CONF_IDLE_POLICY
                )
            ),
        }
        if editing:
            fields[vol.Optional(CONF_REMOVE, default=False)] = bool
        return self.async_show_form(
            step_id="light_details",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(fields), user_input if user_input is not None else self._current
            ),
            errors=errors,
            description_placeholders={"light": self._data.get(CONF_NAME) or self._light},
        )

    # --- Notifications ----------------------------------------------------------

    def _other_priorities(self) -> list[int]:
        """Priorities used by the other notifications."""
        return [
            int(s.data[CONF_PRIORITY])
            for sid, s in self._items(SUBENTRY_NOTIFICATION).items()
            if sid != self._item_id
        ]

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """List all notifications by priority; add one or pick one to edit.

        Args:
            user_input: The submitted choice, or None to show the list.

        Returns:
            The list, or the next step.
        """
        items = self._items(SUBENTRY_NOTIFICATION)
        if user_input is not None:
            choice = user_input[CHOICE]
            if choice == CHOICE_BACK:
                return await self.async_step_init()
            if choice == CHOICE_ADD:
                self._item_id, self._data = None, {}
            else:
                self._item_id, self._data = choice, dict(items[choice].data)
            return await self.async_step_notification()
        options = [
            {"value": CHOICE_ADD, "label": "Add a notification"},
            *[
                {"value": sid, "label": notification_label(s.data)}
                for sid, s in sorted(
                    items.items(), key=lambda kv: int(kv[1].data[CONF_PRIORITY])
                )
            ],
            {"value": CHOICE_BACK, "label": "Back"},
        ]
        return self.async_show_form(
            step_id="notifications",
            data_schema=_pick_schema(options),
            description_placeholders={
                "summary": notification_summary(s.data for s in items.values())
            },
        )

    async def async_step_notification(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Name, colour, footprint, priority, quiet hours, scope and delay.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the next step.
        """
        errors: dict[str, str] = {}
        others = self._other_priorities()
        if user_input is not None:
            if user_input.pop(CONF_REMOVE, False):
                self._remove()
                return await self.async_step_notifications()
            user_input[CONF_PRIORITY] = int(user_input[CONF_PRIORITY])
            user_input[CONF_DELAY] = int(user_input[CONF_DELAY])
            errors = validate_priority(user_input[CONF_PRIORITY], others)
            if not errors:
                self._data.update(user_input)
                scope = user_input[CONF_SCOPE]
                if scope == SCOPE_ROOM:
                    return await self.async_step_notification_room()
                if scope == SCOPE_FLOOR:
                    return await self.async_step_notification_floor()
                return await self.async_step_notification_source()

        defaults = {
            CONF_COLOUR: [255, 255, 255],
            CONF_FOOTPRINT: "eighth_1",
            CONF_PRIORITY: max(others, default=0) + 1,
            CONF_SHOW_QUIET: False,
            CONF_SCOPE: SCOPE_HOUSE,
            CONF_DELAY: 0,
            **self._current,
        }
        fields: dict[Any, Any] = {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_COLOUR): selector.ColorRGBSelector(),
            vol.Required(CONF_FOOTPRINT): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=FOOTPRINTS, translation_key=CONF_FOOTPRINT
                )
            ),
            vol.Required(CONF_PRIORITY): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, mode="box")
            ),
            vol.Required(CONF_SHOW_QUIET): bool,
            vol.Required(CONF_SCOPE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=SCOPES, translation_key=CONF_SCOPE
                )
            ),
            vol.Required(CONF_DELAY): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, mode="box", unit_of_measurement="s"
                )
            ),
        }
        if self._item_id is not None:
            fields[vol.Optional(CONF_REMOVE, default=False)] = bool
        return self.async_show_form(
            step_id="notification",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(fields), user_input if user_input is not None else defaults
            ),
            errors=errors,
        )

    async def async_step_notification_room(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Pick the room for room scope.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the source menu.
        """
        if user_input is not None:
            self._data[CONF_SCOPE_AREA] = user_input[CONF_SCOPE_AREA]
            self._data.pop(CONF_SCOPE_FLOOR, None)
            return await self.async_step_notification_source()
        schema = vol.Schema({vol.Required(CONF_SCOPE_AREA): selector.AreaSelector()})
        return self.async_show_form(
            step_id="notification_room",
            data_schema=self.add_suggested_values_to_schema(schema, self._current),
        )

    async def async_step_notification_floor(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Pick the floor for floor scope.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the source menu.
        """
        if user_input is not None:
            self._data[CONF_SCOPE_FLOOR] = user_input[CONF_SCOPE_FLOOR]
            self._data.pop(CONF_SCOPE_AREA, None)
            return await self.async_step_notification_source()
        schema = vol.Schema({vol.Required(CONF_SCOPE_FLOOR): selector.FloorSelector()})
        return self.async_show_form(
            step_id="notification_floor",
            data_schema=self.add_suggested_values_to_schema(schema, self._current),
        )

    async def async_step_notification_source(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Choose how the source is defined: entities or a template.

        Args:
            user_input: Unused; this is a menu.

        Returns:
            The menu.
        """
        if self._data[CONF_SCOPE] == SCOPE_HOUSE:
            self._data.pop(CONF_SCOPE_AREA, None)
            self._data.pop(CONF_SCOPE_FLOOR, None)
        return self.async_show_menu(
            step_id="notification_source",
            menu_options=["notification_entities", "notification_template"],
        )

    async def async_step_notification_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Source from entities: active while any is in the given state.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the group list once saved.
        """
        if user_input is not None:
            self._data.update(user_input)
            self._data[CONF_SOURCE_TYPE] = SOURCE_ENTITIES
            self._data.pop(CONF_SOURCE_TEMPLATE, None)
            return await self._finish_notification()
        schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True)
                ),
                vol.Required(CONF_SOURCE_STATE, default="on"): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="notification_entities",
            data_schema=self.add_suggested_values_to_schema(schema, self._current),
        )

    async def async_step_notification_template(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Source from a template: active while it renders true.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the group list once saved.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                Template(user_input[CONF_SOURCE_TEMPLATE], self.hass).ensure_valid()
            except TemplateError:
                errors[CONF_SOURCE_TEMPLATE] = "invalid_template"
            else:
                self._data.update(user_input)
                self._data[CONF_SOURCE_TYPE] = SOURCE_TEMPLATE
                self._data.pop(CONF_SOURCE_ENTITIES, None)
                self._data.pop(CONF_SOURCE_STATE, None)
                return await self._finish_notification()
        schema = vol.Schema(
            {vol.Required(CONF_SOURCE_TEMPLATE): selector.TemplateSelector()}
        )
        return self.async_show_form(
            step_id="notification_template",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input if user_input is not None else self._current
            ),
            errors=errors,
        )

    async def _finish_notification(self) -> Any:
        """Save the notification and return to the group list."""
        self._save(SUBENTRY_NOTIFICATION, self._data[CONF_NAME], dict(self._data))
        return await self.async_step_notifications()

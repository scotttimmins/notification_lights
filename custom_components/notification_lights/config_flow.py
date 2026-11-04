"""Config flow for Notification Lights.

Setup asks for the quiet-hours entity. Each light and each notification is a config
subentry, so the integration page shows two collapsible sections with an Add button each
and Reconfigure and Delete on every item. Configure only changes the quiet-hours entity.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
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
    KIND_LIGHT,
    KIND_NOTIFICATION,
)
from .footprint import FOOTPRINTS
from .validation import validate_pick, validate_priority, validate_ring

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

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the quiet-hours dialog shown under Configure.

        Args:
            config_entry: The integration's config entry.

        Returns:
            The quiet-hours flow.
        """
        return QuietFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the two kinds of item added from the integration page.

        Args:
            config_entry: The integration's config entry.

        Returns:
            The flow for each subentry type.
        """
        return {KIND_LIGHT: LightSubentryFlow, KIND_NOTIFICATION: NotificationSubentryFlow}

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




class _FormBase:
    """State and helpers shared by the flows that define a light or a notification."""

    def _init_state(self) -> None:
        """Start with nothing being edited."""
        self._data: dict[str, Any] = {}
        self._item_id: str | None = None
        self._light: str = ""

    def _items(self, kind: str) -> dict[str, dict[str, Any]]:
        """Return the stored data of every subentry of one type, by id."""
        return {
            sid: dict(sub.data)
            for sid, sub in self._get_entry().subentries.items()
            if sub.subentry_type == kind
        }

    @property
    def _current(self) -> dict[str, Any]:
        """Values of the item being edited (empty when adding)."""
        return dict(self._data)

    def _load_for_reconfigure(self) -> None:
        """Load the subentry being reconfigured."""
        sub = self._get_reconfigure_subentry()
        self._item_id, self._data = sub.subentry_id, dict(sub.data)

    def _save(self, data: dict[str, Any]) -> Any:
        """Create the subentry, or update the one being reconfigured.

        Args:
            data: The finished item.

        Returns:
            The finished flow.
        """
        title = data.get(CONF_NAME) or data[CONF_LIGHT]
        if self._item_id is None:
            return self.async_create_entry(title=title, data=data)
        return self.async_update_and_abort(
            self._get_entry(), self._get_reconfigure_subentry(), title=title, data=data
        )


class LightSubentryFlow(_FormBase, ConfigSubentryFlow):
    """Add or reconfigure a Notification light."""

    def __init__(self) -> None:
        """Start with nothing being edited."""
        self._init_state()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        """Pick the ring entity of a new Notification light.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the details step once a valid light is picked.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            others = [s[CONF_LIGHT] for s in self._items(KIND_LIGHT).values()]
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
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> Any:
        """Edit every setting of an existing light in one form."""
        self._load_for_reconfigure()
        self._light = self._data[CONF_LIGHT]
        self._data.setdefault(CONF_NAME, friendly_name_of(self.hass, self._light))
        return await self.async_step_light_details()

    async def async_step_light_details(self, user_input: dict[str, Any] | None = None) -> Any:
        """Name, rooms, floor and drawing options (prefilled from the light's device).

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the finished flow.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            # NumberSelector returns floats.
            for key in (CONF_SEGMENTS, CONF_OFFSET, CONF_BRIGHTNESS):
                user_input[key] = int(user_input[key])
            errors = validate_ring(user_input)
            if not errors:
                return self._save({CONF_LIGHT: self._light, **user_input})

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
        return self.async_show_form(
            step_id="light_details",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(fields), user_input if user_input is not None else self._current
            ),
            errors=errors,
            description_placeholders={"light": self._data.get(CONF_NAME) or self._light},
        )


class NotificationSubentryFlow(_FormBase, ConfigSubentryFlow):
    """Add or reconfigure a notification: every setting in one form."""

    def __init__(self) -> None:
        """Start with nothing being edited."""
        self._init_state()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        """Add a notification."""
        return await self.async_step_notification()

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> Any:
        """Edit every setting of an existing notification in one form."""
        self._load_for_reconfigure()
        return await self.async_step_notification()

    def _other_priorities(self) -> list[int]:
        """Priorities used by the other notifications."""
        return [
            int(s[CONF_PRIORITY])
            for sid, s in self._items(KIND_NOTIFICATION).items()
            if sid != self._item_id
        ]

    def _check(self, values: dict[str, Any], others: list[int]) -> tuple[dict[str, Any], dict[str, str]]:
        """Validate the form and tidy it into the stored shape.

        Scope and source each keep only the fields that apply, so switching one in the
        form never leaves the other's values behind.

        Args:
            values: The submitted form.
            others: Priorities used by other notifications.

        Returns:
            The stored data and the errors by field.
        """
        data = dict(values)
        data[CONF_PRIORITY] = int(data[CONF_PRIORITY])
        data[CONF_DELAY] = int(data[CONF_DELAY])
        errors = validate_priority(data[CONF_PRIORITY], others)

        scope = data[CONF_SCOPE]
        if scope != SCOPE_ROOM:
            data.pop(CONF_SCOPE_AREA, None)
        elif not data.get(CONF_SCOPE_AREA):
            errors[CONF_SCOPE_AREA] = "area_required"
        if scope != SCOPE_FLOOR:
            data.pop(CONF_SCOPE_FLOOR, None)
        elif not data.get(CONF_SCOPE_FLOOR):
            errors[CONF_SCOPE_FLOOR] = "floor_required"

        template = (data.get(CONF_SOURCE_TEMPLATE) or "").strip()
        entities = data.get(CONF_SOURCE_ENTITIES) or []
        if template and entities:
            errors[CONF_SOURCE_TEMPLATE] = "one_source"
        elif template:
            try:
                Template(template, self.hass).ensure_valid()
            except TemplateError:
                errors[CONF_SOURCE_TEMPLATE] = "invalid_template"
            data[CONF_SOURCE_TYPE] = SOURCE_TEMPLATE
            data[CONF_SOURCE_TEMPLATE] = template
            data.pop(CONF_SOURCE_ENTITIES, None)
            data.pop(CONF_SOURCE_STATE, None)
        elif entities:
            data[CONF_SOURCE_TYPE] = SOURCE_ENTITIES
            data.setdefault(CONF_SOURCE_STATE, "on")
            data.pop(CONF_SOURCE_TEMPLATE, None)
        else:
            errors[CONF_SOURCE_ENTITIES] = "source_required"
        return data, errors

    async def async_step_notification(self, user_input: dict[str, Any] | None = None) -> Any:
        """Name, colour, footprint, priority, quiet hours, scope, source and delay.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the finished flow.
        """
        errors: dict[str, str] = {}
        others = self._other_priorities()
        if user_input is not None:
            data, errors = self._check(user_input, others)
            if not errors:
                return self._save(data)

        defaults = {
            CONF_COLOUR: [255, 255, 255],
            CONF_FOOTPRINT: "eighth_1",
            CONF_PRIORITY: max(others, default=0) + 1,
            CONF_SHOW_QUIET: False,
            CONF_SCOPE: SCOPE_HOUSE,
            CONF_DELAY: 0,
            CONF_SOURCE_STATE: "on",
            **self._current,
        }
        fields: dict[Any, Any] = {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_COLOUR): selector.ColorRGBSelector(),
            vol.Required(CONF_FOOTPRINT): selector.SelectSelector(
                selector.SelectSelectorConfig(options=FOOTPRINTS, translation_key=CONF_FOOTPRINT)
            ),
            vol.Required(CONF_PRIORITY): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, mode="box")
            ),
            vol.Required(CONF_SHOW_QUIET): bool,
            vol.Required(CONF_SCOPE): selector.SelectSelector(
                selector.SelectSelectorConfig(options=SCOPES, translation_key=CONF_SCOPE)
            ),
            vol.Optional(CONF_SCOPE_AREA): selector.AreaSelector(),
            vol.Optional(CONF_SCOPE_FLOOR): selector.FloorSelector(),
            vol.Optional(CONF_SOURCE_ENTITIES): selector.EntitySelector(
                selector.EntitySelectorConfig(multiple=True)
            ),
            vol.Optional(CONF_SOURCE_STATE): selector.TextSelector(),
            vol.Optional(CONF_SOURCE_TEMPLATE): selector.TemplateSelector(),
            vol.Required(CONF_DELAY): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, mode="box", unit_of_measurement="s")
            ),
        }
        return self.async_show_form(
            step_id="notification",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(fields), user_input if user_input is not None else defaults
            ),
            errors=errors,
        )


class QuietFlow(OptionsFlow):
    """Configure: pick the quiet-hours entity (lights and notifications are added on the integration page)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        """Pick the quiet-hours entity.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the finished flow once saved.
        """
        if user_input is not None:
            data = {k: v for k, v in self.config_entry.data.items() if k != CONF_QUIET_ENTITY}
            if user_input.get(CONF_QUIET_ENTITY):
                data[CONF_QUIET_ENTITY] = user_input[CONF_QUIET_ENTITY]
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _quiet_schema(), dict(self.config_entry.data)
            ),
        )

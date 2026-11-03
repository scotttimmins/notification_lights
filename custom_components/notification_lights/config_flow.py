"""Config flow for Notification Lights."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
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


class NotificationLightsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance setup: only the optional quiet-hours entity."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Offer the Notification light subentry type.

        Args:
            config_entry: The integration's config entry.

        Returns:
            Subentry type name to flow class.
        """
        return {
            SUBENTRY_LIGHT: LightSubentryFlow,
            SUBENTRY_NOTIFICATION: NotificationSubentryFlow,
        }

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

        schema = vol.Schema(
            {
                vol.Optional(CONF_QUIET_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["input_boolean", "binary_sensor", "schedule", "switch"]
                    )
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)


class LightSubentryFlow(ConfigSubentryFlow):
    """Register one Notification light: the `_rgb` ring entity of a T1M."""

    _light: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick the Notification light.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the details step once a valid light is picked.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            others = [s.data[CONF_LIGHT] for s in self._get_entry().subentries.values()]
            errors = validate_pick(user_input[CONF_LIGHT], others)
            if not errors:
                self._light = user_input[CONF_LIGHT]
                return await self.async_step_details()
        schema = vol.Schema(
            {
                vol.Required(CONF_LIGHT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="light")
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Set the rooms, floor and drawing options of a new light.

        Rooms and floor are prefilled from the light's device; with neither it is
        house-only.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the created subentry.
        """
        area = area_id_of(self.hass, self._light)
        suggested = {
            CONF_AREAS: [area] if area else [],
            CONF_FLOOR: floor_id_of(self.hass, area),
        }
        return await self._async_details_form("details", suggested, user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a Notification light (offset calibration happens here).

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the updated subentry.
        """
        current = self._get_reconfigure_subentry()
        self._light = current.data[CONF_LIGHT]
        return await self._async_details_form(
            "reconfigure", dict(current.data), user_input
        )

    async def _async_details_form(
        self,
        step_id: str,
        suggested: dict[str, Any],
        user_input: dict[str, Any] | None,
    ) -> SubentryFlowResult:
        """Show or process the details form for add and reconfigure.

        Args:
            step_id: "details" (add) or "reconfigure" (edit).
            suggested: Values to prefill when nothing has been submitted yet.
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the created/updated subentry.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            # NumberSelector returns floats.
            for key in (CONF_SEGMENTS, CONF_OFFSET, CONF_BRIGHTNESS):
                user_input[key] = int(user_input[key])
            errors = validate_ring(user_input)
            if not errors:
                data = {CONF_LIGHT: self._light, **user_input}
                if step_id == "reconfigure":
                    return self.async_update_and_abort(
                        self._get_entry(),
                        self._get_reconfigure_subentry(),
                        title=self._light,
                        data=data,
                    )
                return self.async_create_entry(
                    title=self._light, data=data, unique_id=self._light
                )

        schema = vol.Schema(
            {
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
                    selector.NumberSelectorConfig(
                        min=1, max=100, unit_of_measurement="%"
                    )
                ),
                vol.Required(CONF_QUIET_HOURS, default=False): bool,
                vol.Required(
                    CONF_IDLE_POLICY, default=IDLE_OFF
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=IDLE_POLICIES, translation_key=CONF_IDLE_POLICY
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input if user_input is not None else suggested
            ),
            errors=errors,
        )


class NotificationSubentryFlow(ConfigSubentryFlow):
    """Define one Aqara Light Notification: how it looks, where it shows, what raises it."""

    def __init__(self) -> None:
        """Start with no collected data."""
        self._data: dict[str, Any] = {}
        self._editing = False

    @property
    def _current(self) -> dict[str, Any]:
        """Existing values when editing, otherwise nothing."""
        if self._editing:
            return dict(self._get_reconfigure_subentry().data)
        return {}

    def _other_priorities(self) -> list[int]:
        """Priorities used by the other notifications."""
        skip = self._get_reconfigure_subentry().subentry_id if self._editing else None
        return [
            int(s.data[CONF_PRIORITY])
            for s in self._get_entry().subentries.values()
            if s.subentry_type == SUBENTRY_NOTIFICATION and s.subentry_id != skip
        ]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Name, colour, footprint, priority, quiet hours, scope and delay.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the next step.
        """
        errors: dict[str, str] = {}
        others = self._other_priorities()
        if user_input is not None:
            user_input[CONF_PRIORITY] = int(user_input[CONF_PRIORITY])
            user_input[CONF_DELAY] = int(user_input[CONF_DELAY])
            errors = validate_priority(user_input[CONF_PRIORITY], others)
            if not errors:
                self._data.update(user_input)
                scope = user_input[CONF_SCOPE]
                if scope == SCOPE_ROOM:
                    return await self.async_step_scope_room()
                if scope == SCOPE_FLOOR:
                    return await self.async_step_scope_floor()
                return await self.async_step_source()

        defaults = {
            CONF_COLOUR: [255, 255, 255],
            CONF_FOOTPRINT: "eighth_1",
            CONF_PRIORITY: max(others, default=0) + 1,
            CONF_SHOW_QUIET: False,
            CONF_SCOPE: SCOPE_HOUSE,
            CONF_DELAY: 0,
            **self._current,
        }
        schema = vol.Schema(
            {
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
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input if user_input is not None else defaults
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a notification: the same steps, prefilled.

        Args:
            user_input: Unused; the first step collects it.

        Returns:
            The first form.
        """
        self._editing = True
        return await self.async_step_user()

    async def async_step_scope_room(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick the room for room scope.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the source step.
        """
        if user_input is not None:
            self._data[CONF_SCOPE_AREA] = user_input[CONF_SCOPE_AREA]
            self._data.pop(CONF_SCOPE_FLOOR, None)
            return await self.async_step_source()
        schema = vol.Schema({vol.Required(CONF_SCOPE_AREA): selector.AreaSelector()})
        return self.async_show_form(
            step_id="scope_room",
            data_schema=self.add_suggested_values_to_schema(schema, self._current),
        )

    async def async_step_scope_floor(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick the floor for floor scope.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the source step.
        """
        if user_input is not None:
            self._data[CONF_SCOPE_FLOOR] = user_input[CONF_SCOPE_FLOOR]
            self._data.pop(CONF_SCOPE_AREA, None)
            return await self.async_step_source()
        schema = vol.Schema({vol.Required(CONF_SCOPE_FLOOR): selector.FloorSelector()})
        return self.async_show_form(
            step_id="scope_floor",
            data_schema=self.add_suggested_values_to_schema(schema, self._current),
        )

    async def async_step_source(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
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
            step_id="source", menu_options=[SOURCE_ENTITIES, SOURCE_TEMPLATE]
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Source from entities: active while any is in the given state.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the finished subentry.
        """
        if user_input is not None:
            self._data.update(user_input)
            self._data[CONF_SOURCE_TYPE] = SOURCE_ENTITIES
            self._data.pop(CONF_SOURCE_TEMPLATE, None)
            return self._finish()
        schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True)
                ),
                vol.Required(CONF_SOURCE_STATE, default="on"): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="entities",
            data_schema=self.add_suggested_values_to_schema(schema, self._current),
        )

    async def async_step_template(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Source from a template: active while it renders true.

        Args:
            user_input: The submitted form, or None to show it.

        Returns:
            The form, or the finished subentry.
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
                return self._finish()
        schema = vol.Schema(
            {vol.Required(CONF_SOURCE_TEMPLATE): selector.TemplateSelector()}
        )
        return self.async_show_form(
            step_id="template",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input if user_input is not None else self._current
            ),
            errors=errors,
        )

    def _finish(self) -> SubentryFlowResult:
        """Create the subentry, or update it when editing."""
        if self._editing:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=self._data[CONF_NAME],
                data=self._data,
            )
        return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)

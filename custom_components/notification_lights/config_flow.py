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
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    AQARA_DOMAIN,
    CONF_AREAS,
    CONF_BRIGHTNESS,
    CONF_FLOOR,
    CONF_IDLE_POLICY,
    CONF_LIGHT,
    CONF_OFFSET,
    CONF_QUIET_ENTITY,
    CONF_QUIET_HOURS,
    CONF_SEGMENTS,
    DOMAIN,
    IDLE_OFF,
    IDLE_POLICIES,
    SUBENTRY_LIGHT,
)
from .validation import validate_pick, validate_ring


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
        return {SUBENTRY_LIGHT: LightSubentryFlow}

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

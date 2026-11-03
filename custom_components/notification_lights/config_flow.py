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
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    AQARA_DOMAIN,
    CONF_BRIGHTNESS,
    CONF_IDLE_POLICY,
    CONF_LIGHT,
    CONF_OFFSET,
    CONF_QUIET_AT_BEDTIME,
    CONF_QUIET_ENTITY,
    CONF_SEGMENTS,
    DOMAIN,
    IDLE_OFF,
    IDLE_POLICIES,
    SUBENTRY_LIGHT,
)


def area_id_of(hass, entity_id: str) -> str | None:
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


class NotificationLightsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance setup: only the optional quiet-hours entity."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Notification lights are added as subentries."""
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick the ring entity and its drawing settings.

        Rejects a ring that is already registered or that has no area, because scope
        (room, floor, house) is resolved from the area.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            # NumberSelector returns floats.
            for key in (CONF_SEGMENTS, CONF_OFFSET, CONF_BRIGHTNESS):
                user_input[key] = int(user_input[key])
            light = user_input[CONF_LIGHT]
            entry = self._get_entry()
            if any(s.data.get(CONF_LIGHT) == light for s in entry.subentries.values()):
                errors[CONF_LIGHT] = "already_added"
            elif area_id_of(self.hass, light) is None:
                errors[CONF_LIGHT] = "no_area"
            elif user_input[CONF_OFFSET] >= user_input[CONF_SEGMENTS]:
                errors[CONF_OFFSET] = "offset_too_large"
            if not errors:
                return self.async_create_entry(title=light, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_LIGHT): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="light", integration=AQARA_DOMAIN
                    )
                ),
                vol.Required(CONF_SEGMENTS, default=26): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=8, max=60, mode="box")
                ),
                vol.Required(CONF_OFFSET, default=0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=59, mode="box")
                ),
                vol.Required(CONF_BRIGHTNESS, default=100): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=100, unit_of_measurement="%")
                ),
                vol.Required(CONF_QUIET_AT_BEDTIME, default=False): bool,
                vol.Required(CONF_IDLE_POLICY, default=IDLE_OFF): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=IDLE_POLICIES, translation_key=CONF_IDLE_POLICY
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

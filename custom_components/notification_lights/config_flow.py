"""Config flow for Notification Lights."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import AQARA_DOMAIN, CONF_QUIET_ENTITY, DOMAIN


class NotificationLightsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance setup: only the optional quiet-hours entity."""

    VERSION = 1

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

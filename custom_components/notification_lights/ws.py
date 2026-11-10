"""Websocket command the dashboard strategy asks for what to show."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_NAME, DOMAIN
from .footprint import slots_of
from .printing import ring_url

COMMAND = f"{DOMAIN}/model"

# Entity part -> platform, matching the unique ids the entities are created with.
_PARTS = {
    "active": "binary_sensor",
    "enabled": "switch",
    "colour": "light",
    "preview": "button",
    "dismiss": "button",
}


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the model command.

    Args:
        hass: Home Assistant instance.
    """
    websocket_api.async_register_command(hass, _model)


def build_model(hass: HomeAssistant) -> dict[str, Any] | None:
    """List every notification and light with its entity ids.

    Entity ids come from the entity registry, which is filled before any state exists, so
    the answer does not depend on how far startup has got.

    Args:
        hass: Home Assistant instance.

    Returns:
        The model, or None while the integration has not loaded yet.
    """
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        return None
    entry = entries[0]
    hub = entry.runtime_data
    registry = er.async_get(hass)

    def entity(domain: str, unique_id: str) -> str | None:
        return registry.async_get_entity_id(domain, DOMAIN, unique_id)

    notifications = []
    for item_id, runtime in hub.notifications.items():
        notifications.append(
            {
                "name": runtime.name,
                "priority": runtime.priority,
                "footprint": runtime.footprint,
                "slots": slots_of(runtime.footprint),
                "picture": ring_url(runtime.footprint, runtime.rgb),
                **{part: entity(domain, f"{item_id}_{part}") for part, domain in _PARTS.items()},
            }
        )
    notifications.sort(key=lambda n: n["priority"])
    lights = sorted(
        (
            {"name": data.get(CONF_NAME) or data["light"], "entity": entity("button", f"{item_id}_preview")}
            for item_id, data in hub.lights.items()
        ),
        key=lambda light: light["name"].lower(),
    )
    return {
        "notifications": notifications,
        "lights": lights,
        "dismiss_all": entity("button", f"{entry.entry_id}_dismiss_all"),
        "print_guide": entity("button", f"{entry.entry_id}_print_guide"),
    }


@websocket_api.websocket_command({vol.Required("type"): COMMAND})
@callback
def _model(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Answer with the model, or an error the strategy retries on."""
    model = build_model(hass)
    if model is None:
        connection.send_error(msg["id"], "not_ready", "Notification Lights is still starting")
    else:
        connection.send_result(msg["id"], model)

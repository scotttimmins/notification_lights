/**
 * Notification Lights dashboard strategy.
 *
 * Use it from a dashboard's raw configuration:
 *
 *   strategy:
 *     type: custom:notification-lights
 *     title: Notifications        # optional
 *
 * It lists every Aqara Light Notification by priority (a tile in its own colour, lit while it
 * is showing; tap it to change the colour; then its details and Enabled / Preview / Dismiss controls), a Dismiss all
 * button, and the Notification lights with their calibration buttons. What to show comes from
 * the integration (websocket command notification_lights/model), not from entity states, so
 * it is right straight after a restart. The view is built when the dashboard loads, so reload
 * it after adding or removing items.
 */

const PER_COLUMN = 6;
const RETRIES = 10;
const RETRY_MS = 1000;

/**
 * Ask the integration what to show. Right after a restart it may not be loaded yet, so
 * retry for a few seconds rather than build an empty dashboard.
 * @param {object} hass Home Assistant frontend object.
 * @returns {Promise<{notifications: object[], lights: object[], dismiss_all: string|null, print_guide: string|null}>}
 */
async function loadModel(hass) {
  for (let attempt = 1; ; attempt++) {
    try {
      return await hass.callWS({ type: "notification_lights/model" });
    } catch (err) {
      if (attempt >= RETRIES) throw err;
      await new Promise((resolve) => setTimeout(resolve, RETRY_MS));
    }
  }
}

/**
 * Press a button entity in one tap (the default would open its more-info dialog first).
 * @param {string} entityId A button entity.
 * @returns {object} A tap action.
 */
function press(entityId) {
  return {
    action: "perform-action",
    perform_action: "button.press",
    target: { entity_id: entityId },
  };
}

/**
 * One notification: a tile that lights up in its colour while showing, then its details.
 * @param {object} n A notification from the model.
 * @returns {object} A vertical-stack card.
 */
function notificationCard(n) {
  const rows = [];
  if (n.active) {
    rows.push({ type: "attribute", entity: n.active, attribute: "scope", name: "Where" });
    rows.push({ type: "attribute", entity: n.active, attribute: "footprint", name: "Footprint" });
  }
  if (n.enabled) rows.push({ entity: n.enabled, name: "Enabled" });
  const buttons = [];
  if (n.preview) buttons.push({ entity: n.preview, name: "Preview", icon: "mdi:eye", tap_action: press(n.preview) });
  if (n.dismiss) buttons.push({ entity: n.dismiss, name: "Dismiss", icon: "mdi:bell-off", tap_action: press(n.dismiss) });
  if (buttons.length) rows.push({ type: "buttons", entities: buttons });

  return {
    type: "vertical-stack",
    cards: [
      {
        type: "tile",
        entity: n.colour || n.active,
        name: `${n.priority}. ${n.name}`,
        // The Colour light's picture is a ring showing the footprint in the colour.
        show_entity_picture: Boolean(n.colour),
        icon: "mdi:bell-ring",
        tap_action: { action: "more-info" },
        state_content: ["status"],
      },
      { type: "entities", entities: rows },
    ],
  };
}

class NotificationLightsStrategy extends HTMLElement {
  /**
   * Build the dashboard.
   * @param {object} config The strategy options.
   * @param {object} hass Home Assistant frontend object.
   * @returns {Promise<object>} A Lovelace dashboard config.
   */
  static async generate(config, hass) {
    let model;
    try {
      model = await loadModel(hass);
    } catch (err) {
      return {
        title: config.title || "Notifications",
        views: [
          {
            type: "sections",
            title: config.title || "Notifications",
            sections: [
              {
                type: "grid",
                cards: [
                  {
                    type: "markdown",
                    content: "Notification Lights did not answer. Check the integration is loaded, then reload this page.",
                  },
                ],
              },
            ],
          },
        ],
      };
    }
    const { notifications, lights, dismiss_all: dismissAll, print_guide: printGuide } = model;

    const overview = [
      { type: "heading", heading: config.title || "Notifications", icon: "mdi:bell-ring" },
      {
        type: "markdown",
        content:
          "**{{ states.binary_sensor | selectattr('attributes.part', 'defined') " +
          "| selectattr('attributes.part', 'eq', 'active') " +
          "| selectattr('state', 'eq', 'on') | list | count }}** showing now",
      },
    ];
    if (dismissAll) {
      overview.push({
        type: "button",
        entity: dismissAll,
        name: "Dismiss all",
        icon: "mdi:bell-off-outline",
        show_state: false,
        tap_action: press(dismissAll),
      });
    }
    if (printGuide) {
      overview.push({
        type: "button",
        entity: printGuide,
        name: "Print guide",
        icon: "mdi:printer",
        show_state: false,
        tap_action: press(printGuide),
      });
    }
    if (!notifications.length) {
      overview.push({
        type: "markdown",
        content:
          "No notifications yet. Add them under Settings, Devices & services, " +
          "Notification Lights, Add notification.",
      });
    }

    const sections = [{ type: "grid", cards: overview }];
    for (let i = 0; i < notifications.length; i += PER_COLUMN) {
      const slice = notifications.slice(i, i + PER_COLUMN);
      const cards = slice.map(notificationCard);
      if (i === 0) cards.unshift({ type: "heading", heading: "By priority", icon: "mdi:sort-numeric-ascending" });
      sections.push({ type: "grid", cards });
    }

    if (lights.length) {
      sections.push({
        type: "grid",
        cards: [
          { type: "heading", heading: "Notification lights", icon: "mdi:ceiling-light" },
          {
            type: "entities",
            title: "Calibration preview",
            entities: lights.filter((l) => l.entity).map((l) => ({ entity: l.entity, name: l.name })),
          },
        ],
      });
    }

    return {
      title: config.title || "Notifications",
      views: [
        {
          type: "sections",
          title: config.title || "Notifications",
          path: "notifications",
          max_columns: 4,
          sections,
        },
      ],
    };
  }
}

// Guard: loading the script twice (a cache-busted URL after an update) must not throw.
if (!customElements.get("ll-strategy-notification-lights")) {
  customElements.define("ll-strategy-notification-lights", NotificationLightsStrategy);
}

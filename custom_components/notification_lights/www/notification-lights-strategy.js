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
 * button, and the Notification lights with their calibration buttons. The view is built when
 * the dashboard loads, so reload it after adding or removing items.
 */

const PLATFORM = "notification_lights";
const PER_COLUMN = 6;

/**
 * Read everything this integration exposes, grouped by notification and by light.
 * @param {object} hass Home Assistant frontend object.
 * @returns {{notifications: object[], lights: object[], dismissAll: string|null}}
 */
function readModel(hass) {
  const byName = new Map();
  const lights = [];
  let dismissAll = null;
  let printGuide = null;

  for (const [entityId, entry] of Object.entries(hass.entities || {})) {
    if (entry.platform !== PLATFORM) continue;
    const attrs = hass.states[entityId]?.attributes;
    if (!attrs || !attrs.part) continue;

    if (attrs.part === "dismiss_all") {
      dismissAll = entityId;
    } else if (attrs.part === "print_guide") {
      printGuide = entityId;
    } else if (attrs.part === "calibration") {
      lights.push({ name: attrs.light, entityId });
    } else if (attrs.notification) {
      if (!byName.has(attrs.notification)) {
        byName.set(attrs.notification, { name: attrs.notification, priority: Infinity });
      }
      const item = byName.get(attrs.notification);
      item[attrs.part] = entityId;
      if (attrs.part === "active") {
        item.priority = attrs.priority;
        item.rgb = attrs.colour;
      }
    }
  }

  const notifications = [...byName.values()]
    .filter((n) => n.active)
    .sort((a, b) => a.priority - b.priority);
  lights.sort((a, b) => a.name.localeCompare(b.name));
  return { notifications, lights, dismissAll, printGuide };
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
 * @param {object} n A notification from readModel.
 * @returns {object} A vertical-stack card.
 */
function notificationCard(n) {
  // The Colour light colours its own tile and opens the colour wheel when tapped; without
  // one (older install) fall back to the colour recorded when the dashboard was built.
  const fallback = Array.isArray(n.rgb) ? `rgb(${n.rgb.join(",")})` : "primary";
  const rows = [
    { type: "attribute", entity: n.active, attribute: "scope", name: "Where" },
    { type: "attribute", entity: n.active, attribute: "footprint", name: "Footprint" },
  ];
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
        name: `${Number.isFinite(n.priority) ? `${n.priority}. ` : ""}${n.name}`,
        icon: "mdi:bell-ring",
        ...(n.colour ? {} : { color: fallback }),
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
    const { notifications, lights, dismissAll, printGuide } = readModel(hass);

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
          "Notification Lights, Configure.",
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
            entities: lights.map((l) => ({ entity: l.entityId, name: l.name })),
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

customElements.define("ll-strategy-notification-lights", NotificationLightsStrategy);

// Why: the dashboard must list notifications in priority order and survive the integration starting late.
// Run: node tests/strategy_test.js
const fs = require("fs");
const vm = require("vm");

let Strategy;
const sandbox = {
  HTMLElement: class {},
  customElements: { get: () => undefined, define: (name, cls) => { Strategy = cls; sandbox.defined = name; } },
  console,
};
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(require("path").join(__dirname, "..", "custom_components", "notification_lights", "www", "notification-lights-strategy.js"), "utf8"),
  sandbox,
);

// What the integration's websocket command returns (priority order, entity ids from the registry).
const make = (p, name, extra = {}) => {
  const slug = name.toLowerCase();
  return { name, priority: p, footprint: "eighth_1", slots: [0], active: `binary_sensor.${slug}_active`, enabled: `switch.${slug}_enabled`, colour: `light.${slug}_colour`, preview: `button.${slug}_preview`, dismiss: `button.${slug}_dismiss`, ...extra };
};
const model = {
  notifications: [[1, "Fire"], [2, "Leak"], [3, "Washing"], [4, "Drying"], [5, "Fridge"], [6, "Vacuum"], [7, "Rain"]].map(([p, n]) => make(p, n)).concat([make(8, "Bins", { colour: null })]),
  lights: [{ name: "Bedroom", entity: "button.bed_cal" }, { name: "Dining", entity: "button.dining_cal" }],
  dismiss_all: "button.dismiss_all",
  print_guide: "button.print_guide",
};
let calls = 0;
// The integration is not ready for the first two asks, as right after a restart.
const hass = {
  callWS: async (msg) => {
    if (msg.type !== "notification_lights/model") throw new Error("wrong command");
    if (++calls < 3) throw new Error("not_ready");
    return model;
  },
};
sandbox.setTimeout = (fn) => fn();

(async () => {
  const cfg = await Strategy.generate({}, hass);
  const view = cfg.views[0];
  const assert = (c, m) => { if (!c) { console.error("FAIL", m); process.exit(1); } };
  assert(sandbox.defined === "ll-strategy-notification-lights", "element name");
  assert(view.type === "sections", "sections view");
  const names = view.sections.flatMap((s) => s.cards).filter((c) => c.type === "vertical-stack").map((c) => c.cards[0].name);
  assert(JSON.stringify(names) === JSON.stringify(["1. Fire", "2. Leak", "3. Washing", "4. Drying", "5. Fridge", "6. Vacuum", "7. Rain", "8. Bins"]), "priority order: " + names);
  const tiles = view.sections.flatMap((s) => s.cards).filter((c) => c.type === "vertical-stack").map((c) => c.cards[0]);
  assert(calls === 3, "retried until the integration answered, calls=" + calls);
  assert(tiles.find((t) => t.name === "1. Fire").entity === "light.fire_colour", "tile uses the colour light");
  assert(tiles.find((t) => t.name === "1. Fire").show_entity_picture === true, "tile shows the ring picture");
  assert(tiles.find((t) => t.name === "8. Bins").show_entity_picture === false, "no picture without a colour light");
  assert(tiles.find((t) => t.name === "8. Bins").entity === "binary_sensor.bins_active", "falls back to the active sensor");
  assert(view.sections.length === 4, "overview + 2 columns of notifications + lights, got " + view.sections.length);
  const flat = JSON.stringify(view);
  // One tap must press: every Preview/Dismiss button has a press action (no more-info popup).
  const rows = view.sections.flatMap((s) => s.cards).filter((c) => c.type === "vertical-stack").flatMap((c) => c.cards[1].entities).filter((r) => r.type === "buttons").flatMap((r) => r.entities);
  assert(rows.length === 16 && rows.every((b) => b.tap_action.perform_action === "button.press" && b.tap_action.target.entity_id === b.entity), "buttons press in one tap");
  assert(flat.includes("button.print_guide"), "print guide button");
  assert(flat.includes("button.dismiss_all") && flat.includes("button.bed_cal"), "dismiss all and lights present");
  const empty = await Strategy.generate({ title: "X" }, { callWS: async () => ({ notifications: [], lights: [], dismiss_all: null, print_guide: null }) });
  assert(JSON.stringify(empty).includes("No notifications yet"), "empty state");
  const down = await Strategy.generate({}, { callWS: async () => { throw new Error("down"); } });
  assert(JSON.stringify(down).includes("did not answer"), "says so when the integration never answers");
  console.log("strategy ok:", names.length, "notifications,", view.sections.length, "sections");
})();

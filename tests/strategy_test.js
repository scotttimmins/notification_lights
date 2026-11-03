// Why: the dashboard must list notifications in priority order and ignore other integrations.
// Run: node tests/strategy_test.js
const fs = require("fs");
const vm = require("vm");

let Strategy;
const sandbox = {
  HTMLElement: class {},
  customElements: { define: (name, cls) => { Strategy = cls; sandbox.defined = name; } },
  console,
};
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(require("path").join(__dirname, "..", "custom_components", "notification_lights", "www", "notification-lights-strategy.js"), "utf8"),
  sandbox,
);

const entities = {};
const states = {};
function add(id, attrs) {
  entities[id] = { platform: "notification_lights" };
  states[id] = { attributes: attrs };
}
// 8 notifications, deliberately out of priority order
[[3, "Washing"], [1, "Fire"], [2, "Leak"], [4, "Drying"], [5, "Fridge"], [6, "Vacuum"], [7, "Rain"], [8, "Bins"]].forEach(([p, name]) => {
  const slug = name.toLowerCase();
  add(`binary_sensor.${slug}_active`, { notification: name, part: "active", priority: p, footprint: "eighth_1", scope: "house", colour: [255, 0, 0] });
  add(`switch.${slug}_enabled`, { notification: name, part: "enabled" });
  add(`button.${slug}_preview`, { notification: name, part: "preview" });
  add(`button.${slug}_dismiss`, { notification: name, part: "dismiss" });
  if (name !== "Bins") add(`light.${slug}_colour`, { notification: name, part: "colour" });
});
add("button.dismiss_all", { part: "dismiss_all" });
add("button.bed_cal", { part: "calibration", light: "Bedroom" });
add("button.dining_cal", { part: "calibration", light: "Dining" });
entities["sensor.other"] = { platform: "other" };
states["sensor.other"] = { attributes: { part: "active", notification: "Nope" } };

(async () => {
  const cfg = await Strategy.generate({}, { entities, states });
  const view = cfg.views[0];
  const assert = (c, m) => { if (!c) { console.error("FAIL", m); process.exit(1); } };
  assert(sandbox.defined === "ll-strategy-notification-lights", "element name");
  assert(view.type === "sections", "sections view");
  const names = view.sections.flatMap((s) => s.cards).filter((c) => c.type === "vertical-stack").map((c) => c.cards[0].name);
  assert(JSON.stringify(names) === JSON.stringify(["1. Fire", "2. Leak", "3. Washing", "4. Drying", "5. Fridge", "6. Vacuum", "7. Rain", "8. Bins"]), "priority order: " + names);
  const tiles = view.sections.flatMap((s) => s.cards).filter((c) => c.type === "vertical-stack").map((c) => c.cards[0]);
  assert(tiles.find((t) => t.name === "1. Fire").entity === "light.fire_colour", "tile uses the colour light");
  assert(tiles.find((t) => t.name === "8. Bins").entity === "binary_sensor.bins_active", "falls back to the active sensor");
  assert(!names.some((n) => n.includes("Nope")), "other platforms ignored");
  assert(view.sections.length === 4, "overview + 2 columns of notifications + lights, got " + view.sections.length);
  const flat = JSON.stringify(view);
  assert(flat.includes("button.dismiss_all") && flat.includes("button.bed_cal"), "dismiss all and lights present");
  const empty = await Strategy.generate({ title: "X" }, { entities: {}, states: {} });
  assert(JSON.stringify(empty).includes("No notifications yet"), "empty state");
  console.log("strategy ok:", names.length, "notifications,", view.sections.length, "sections");
})();

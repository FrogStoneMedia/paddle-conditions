// Convert the integration's native forecast series (°F, mph, miles) into the
// unit Home Assistant displays for the matching sensor, so charts match the
// numbers on the entity rows.

const TEMP = {
  "°F": (f) => f,
  "°C": (f) => ((f - 32) * 5) / 9,
  K: (f) => ((f - 32) * 5) / 9 + 273.15,
};
const SPEED = {
  mph: (v) => v,
  "km/h": (v) => v * 1.609344,
  "m/s": (v) => v * 0.44704,
  kn: (v) => v * 0.868976,
  "ft/s": (v) => v * 1.466667,
  "Beaufort": null,
};
const DISTANCE = {
  mi: (v) => v,
  km: (v) => v * 1.609344,
  m: (v) => v * 1609.344,
  ft: (v) => v * 5280,
  yd: (v) => v * 1760,
};

const NATIVE = { temperature: "°F", speed: "mph", distance: "mi" };
const TABLES = { temperature: TEMP, speed: SPEED, distance: DISTANCE };

/** The unit HA shows for a sensor, or the native unit if unknown/unsupported. */
export function displayUnit(stateObj, kind) {
  const unit = stateObj?.attributes?.unit_of_measurement;
  return unit && TABLES[kind][unit] ? unit : NATIVE[kind];
}

/** Convert one native value. Null stays null. */
export function convert(value, kind, unit) {
  if (value == null || Number.isNaN(Number(value))) return null;
  const fn = TABLES[kind][unit] || TABLES[kind][NATIVE[kind]];
  return fn(Number(value));
}

// Display unit -> native unit, for values that arrive in some other unit.
const TO_NATIVE = {
  temperature: { "°F": (v) => v, "°C": (v) => (v * 9) / 5 + 32, K: (v) => ((v - 273.15) * 9) / 5 + 32 },
  speed: { mph: (v) => v, "km/h": (v) => v / 1.609344, "m/s": (v) => v / 0.44704, kn: (v) => v / 0.868976, "ft/s": (v) => v / 1.466667 },
  distance: { mi: (v) => v, km: (v) => v / 1.609344, m: (v) => v / 1609.344, ft: (v) => v / 5280, yd: (v) => v / 1760 },
};

/** Convert a value from one display unit to another of the same kind. */
export function convertBetween(value, kind, fromUnit, toUnit) {
  if (value == null || Number.isNaN(Number(value))) return null;
  const toNative = TO_NATIVE[kind][fromUnit];
  if (!toNative) return null; // Unknown source unit: better no value than a wrong one.
  return convert(toNative(Number(value)), kind, toUnit);
}

export function convertSeries(values, kind, unit) {
  return (values || []).map((v) => convert(v, kind, unit));
}

/** Format a sensor the way HA does (localized number + unit), with a plain fallback. */
export function formatState(hass, stateObj) {
  if (!stateObj) return "—";
  if (stateObj.state === "unavailable" || stateObj.state === "unknown") return "—";
  if (typeof hass?.formatEntityState === "function") return hass.formatEntityState(stateObj);
  const unit = stateObj.attributes?.unit_of_measurement;
  return unit ? `${stateObj.state} ${unit}` : String(stateObj.state);
}

/** Numeric state or null. */
export function numericState(stateObj) {
  if (!stateObj) return null;
  const n = Number.parseFloat(stateObj.state);
  return Number.isFinite(n) ? n : null;
}

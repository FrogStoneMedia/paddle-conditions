// Resolve a paddle location's sensors through Home Assistant's entity registry.
//
// Cards are configured with one entity (usually the Paddle Score). Its
// siblings are found by device and translation key, so renamed entities keep
// working. The old suffix guess is only a fallback for very old frontends.

export const DOMAIN = "paddle_conditions";

// Translation key -> default entity_id suffix (English entity names).
const DEFAULT_SUFFIX = {
  paddle_score: "paddle_score",
  rating: "rating",
  wind_speed: "wind_speed",
  wind_gusts: "wind_gusts",
  wind_direction: "wind_direction",
  air_temp: "air_temperature",
  water_temp: "water_temperature",
  uv_index: "uv_index",
  aqi: "air_quality_index",
  visibility: "visibility",
  precipitation: "precipitation_chance",
  streamflow: "streamflow",
  river_stage: "river_stage",
  reservoir_level: "reservoir_level",
  dam_outflow: "dam_outflow",
  condition: "conditions",
  forecast_3hr: "3_hour_forecast",
};

export const SENSOR_KEYS = Object.keys(DEFAULT_SUFFIX);

/**
 * Map every sensor of the location `entityId` belongs to.
 * Returns { [translationKey]: entityId }.
 */
export function resolveLocation(hass, entityId) {
  const registry = hass?.entities;
  const entry = registry?.[entityId];
  if (entry?.device_id) {
    const ids = {};
    for (const candidate of Object.values(registry)) {
      if (candidate.device_id === entry.device_id && candidate.platform === DOMAIN && candidate.translation_key) {
        ids[candidate.translation_key] = candidate.entity_id;
      }
    }
    if (Object.keys(ids).length) return ids;
  }
  return guessBySuffix(entityId);
}

function guessBySuffix(entityId) {
  const ids = {};
  if (typeof entityId !== "string") return ids;
  const match = Object.entries(DEFAULT_SUFFIX).find(([, suffix]) => entityId.endsWith(`_${suffix}`));
  if (!match) return { paddle_score: entityId };
  const base = entityId.slice(0, -(match[1].length + 1));
  for (const [key, suffix] of Object.entries(DEFAULT_SUFFIX)) ids[key] = `${base}_${suffix}`;
  return ids;
}

/** Whether entityId is a Paddle Conditions score sensor. */
export function isScoreEntity(hass, entityId) {
  const entry = hass?.entities?.[entityId];
  if (entry) return entry.platform === DOMAIN && entry.translation_key === "paddle_score";
  return typeof entityId === "string" && entityId.startsWith("sensor.") && entityId.endsWith("_paddle_score");
}

/** All Paddle Score entities, for card stubs and the spots card. */
export function scoreEntities(hass) {
  const registry = hass?.entities;
  if (registry) {
    const found = Object.values(registry)
      .filter((e) => e.platform === DOMAIN && e.translation_key === "paddle_score")
      .map((e) => e.entity_id);
    if (found.length) return found;
  }
  return Object.keys(hass?.states || {}).filter((id) => id.startsWith("sensor.") && id.endsWith("_paddle_score"));
}

/** A location view over hass: state(key), id(key), and a cheap change signature. */
export class PaddleLocation {
  constructor(hass, entityId) {
    this.hass = hass;
    this.entityId = entityId;
    this.ids = resolveLocation(hass, entityId);
    if (!this.ids.paddle_score && entityId) this.ids.paddle_score = entityId;
  }

  id(key) {
    return this.ids[key];
  }

  state(key) {
    const id = this.ids[key];
    return id ? this.hass.states[id] : undefined;
  }

  /** States change by identity in HA, so this is enough to skip redundant renders. */
  signature(hass) {
    return Object.values(this.ids).map((id) => hass.states[id]);
  }
}

export function signatureChanged(prev, next) {
  if (!prev || prev.length !== next.length) return true;
  return next.some((s, i) => s !== prev[i]);
}

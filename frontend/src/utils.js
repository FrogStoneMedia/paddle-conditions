// Score thresholds (must match const.py SCORE_GO=70, SCORE_CAUTION=40)
const SCORE_GO = 70;
const SCORE_CAUTION = 40;

const RATING_COLORS = {
  GO: "#4CAF50",
  CAUTION: "#FF9800",
  NO_GO: "#F44336",
};
const DEFAULT_COLOR = "#9E9E9E";

const RATING_ICONS = {
  GO: "mdi:check-circle",
  CAUTION: "mdi:alert",
  NO_GO: "mdi:close-circle",
};

export function colorForRating(rating) {
  return RATING_COLORS[rating] ?? DEFAULT_COLOR;
}

export function colorForScore(score) {
  if (score == null) return DEFAULT_COLOR;
  if (score >= SCORE_GO) return RATING_COLORS.GO;
  if (score >= SCORE_CAUTION) return RATING_COLORS.CAUTION;
  return RATING_COLORS.NO_GO;
}

export function formatScore(score) {
  if (score == null) return "--";
  return `${score}%`;
}

export function iconForRating(rating) {
  return RATING_ICONS[rating] ?? "mdi:help-circle";
}

export function fireMoreInfo(element, entityId) {
  element.dispatchEvent(
    new CustomEvent("hass-more-info", {
      bubbles: true,
      composed: true,
      detail: { entityId },
    })
  );
}

export function labelForRating(rating) {
  const labels = { GO: "Good to go", CAUTION: "Caution", NO_GO: "Not recommended" };
  return labels[rating] || "Unknown";
}

/** Make an element interactive: adds role="button", tabindex, keyboard Enter/Space. */
export function makeInteractive(el, handler, label) {
  el.setAttribute("role", "button");
  el.setAttribute("tabindex", "0");
  if (label) el.setAttribute("aria-label", label);
  el.addEventListener("click", handler);
  el.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handler(e);
    }
  });
}

export const FACTOR_META = {
  wind_speed: { label: "Wind Speed", icon: "mdi:weather-windy", unit: "mph" },
  wind_gusts: { label: "Wind Gusts", icon: "mdi:weather-windy-variant", unit: "mph" },
  air_quality: { label: "Air Quality", icon: "mdi:air-filter", unit: "AQI" },
  temperature: { label: "Temperature", icon: "mdi:thermometer", unit: "\u00B0F" },
  uv_index: { label: "UV Index", icon: "mdi:white-balance-sunny", unit: "" },
  visibility: { label: "Visibility", icon: "mdi:eye", unit: "mi" },
  precipitation: { label: "Precipitation", icon: "mdi:weather-rainy", unit: "%" },
};

// Maps scoring factor keys to sensor entity suffixes
// air_quality -> aqi, temperature -> air_temp (not 1:1)
export const FACTOR_SENSOR_SUFFIX = {
  wind_speed: "wind_speed",
  wind_gusts: "wind_gusts",
  air_quality: "aqi",
  temperature: "air_temp",
  uv_index: "uv_index",
  visibility: "visibility",
  precipitation: "precipitation",
};

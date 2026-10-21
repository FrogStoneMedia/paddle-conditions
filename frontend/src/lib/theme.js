// Rating colours with separate light/dark palettes, each chosen for at least
// 4.5:1 contrast against the card (text) or with white text (hero/badges).
// Rating is always also given as text, never by colour alone.

export const PALETTE = {
  // Text colours are checked against every surface they sit on: the card and
  // the tile/secondary backgrounds of HA's default light and dark themes.
  light: {
    text: { GO: "#1B5E20", CAUTION: "#92400E", NO_GO: "#B71C1C", NONE: "#555555" },
    backgrounds: ["#FFFFFF", "#F2F2F2", "#E5E5E5"],
  },
  dark: {
    text: { GO: "#81C784", CAUTION: "#FFB74D", NO_GO: "#EF9A9A", NONE: "#BDBDBD" },
    backgrounds: ["#1C1C1C", "#111111", "#282828", "#2C2C2C"],
  },
  // White text sits on these in both themes.
  fill: {
    GO: ["#1B5E20", "#2E7D32"],
    CAUTION: ["#92400E", "#B45309"],
    NO_GO: ["#B71C1C", "#C62828"],
    NONE: ["#424242", "#616161"],
  },
};

// Chart line/area colours per theme: at least 3:1 against every surface
// they're drawn on (WCAG 1.4.11). Chart toggles put white text on the light
// set and near-black text on the dark set.
export const SERIES = {
  light: { score: "#2E7D32", wind: "#1565C0", gust: "#BF360C", temp: "#BF360C", water: "#00838F", uv: "#8D6E00", rain: "#6A1B9A", flow: "#00695C" },
  dark: { score: "#81C784", wind: "#64B5F6", gust: "#FFB74D", temp: "#FF8A65", water: "#4DD0E1", uv: "#FFD54F", rain: "#CE93D8", flow: "#80CBC4" },
  onFill: { light: "#FFFFFF", dark: "#111111" },
};

export function seriesColors(hass) {
  return isDark(hass) ? SERIES.dark : SERIES.light;
}

export function onSeriesFill(hass) {
  return isDark(hass) ? SERIES.onFill.dark : SERIES.onFill.light;
}

export function ratingForScore(score) {
  if (score == null || Number.isNaN(score)) return "NONE";
  if (score >= 70) return "GO";
  if (score >= 40) return "CAUTION";
  return "NO_GO";
}

export function normalizeRating(rating) {
  const r = String(rating || "").toUpperCase();
  return r === "GO" || r === "CAUTION" || r === "NO_GO" ? r : "NONE";
}

export const RATING_TEXT = { GO: "Go", CAUTION: "Caution", NO_GO: "No-go", NONE: "Unavailable" };

export function isDark(hass) {
  return Boolean(hass?.themes?.darkMode);
}

/** CSS custom properties for the host element, per theme. */
export function themeVars(hass) {
  const mode = isDark(hass) ? PALETTE.dark : PALETTE.light;
  const vars = {};
  for (const [k, v] of Object.entries(mode.text)) vars[`--pc-${k.toLowerCase().replace("_", "-")}`] = v;
  for (const [k, [a, b]] of Object.entries(PALETTE.fill)) {
    vars[`--pc-fill-${k.toLowerCase().replace("_", "-")}`] = `linear-gradient(135deg, ${a}, ${b})`;
    vars[`--pc-solid-${k.toLowerCase().replace("_", "-")}`] = a;
  }
  return vars;
}

export function applyTheme(host, hass) {
  for (const [k, v] of Object.entries(themeVars(hass))) host.style.setProperty(k, v);
}

/** CSS variable name for a rating's text colour, e.g. var(--pc-caution). */
export function ratingVar(rating) {
  return `var(--pc-${normalizeRating(rating).toLowerCase().replace("_", "-")})`;
}

export function fillVar(rating) {
  return `var(--pc-fill-${normalizeRating(rating).toLowerCase().replace("_", "-")})`;
}

// WCAG relative luminance / contrast, used by tests.
export function contrast(hexA, hexB) {
  const lum = (hex) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  };
  const [hi, lo] = [lum(hexA), lum(hexB)].sort((a, b) => b - a);
  return (hi + 0.05) / (lo + 0.05);
}

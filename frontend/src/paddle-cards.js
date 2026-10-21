// Paddle Conditions dashboard cards, bundled into one module.

import "./cards/paddle-score-card.js";
import "./cards/paddle-spots-card.js";
import "./cards/paddle-factors-card.js";
import "./cards/paddle-forecast-card.js";
import "./cards/paddle-chart-card.js";
import "./cards/paddle-history-card.js";
import { isScoreEntity } from "./lib/entities.js";

const DOCS = "https://github.com/FrogStoneMedia/paddle-conditions#dashboard";
// [type, name, description, suggest for a picked Paddle Score sensor]
const CARDS = [
  ["paddle-score-card", "Paddle Score", "Go / Caution / No-go hero, factor breakdown, forecast strip and hourly details", true],
  ["paddle-spots-card", "Paddle Spots", "Every paddle spot's score and rating at a glance", false],
  ["paddle-factors-card", "Paddle Factors", "Each scoring factor with its reading and sub-score", true],
  ["paddle-forecast-card", "Paddle Forecast", "The next 24 hours in 3-hour blocks, with the best window", true],
  ["paddle-chart-card", "Paddle Chart", "Score over the next 24 hours with wind, temperature, UV and rain layers", true],
  ["paddle-history-card", "Paddle History", "Score history and summary from the recorder", true],
];

/** Entries for window.customCards, including "By entity" suggestions in the card picker. */
export function customCardEntries() {
  return CARDS.map(([type, name, description, suggest]) => ({
    type,
    name,
    description,
    preview: true,
    documentationURL: DOCS,
    ...(suggest && {
      getEntitySuggestion: (hass, entityId) => (isScoreEntity(hass, entityId) ? { config: { type: `custom:${type}`, entity: entityId } } : null),
    }),
  }));
}

if (typeof window !== "undefined") {
  window.customCards = window.customCards || [];
  for (const entry of customCardEntries()) {
    if (!window.customCards.some((c) => c.type === entry.type)) window.customCards.push(entry);
  }
}

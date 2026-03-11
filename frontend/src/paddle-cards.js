// Paddle Conditions - Custom Lovelace Cards
// Bundled dashboard cards for Home Assistant integration

import "./cards/paddle-score-card.js";
import "./cards/paddle-factors-card.js";
import "./cards/paddle-chips-card.js";
import "./cards/paddle-forecast-card.js";
import "./cards/paddle-fitness-card.js";
import "./cards/paddle-chart-card.js";
import "./cards/paddle-history-card.js";

import "./editors/paddle-score-editor.js";
import "./editors/paddle-factors-editor.js";
import "./editors/paddle-chips-editor.js";
import "./editors/paddle-forecast-editor.js";
import "./editors/paddle-fitness-editor.js";
import "./editors/paddle-chart-editor.js";
import "./editors/paddle-history-editor.js";

// Register cards with HA's card picker
window.customCards = window.customCards || [];
window.customCards.push(
  {
    type: "paddle-score-card",
    name: "Paddle Score",
    description: "Paddle conditions score with Go/Caution/No-go rating",
    preview: true,
  },
  {
    type: "paddle-factors-card",
    name: "Paddle Factors",
    description: "Factor breakdown showing individual scoring components",
    preview: true,
  },
  {
    type: "paddle-chips-card",
    name: "Paddle Chips",
    description: "Location navigation chips with quick scores",
    preview: true,
  },
  {
    type: "paddle-forecast-card",
    name: "Paddle Forecast",
    description: "3-hour forecast blocks with best window highlight",
    preview: true,
  },
  {
    type: "paddle-fitness-card",
    name: "Paddle Fitness",
    description: "Session tracking placeholder (coming soon)",
    preview: false,
  },
  {
    type: "paddle-chart-card",
    name: "Paddle Chart",
    description: "Multi-metric forecast chart with toggleable overlays",
    preview: true,
  },
  {
    type: "paddle-history-card",
    name: "Paddle History",
    description: "Score trend over time with summary statistics",
    preview: true,
  }
);

console.info(
  "%c PADDLE CONDITIONS %c Cards loaded ",
  "background: #4CAF50; color: white; font-weight: bold; padding: 2px 6px; border-radius: 4px 0 0 4px;",
  "background: #eee; color: #333; padding: 2px 6px; border-radius: 0 4px 4px 0;"
);
